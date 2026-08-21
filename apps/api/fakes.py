"""Replaceable in-memory repository used before Agent 2 integration.

This is deliberately an adapter, not a second domain/storage implementation.
It implements the narrow repository methods required by Agent 3 services.
"""

from __future__ import annotations

from campusmind.services.course import Course
from campusmind.services.notice import Notice
from campusmind.services.reminder import Reminder, StudentProfile
from campusmind.services.task import Task


class InMemoryRepository:
    def __init__(self) -> None:
        self.tasks: dict[str, Task] = {}
        self.courses: dict[str, Course] = {}
        self.reminders: dict[str, Reminder] = {}
        self.notices: dict[str, Notice] = {}
        self.notice_sources: dict[str, str] = {}
        self.profiles: dict[str, StudentProfile] = {}

    def reset(self) -> None:
        self.__init__()

    def get_task(self, task_id: str) -> Task | None:
        task = self.tasks.get(task_id)
        return task.model_copy(deep=True) if task else None

    def get_task_by_dedupe(self, dedupe_key: str) -> Task | None:
        task = next(
            (item for item in self.tasks.values() if item.dedupe_key == dedupe_key),
            None,
        )
        return task.model_copy(deep=True) if task else None

    def list_tasks(self, student_id: str) -> list[Task]:
        return [
            task.model_copy(deep=True)
            for task in self.tasks.values()
            if task.student_id == student_id
        ]

    def save_task(self, task: Task) -> Task:
        stored = Task.model_validate(task.model_dump())
        self.tasks[task.id] = stored
        return stored.model_copy(deep=True)

    def list_courses(self, student_id: str) -> list[Course]:
        return [
            course.model_copy(deep=True)
            for course in self.courses.values()
            if course.student_id == student_id
        ]

    def save_course(self, course: Course) -> Course:
        stored = Course.model_validate(course.model_dump())
        self.courses[course.id] = stored
        return stored.model_copy(deep=True)

    def get_notice_by_source(self, source_key: str) -> Notice | None:
        notice_id = self.notice_sources.get(source_key)
        notice = self.notices.get(notice_id) if notice_id else None
        return notice.model_copy(deep=True) if notice else None

    def save_notice(self, source_key: str, notice: Notice) -> Notice:
        stored = Notice.model_validate(notice.model_dump())
        self.notices[notice.id] = stored
        self.notice_sources[source_key] = notice.id
        return stored.model_copy(deep=True)

    def list_notices(self) -> list[Notice]:
        return [notice.model_copy(deep=True) for notice in self.notices.values()]

    def list_tasks_for_notice(self, notice_id: str) -> list[Task]:
        return [
            task.model_copy(deep=True)
            for task in self.tasks.values()
            if task.source_notice_id == notice_id
        ]

    def get_profile(self, student_id: str) -> StudentProfile | None:
        profile = self.profiles.get(student_id)
        return profile.model_copy(deep=True) if profile else None

    def save_profile(self, profile: StudentProfile) -> StudentProfile:
        stored = StudentProfile.model_validate(profile.model_dump())
        self.profiles[profile.id] = stored
        return stored.model_copy(deep=True)

    def list_reminders(self) -> list[Reminder]:
        return [reminder.model_copy(deep=True) for reminder in self.reminders.values()]

    def save_reminder(self, reminder: Reminder) -> Reminder:
        stored = Reminder.model_validate(reminder.model_dump())
        self.reminders[reminder.id] = stored
        return stored.model_copy(deep=True)
