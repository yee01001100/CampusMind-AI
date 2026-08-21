from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from campusmind.domain import Course, Reminder, StudentProfile, Task
from campusmind.repositories import (
    CourseRepository,
    NoticeRepository,
    ReminderRepository,
    StudentProfileRepository,
    TaskRepository,
)
from campusmind.storage import SQLiteDatabase, load_demo_data


ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "data/demo"
SHANGHAI = timezone(timedelta(hours=8))
TERM_START = date(2026, 8, 17)


def loaded_database(tmp_path: Path) -> SQLiteDatabase:
    database = SQLiteDatabase(tmp_path / "campusmind-test.sqlite3")
    load_demo_data(database, DEMO)
    return database


def test_database_initialization_is_repeatable_and_enables_foreign_keys(tmp_path: Path):
    database = SQLiteDatabase(tmp_path / "repeat.sqlite3")
    database.initialize()
    database.initialize()
    with database.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        table_count = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='tasks'"
        ).fetchone()[0]
    assert table_count == 1


def test_foreign_key_constraint_rejects_unknown_student(tmp_path: Path):
    database = SQLiteDatabase(tmp_path / "fk.sqlite3")
    database.initialize()
    with database.connect() as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO courses
                (id, student_id, name, weekday, start_time, end_time, start_week,
                 end_week, week_pattern, custom_weeks_json)
            VALUES ('bad-course', 'missing-student', '模拟课', 1, '08:00', '09:00', 1, 2, 'all', '[]')
            """
        )


def test_demo_loader_has_required_counts_and_is_idempotent(tmp_path: Path):
    database = SQLiteDatabase(tmp_path / "demo.sqlite3")
    first = load_demo_data(database, DEMO)
    second = load_demo_data(database, DEMO)
    assert (first.profiles, first.courses, first.notices, first.tasks, first.reminders) == (1, 8, 5, 8, 5)
    assert (first.notices_created, first.tasks_created) == (5, 8)
    assert (second.notices_created, second.tasks_created) == (0, 0)
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM courses").fetchone()[0] == 8
        assert connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 8


def test_storage_cli_creates_separate_demo_database_with_knowledge(tmp_path: Path):
    database_path = tmp_path / "cli-demo.sqlite3"
    completed = subprocess.run(
        [
            sys.executable, "-m", "campusmind.storage", "--database", str(database_path),
            "--demo-dir", str(DEMO), "--knowledge-dir", str(ROOT / "data/knowledge"),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    output = json.loads(completed.stdout)
    assert output["demo"]["tasks"] == 8
    assert output["knowledge"]["imported"] == 10
    with SQLiteDatabase(database_path).connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM rag_sources").fetchone()[0] == 10


def test_demo_manifest_and_two_conflict_groups_are_explicitly_simulated():
    manifest = json.loads((DEMO / "manifest.json").read_text(encoding="utf-8"))
    conflicts = json.loads((DEMO / "conflicts.json").read_text(encoding="utf-8"))
    assert manifest["is_demo"] is True
    assert manifest["contains_real_personal_data"] is False
    assert len(conflicts) >= 2
    assert all(item["is_demo"] is True and len(item["course_ids"]) >= 2 for item in conflicts)


def test_course_query_handles_odd_even_custom_weeks(tmp_path: Path):
    repository = CourseRepository(loaded_database(tmp_path))
    odd_monday = repository.list_for_student_on_date(
        "student-demo-001", date(2026, 8, 17), term_start=TERM_START
    )
    even_monday = repository.list_for_student_on_date(
        "student-demo-001", date(2026, 8, 24), term_start=TERM_START
    )
    custom_saturday = repository.list_for_student_on_date(
        "student-demo-001", date(2026, 9, 5), term_start=TERM_START
    )
    assert {course.id for course in odd_monday} == {"course-demo-001", "course-demo-002"}
    assert {course.id for course in even_monday} == {"course-demo-001"}
    assert {course.id for course in custom_saturday} == {"course-demo-008"}


def test_course_query_requires_week_one_monday(tmp_path: Path):
    repository = CourseRepository(loaded_database(tmp_path))
    with pytest.raises(ValueError, match="Monday"):
        repository.list_for_student_on_date(
            "student-demo-001", date(2026, 8, 17), term_start=date(2026, 8, 18)
        )


def test_different_students_are_isolated_in_course_and_task_queries(tmp_path: Path):
    database = loaded_database(tmp_path)
    StudentProfileRepository(database).save(StudentProfile(id="student-demo-002", name="另一模拟学生"))
    CourseRepository(database).save(
        Course(
            id="course-demo-other", student_id="student-demo-002", name="隔离测试课程",
            weekday=1, start_time="13:00", end_time="14:00", start_week=1,
            end_week=16, week_pattern="all", custom_weeks=[],
        )
    )
    TaskRepository(database).create(
        Task(
            id="task-demo-other", student_id="student-demo-002", title="隔离测试任务",
            task_type="general", priority="normal", status="pending",
            due_at="2026-08-22T10:00:00+08:00", source_notice_id=None,
            dedupe_key="student-demo-002:isolated", created_at="2026-08-21T10:00:00+08:00",
            completed_at=None,
        )
    )
    first_courses = CourseRepository(database).list_for_student("student-demo-001")
    second_courses = CourseRepository(database).list_for_student("student-demo-002")
    first_tasks = TaskRepository(database).list_for_student("student-demo-001")
    second_tasks = TaskRepository(database).list_for_student("student-demo-002")
    assert all(item.student_id == "student-demo-001" for item in first_courses + first_tasks)
    assert {item.id for item in second_courses} == {"course-demo-other"}
    assert {item.id for item in second_tasks} == {"task-demo-other"}


def test_task_dedupe_returns_original_without_second_row(tmp_path: Path):
    database = loaded_database(tmp_path)
    repository = TaskRepository(database)
    original = repository.get("task-demo-001")
    assert original is not None
    attempted = original.model_copy(update={"id": "task-duplicate-attempt", "title": "不应覆盖"})
    stored, created = repository.create(attempted)
    assert created is False
    assert stored.id == "task-demo-001"
    assert stored.title == original.title
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM tasks WHERE dedupe_key = ?", (original.dedupe_key,)
        ).fetchone()[0] == 1


def test_task_complete_restore_and_status_query(tmp_path: Path):
    repository = TaskRepository(loaded_database(tmp_path))
    completed_at = datetime(2026, 8, 21, 15, 0, tzinfo=SHANGHAI)
    completed = repository.complete("student-demo-001", "task-demo-001", completed_at=completed_at)
    assert completed is not None and completed.status == "completed"
    assert completed.completed_at == completed_at
    assert "task-demo-001" in {
        task.id for task in repository.list_for_student("student-demo-001", status="completed")
    }
    restored = repository.restore("student-demo-001", "task-demo-001")
    assert restored is not None and restored.status == "pending" and restored.completed_at is None


def test_complete_rejects_naive_time_and_wrong_student_does_not_mutate(tmp_path: Path):
    repository = TaskRepository(loaded_database(tmp_path))
    with pytest.raises(ValueError, match="timezone"):
        repository.complete("student-demo-001", "task-demo-001", completed_at=datetime(2026, 8, 21, 12))
    assert repository.complete(
        "student-demo-999", "task-demo-001", completed_at=datetime(2026, 8, 21, 12, tzinfo=SHANGHAI)
    ) is None
    assert repository.get("task-demo-001").status == "pending"


def test_notice_duplicate_preserves_original_raw_text_and_source(tmp_path: Path):
    database = loaded_database(tmp_path)
    repository = NoticeRepository(database)
    original = repository.get("notice-demo-001")
    assert original is not None
    attempted = original.model_copy(update={"raw_text": "覆盖尝试", "source_ref": "demo://wrong"})
    stored, created = repository.create(attempted)
    assert created is False
    assert stored.raw_text == original.raw_text
    assert stored.source_ref == original.source_ref


def test_notice_and_task_queries_use_timezone_aware_day_boundaries(tmp_path: Path):
    database = loaded_database(tmp_path)
    notices = NoticeRepository(database).list_for_date(date(2026, 8, 22), tzinfo=SHANGHAI)
    tasks = TaskRepository(database).list_for_student_on_date(
        "student-demo-001", date(2026, 8, 22), tzinfo=SHANGHAI
    )
    assert {item.id for item in notices} == {"notice-demo-001"}
    assert {item.id for item in tasks} == {"task-demo-001"}


def test_records_persist_after_database_object_restart(tmp_path: Path):
    path = tmp_path / "restart.sqlite3"
    first = SQLiteDatabase(path)
    load_demo_data(first, DEMO)
    first.close()
    second = SQLiteDatabase(path)
    second.initialize()
    assert StudentProfileRepository(second).get("student-demo-001") is not None
    assert TaskRepository(second).get("task-demo-006").title == "提交程序设计实验一"


def test_reminder_time_range_and_due_exclude_completed_tasks(tmp_path: Path):
    database = loaded_database(tmp_path)
    repository = ReminderRepository(database)
    start = datetime(2026, 8, 21, 0, 0, tzinfo=SHANGHAI)
    end = datetime(2026, 8, 24, 0, 0, tzinfo=SHANGHAI)
    in_range = repository.list_in_range(start, end, student_id="student-demo-001")
    assert {item.id for item in in_range} == {"reminder-demo-001", "reminder-demo-002"}
    due = repository.list_due(datetime(2026, 8, 21, 19, 0, tzinfo=SHANGHAI))
    assert {item.id for item in due} == {"reminder-demo-001"}
    TaskRepository(database).complete(
        "student-demo-001", "task-demo-001",
        completed_at=datetime(2026, 8, 21, 18, 30, tzinfo=SHANGHAI),
    )
    assert repository.list_due(datetime(2026, 8, 21, 19, 0, tzinfo=SHANGHAI)) == []


def test_reminder_foreign_key_rejects_unknown_task(tmp_path: Path):
    database = loaded_database(tmp_path)
    reminder = Reminder(
        id="bad-reminder", task_id="missing-task", trigger_at="2026-08-22T10:00:00+08:00",
        channel="in_app", status="pending", sent_at=None, failure_reason=None,
    )
    with pytest.raises(sqlite3.IntegrityError):
        ReminderRepository(database).save(reminder)
