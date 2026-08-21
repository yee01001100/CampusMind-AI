"""Repeatable loader for the explicitly simulated CampusMind demo dataset."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from campusmind.domain import Course, Notice, Reminder, StudentProfile, Task
from campusmind.repositories.sqlite import (
    CourseRepository,
    NoticeRepository,
    ReminderRepository,
    StudentProfileRepository,
    TaskRepository,
)

from .database import SQLiteDatabase


@dataclass(frozen=True)
class DemoLoadResult:
    profiles: int
    courses: int
    notices: int
    notices_created: int
    tasks: int
    tasks_created: int
    reminders: int


def _read_json(directory: Path, name: str):
    return json.loads((directory / name).read_text(encoding="utf-8"))


def load_demo_data(database: SQLiteDatabase, directory: str | Path) -> DemoLoadResult:
    """Initialize and upsert the demo dataset in foreign-key-safe order."""
    directory = Path(directory)
    manifest = _read_json(directory, "manifest.json")
    if manifest.get("is_demo") is not True:
        raise ValueError("demo manifest must explicitly set is_demo=true")

    database.initialize()
    profiles = [StudentProfile.model_validate(item) for item in _read_json(directory, "student_profiles.json")]
    courses = [Course.model_validate(item) for item in _read_json(directory, "courses.json")]
    notices = [Notice.model_validate(item) for item in _read_json(directory, "notices.json")]
    tasks = [Task.model_validate(item) for item in _read_json(directory, "tasks.json")]
    reminders = [Reminder.model_validate(item) for item in _read_json(directory, "reminders.json")]

    profile_repo = StudentProfileRepository(database)
    course_repo = CourseRepository(database)
    notice_repo = NoticeRepository(database)
    task_repo = TaskRepository(database)
    reminder_repo = ReminderRepository(database)

    for profile in profiles:
        profile_repo.save(profile)
    for course in courses:
        course_repo.save(course)
    notices_created = sum(notice_repo.create(notice)[1] for notice in notices)
    tasks_created = sum(task_repo.create(task)[1] for task in tasks)
    for reminder in reminders:
        reminder_repo.save(reminder)

    return DemoLoadResult(
        profiles=len(profiles), courses=len(courses), notices=len(notices),
        notices_created=notices_created, tasks=len(tasks), tasks_created=tasks_created,
        reminders=len(reminders),
    )
