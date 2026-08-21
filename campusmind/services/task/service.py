"""Task lifecycle rules."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4

from .models import (
    ServiceError,
    Task,
    TaskCreate,
    TaskCreateResult,
    TaskListQuery,
    TaskPatch,
)


class TaskRepository(Protocol):
    def get_task(self, task_id: str) -> Task | None: ...
    def get_task_by_dedupe(self, dedupe_key: str) -> Task | None: ...
    def list_tasks(self, student_id: str) -> list[Task]: ...
    def save_task(self, task: Task) -> Task: ...


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    @staticmethod
    def priority_for(due_at: datetime | None, now: datetime) -> str:
        if due_at is None:
            return "normal"
        delta = due_at - now
        if delta <= timedelta(0):
            return "critical"
        if delta <= timedelta(hours=24):
            return "high"
        if delta <= timedelta(days=3):
            return "medium"
        return "normal"

    def create(self, data: TaskCreate, *, now: datetime) -> TaskCreateResult:
        existing = self.repository.get_task_by_dedupe(data.dedupe_key)
        if existing is not None:
            if existing.student_id != data.student_id:
                raise ServiceError(
                    "TASK_DUPLICATE",
                    "任务去重键已被占用",
                    details={"duplicate_of": existing.id},
                    status_code=409,
                )
            return TaskCreateResult(
                task=existing, created=False, duplicate_of=existing.id
            )
        task = Task(
            id=f"task-{uuid4().hex}",
            student_id=data.student_id,
            title=data.title.strip(),
            description=data.description,
            task_type=data.task_type,
            priority=data.priority or self.priority_for(data.due_at, now),
            status="pending",
            due_at=data.due_at,
            source_notice_id=data.source_notice_id,
            dedupe_key=data.dedupe_key,
            created_at=now,
            completed_at=None,
        )
        return TaskCreateResult(
            task=self.repository.save_task(task), created=True, duplicate_of=None
        )

    def get(self, task_id: str, *, student_id: str | None = None) -> Task:
        task = self.repository.get_task(task_id)
        if task is None or (student_id is not None and task.student_id != student_id):
            raise ServiceError(
                "TASK_NOT_FOUND", "任务不存在", details={"task_id": task_id}, status_code=404
            )
        return task

    @staticmethod
    def is_overdue(task: Task, *, now: datetime) -> bool:
        return bool(
            task.due_at is not None
            and task.due_at < now
            and task.status == "pending"
        )

    def list(self, query: TaskListQuery, *, now: datetime) -> list[Task]:
        tasks = self.repository.list_tasks(query.student_id)
        if query.status is not None:
            tasks = [task for task in tasks if task.status == query.status]
        if query.task_type is not None:
            tasks = [task for task in tasks if task.task_type == query.task_type]

        if query.overdue is not None:
            tasks = [
                task
                for task in tasks
                if self.is_overdue(task, now=now) is query.overdue
            ]

        priority_rank = {"critical": 0, "high": 1, "medium": 2, "normal": 3}
        if query.sort == "priority":
            return sorted(tasks, key=lambda task: priority_rank[task.priority])
        if query.sort == "created_at":
            return sorted(tasks, key=lambda task: task.created_at, reverse=True)
        ceiling = datetime.max.replace(tzinfo=now.tzinfo)
        return sorted(tasks, key=lambda task: task.due_at or ceiling)

    def update(
        self, task_id: str, patch: TaskPatch, *, now: datetime, student_id: str | None = None
    ) -> Task:
        current = self.get(task_id, student_id=student_id)
        changes = patch.model_dump(exclude_unset=True)
        status = changes.get("status", current.status)
        if status == "completed":
            changes["completed_at"] = current.completed_at or now
        else:
            changes["completed_at"] = None
        if "due_at" in changes and "priority" not in changes:
            changes["priority"] = self.priority_for(changes["due_at"], now)
        updated = current.model_copy(update=changes)
        return self.repository.save_task(Task.model_validate(updated.model_dump()))

    def complete(self, task_id: str, *, now: datetime, student_id: str | None = None) -> Task:
        return self.update(task_id, TaskPatch(status="completed"), now=now, student_id=student_id)

    def restore(self, task_id: str, *, now: datetime, student_id: str | None = None) -> Task:
        return self.update(task_id, TaskPatch(status="pending"), now=now, student_id=student_id)

    def cancel(self, task_id: str, *, now: datetime, student_id: str | None = None) -> Task:
        return self.update(task_id, TaskPatch(status="cancelled"), now=now, student_id=student_id)
