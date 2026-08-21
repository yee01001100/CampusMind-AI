"""SQLite repository implementations for the five public models."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable

from campusmind.domain import Course, Notice, Reminder, StudentProfile, Task, TaskStatus
from campusmind.storage.database import SQLiteDatabase


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _day_bounds(day: date, tzinfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=tzinfo)
    return start, start + timedelta(days=1)


class StudentProfileRepository:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def save(self, profile: StudentProfile) -> StudentProfile:
        values = profile.model_dump(mode="json")
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO student_profiles
                    (id, name, major, grade, timezone, quiet_hours_start,
                     quiet_hours_end, interests_json, reminder_preferences_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, major=excluded.major, grade=excluded.grade,
                    timezone=excluded.timezone,
                    quiet_hours_start=excluded.quiet_hours_start,
                    quiet_hours_end=excluded.quiet_hours_end,
                    interests_json=excluded.interests_json,
                    reminder_preferences_json=excluded.reminder_preferences_json
                """,
                (
                    values["id"], values["name"], values["major"], values["grade"],
                    values["timezone"], values["quiet_hours_start"],
                    values["quiet_hours_end"], _json(values["interests"]),
                    _json(values["reminder_preferences"]),
                ),
            )
            connection.commit()
        return profile

    def get(self, student_id: str) -> StudentProfile | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM student_profiles WHERE id = ?", (student_id,)
            ).fetchone()
        if row is None:
            return None
        return StudentProfile(
            id=row["id"], name=row["name"], major=row["major"], grade=row["grade"],
            timezone=row["timezone"], quiet_hours_start=row["quiet_hours_start"],
            quiet_hours_end=row["quiet_hours_end"],
            interests=json.loads(row["interests_json"]),
            reminder_preferences=json.loads(row["reminder_preferences_json"]),
        )

    def list_all(self) -> list[StudentProfile]:
        with self.database.connect() as connection:
            ids = [row["id"] for row in connection.execute(
                "SELECT id FROM student_profiles ORDER BY id"
            )]
        return [profile for student_id in ids if (profile := self.get(student_id)) is not None]


class NoticeRepository:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def create(self, notice: Notice) -> tuple[Notice, bool]:
        values = notice.model_dump(mode="json")
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO notices
                    (id, title, raw_text, audience_json, published_at, deadline,
                     actions_json, priority, source_type, source_ref, confidence,
                     needs_confirmation, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    values["id"], values["title"], values["raw_text"],
                    _json(values["audience"]), values["published_at"], values["deadline"],
                    _json(values["actions"]), values["priority"], values["source_type"],
                    values["source_ref"], values["confidence"],
                    int(values["needs_confirmation"]), values["created_at"],
                ),
            )
            connection.commit()
            created = cursor.rowcount == 1
        stored = self.get(notice.id)
        if stored is None:  # pragma: no cover - defensive database failure guard
            raise RuntimeError("notice was not persisted")
        return stored, created

    save = create

    def get(self, notice_id: str) -> Notice | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM notices WHERE id = ?", (notice_id,)).fetchone()
        return self._from_row(row) if row else None

    def list_for_date(self, day: date, *, tzinfo) -> list[Notice]:
        start, end = _day_bounds(day, tzinfo)
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM notices
                WHERE (published_at >= ? AND published_at < ?)
                   OR (deadline >= ? AND deadline < ?)
                ORDER BY COALESCE(deadline, published_at), id
                """,
                (_iso(start), _iso(end), _iso(start), _iso(end)),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_all(self) -> list[Notice]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM notices ORDER BY created_at, id").fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Notice:
        return Notice(
            id=row["id"], title=row["title"], raw_text=row["raw_text"],
            audience=json.loads(row["audience_json"]), published_at=row["published_at"],
            deadline=row["deadline"], actions=json.loads(row["actions_json"]),
            priority=row["priority"], source_type=row["source_type"],
            source_ref=row["source_ref"], confidence=row["confidence"],
            needs_confirmation=bool(row["needs_confirmation"]), created_at=row["created_at"],
        )


class CourseRepository:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def save(self, course: Course) -> Course:
        values = course.model_dump(mode="json")
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO courses
                    (id, student_id, name, teacher, weekday, start_time, end_time,
                     location, start_week, end_week, week_pattern, custom_weeks_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    student_id=excluded.student_id, name=excluded.name,
                    teacher=excluded.teacher, weekday=excluded.weekday,
                    start_time=excluded.start_time, end_time=excluded.end_time,
                    location=excluded.location, start_week=excluded.start_week,
                    end_week=excluded.end_week, week_pattern=excluded.week_pattern,
                    custom_weeks_json=excluded.custom_weeks_json
                """,
                (
                    values["id"], values["student_id"], values["name"], values["teacher"],
                    values["weekday"], values["start_time"], values["end_time"],
                    values["location"], values["start_week"], values["end_week"],
                    values["week_pattern"], _json(values["custom_weeks"]),
                ),
            )
            connection.commit()
        return course

    def get(self, course_id: str) -> Course | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
        return self._from_row(row) if row else None

    def list_for_student(self, student_id: str) -> list[Course]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM courses WHERE student_id = ? ORDER BY weekday, start_time, id",
                (student_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_for_student_on_date(
        self, student_id: str, day: date, *, term_start: date
    ) -> list[Course]:
        """Return courses for a date; term_start must be the Monday of week 1."""
        if term_start.isoweekday() != 1:
            raise ValueError("term_start must be the Monday of academic week 1")
        week_number = ((day - term_start).days // 7) + 1
        if week_number < 1:
            return []
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM courses
                WHERE student_id = ? AND weekday = ?
                  AND start_week <= ? AND end_week >= ?
                ORDER BY start_time, id
                """,
                (student_id, day.isoweekday(), week_number, week_number),
            ).fetchall()
        courses = [self._from_row(row) for row in rows]
        return [course for course in courses if self._occurs_in_week(course, week_number)]

    @staticmethod
    def _occurs_in_week(course: Course, week_number: int) -> bool:
        if course.week_pattern == "all":
            return True
        if course.week_pattern == "odd":
            return week_number % 2 == 1
        if course.week_pattern == "even":
            return week_number % 2 == 0
        return week_number in course.custom_weeks

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Course:
        return Course(
            id=row["id"], student_id=row["student_id"], name=row["name"],
            teacher=row["teacher"], weekday=row["weekday"], start_time=row["start_time"],
            end_time=row["end_time"], location=row["location"], start_week=row["start_week"],
            end_week=row["end_week"], week_pattern=row["week_pattern"],
            custom_weeks=json.loads(row["custom_weeks_json"]),
        )


class TaskRepository:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def create(self, task: Task) -> tuple[Task, bool]:
        values = task.model_dump(mode="json")
        with self.database.connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO tasks
                        (id, student_id, title, description, task_type, priority, status,
                         due_at, source_notice_id, dedupe_key, created_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        values["id"], values["student_id"], values["title"],
                        values["description"], values["task_type"], values["priority"],
                        values["status"], values["due_at"], values["source_notice_id"],
                        values["dedupe_key"], values["created_at"], values["completed_at"],
                    ),
                )
                connection.commit()
                return task, True
            except sqlite3.IntegrityError as exc:
                if "dedupe_key" not in str(exc):
                    raise
        duplicate = self.get_by_dedupe_key(task.dedupe_key)
        if duplicate is None:  # pragma: no cover - defensive database failure guard
            raise RuntimeError("duplicate task could not be loaded")
        return duplicate, False

    def get(self, task_id: str, *, student_id: str | None = None) -> Task | None:
        query = "SELECT * FROM tasks WHERE id = ?"
        params: tuple[Any, ...] = (task_id,)
        if student_id is not None:
            query += " AND student_id = ?"
            params += (student_id,)
        with self.database.connect() as connection:
            row = connection.execute(query, params).fetchone()
        return self._from_row(row) if row else None

    def get_by_dedupe_key(self, dedupe_key: str) -> Task | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE dedupe_key = ?", (dedupe_key,)
            ).fetchone()
        return self._from_row(row) if row else None

    def list_for_student(
        self, student_id: str, *, status: TaskStatus | str | None = None
    ) -> list[Task]:
        query = "SELECT * FROM tasks WHERE student_id = ?"
        params: tuple[Any, ...] = (student_id,)
        if status is not None:
            query += " AND status = ?"
            params += (str(status),)
        query += " ORDER BY due_at IS NULL, due_at, created_at, id"
        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._from_row(row) for row in rows]

    def list_for_student_on_date(self, student_id: str, day: date, *, tzinfo) -> list[Task]:
        start, end = _day_bounds(day, tzinfo)
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM tasks
                WHERE student_id = ? AND due_at >= ? AND due_at < ?
                ORDER BY due_at, id
                """,
                (student_id, _iso(start), _iso(end)),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def complete(self, student_id: str, task_id: str, *, completed_at: datetime) -> Task | None:
        _ = Task.model_fields["completed_at"]  # keeps validation source explicit
        if completed_at.tzinfo is None or completed_at.utcoffset() is None:
            raise ValueError("completed_at must include a timezone offset")
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE tasks SET status = 'completed', completed_at = ?
                WHERE id = ? AND student_id = ?
                """,
                (_iso(completed_at), task_id, student_id),
            )
            connection.commit()
        return self.get(task_id, student_id=student_id)

    def restore(self, student_id: str, task_id: str) -> Task | None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE tasks SET status = 'pending', completed_at = NULL
                WHERE id = ? AND student_id = ?
                """,
                (task_id, student_id),
            )
            connection.commit()
        return self.get(task_id, student_id=student_id)

    def set_status(self, student_id: str, task_id: str, status: TaskStatus | str) -> Task | None:
        status_value = TaskStatus(status)
        if status_value == TaskStatus.COMPLETED:
            raise ValueError("use complete() so completed_at is recorded")
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE tasks SET status = ?, completed_at = NULL
                WHERE id = ? AND student_id = ?
                """,
                (status_value.value, task_id, student_id),
            )
            connection.commit()
        return self.get(task_id, student_id=student_id)

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Task:
        return Task(
            id=row["id"], student_id=row["student_id"], title=row["title"],
            description=row["description"], task_type=row["task_type"],
            priority=row["priority"], status=row["status"], due_at=row["due_at"],
            source_notice_id=row["source_notice_id"], dedupe_key=row["dedupe_key"],
            created_at=row["created_at"], completed_at=row["completed_at"],
        )


class ReminderRepository:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def save(self, reminder: Reminder) -> Reminder:
        values = reminder.model_dump(mode="json")
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO reminders
                    (id, task_id, trigger_at, channel, status, sent_at, failure_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    task_id=excluded.task_id, trigger_at=excluded.trigger_at,
                    channel=excluded.channel, status=excluded.status,
                    sent_at=excluded.sent_at, failure_reason=excluded.failure_reason
                """,
                (
                    values["id"], values["task_id"], values["trigger_at"],
                    values["channel"], values["status"], values["sent_at"],
                    values["failure_reason"],
                ),
            )
            connection.commit()
        return reminder

    def get(self, reminder_id: str) -> Reminder | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
            ).fetchone()
        return self._from_row(row) if row else None

    def list_for_task(self, task_id: str) -> list[Reminder]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM reminders WHERE task_id = ? ORDER BY trigger_at, id",
                (task_id,),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_in_range(
        self,
        start: datetime,
        end: datetime,
        *,
        status: str | None = None,
        student_id: str | None = None,
    ) -> list[Reminder]:
        if any(value.tzinfo is None or value.utcoffset() is None for value in (start, end)):
            raise ValueError("range datetimes must include timezone offsets")
        if end <= start:
            raise ValueError("end must be after start")
        query = (
            "SELECT r.* FROM reminders r "
            "JOIN tasks t ON t.id = r.task_id "
            "WHERE r.trigger_at >= ? AND r.trigger_at < ?"
        )
        params: list[Any] = [_iso(start), _iso(end)]
        if status is not None:
            query += " AND r.status = ?"
            params.append(status)
        if student_id is not None:
            query += " AND t.student_id = ?"
            params.append(student_id)
        query += " ORDER BY r.trigger_at, r.id"
        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._from_row(row) for row in rows]

    def list_due(self, at: datetime, *, student_id: str | None = None) -> list[Reminder]:
        if at.tzinfo is None or at.utcoffset() is None:
            raise ValueError("at must include a timezone offset")
        query = (
            "SELECT r.* FROM reminders r JOIN tasks t ON t.id = r.task_id "
            "WHERE r.status = 'pending' AND r.trigger_at <= ? AND t.status = 'pending'"
        )
        params: list[Any] = [_iso(at)]
        if student_id is not None:
            query += " AND t.student_id = ?"
            params.append(student_id)
        query += " ORDER BY r.trigger_at, r.id"
        with self.database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Reminder:
        return Reminder(
            id=row["id"], task_id=row["task_id"], trigger_at=row["trigger_at"],
            channel=row["channel"], status=row["status"], sent_at=row["sent_at"],
            failure_reason=row["failure_reason"],
        )
