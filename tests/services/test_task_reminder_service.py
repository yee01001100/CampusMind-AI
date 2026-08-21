from __future__ import annotations

from datetime import timedelta

import pytest

from campusmind.services.reminder import ReminderService
from campusmind.services.task import TaskCreate, TaskPatch, TaskService
from campusmind.services.task.models import TaskListQuery

from .conftest import NOW


def create_task(service: TaskService, *, key: str, due=NOW + timedelta(days=10), task_type="general"):
    return service.create(
        TaskCreate(
            student_id="student-demo-001",
            title=f"任务 {key}",
            task_type=task_type,
            due_at=due,
            source_notice_id="notice-demo",
            dedupe_key=key,
        ),
        now=NOW,
    )


@pytest.mark.parametrize("key", ["dup-a", "dup-b", "dup-c", "dup-d", "dup-e"])
def test_five_duplicate_task_groups(task_service, key) -> None:
    first = create_task(task_service, key=key)
    second = create_task(task_service, key=key)
    assert first.created is True
    assert second.created is False
    assert second.duplicate_of == first.task.id


@pytest.mark.parametrize(
    "delta,expected",
    [
        (timedelta(hours=-1), "critical"),
        (timedelta(hours=20), "high"),
        (timedelta(days=2), "medium"),
        (timedelta(days=5), "normal"),
        (None, "normal"),
    ],
)
def test_priority_boundaries(task_service, delta, expected) -> None:
    due = None if delta is None else NOW + delta
    assert task_service.priority_for(due, NOW) == expected


def test_query_filter_sort_complete_restore_cancel_and_source(task_service) -> None:
    old = create_task(task_service, key="old", due=NOW - timedelta(hours=1)).task
    future = create_task(task_service, key="future", due=NOW + timedelta(hours=2)).task
    completed = task_service.complete(future.id, now=NOW)
    assert completed.completed_at == NOW
    restored = task_service.restore(future.id, now=NOW + timedelta(minutes=1))
    assert restored.status == "pending" and restored.completed_at is None
    cancelled = task_service.cancel(future.id, now=NOW + timedelta(minutes=2))
    assert cancelled.status == "cancelled"
    overdue = task_service.list(
        TaskListQuery(student_id="student-demo-001", overdue=True), now=NOW
    )
    assert [task.id for task in overdue] == [old.id]
    assert old.source_notice_id == "notice-demo"


@pytest.mark.parametrize(
    "task_type,expected",
    [("registration", 4), ("exam", 3), ("assignment", 3), ("course", 1), ("activity", 2)],
)
def test_default_reminder_rules(repository, task_type, expected) -> None:
    task = create_task(
        TaskService(repository), key=f"rule-{task_type}", due=NOW + timedelta(days=10), task_type=task_type
    ).task
    assert len(ReminderService(repository).schedule(task, now=NOW)) == expected


def test_quiet_hours_duplicate_recovery_failure_retry_and_completion(repository) -> None:
    tasks = TaskService(repository)
    reminders = ReminderService(repository)
    task = create_task(
        tasks,
        key="quiet",
        due=NOW + timedelta(days=1, hours=1),
        task_type="activity",
    ).task
    scheduled = reminders.schedule(task, now=NOW)
    assert scheduled
    assert all(item.trigger_at.hour != 23 for item in scheduled)
    assert reminders.schedule(task, now=NOW) == []
    assert reminders.recover_pending(at=NOW)

    failed = reminders.mark_failed(scheduled[0].id, reason="demo transport failure")
    assert failed.status == "failed" and failed.failure_reason == "demo transport failure"
    retried = reminders.retry_failed(failed.id, retry_at=NOW + timedelta(minutes=5))
    assert retried.status == "pending" and retried.failure_reason is None

    completed = tasks.update(task.id, TaskPatch(status="completed"), now=NOW)
    assert completed.status == "completed"
    assert reminders.due(student_id=task.student_id, at=task.due_at) == []
    assert all(item.status == "skipped" for item in repository.list_reminders())
