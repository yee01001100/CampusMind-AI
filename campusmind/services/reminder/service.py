from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Protocol
from uuid import uuid4
from zoneinfo import ZoneInfo

from campusmind.services.task.models import ServiceError, Task

from .models import Reminder, StudentProfile


class ReminderRepository(Protocol):
    def get_task(self, task_id: str) -> Task | None: ...
    def get_profile(self, student_id: str) -> StudentProfile | None: ...
    def list_reminders(self) -> list[Reminder]: ...
    def save_reminder(self, reminder: Reminder) -> Reminder: ...


OFFSETS = {
    "registration": [timedelta(days=7), timedelta(days=3), timedelta(days=1), timedelta(hours=3)],
    "exam": [timedelta(days=7), timedelta(days=3), timedelta(days=1)],
    "assignment": [timedelta(days=3), timedelta(days=1), timedelta(hours=3)],
    "course": [timedelta(minutes=30)],
    "activity": [timedelta(days=1), timedelta(hours=2)],
    "general": [timedelta(days=1), timedelta(hours=2)],
}


class ReminderService:
    def __init__(self, repository: ReminderRepository) -> None:
        self.repository = repository

    @staticmethod
    def _parse_clock(value: str) -> time:
        return datetime.strptime(value, "%H:%M").time()

    def move_out_of_quiet_hours(
        self, trigger_at: datetime, profile: StudentProfile | None
    ) -> datetime:
        if not profile or not profile.quiet_hours_start or not profile.quiet_hours_end:
            return trigger_at
        zone = ZoneInfo(profile.timezone)
        local = trigger_at.astimezone(zone)
        start = self._parse_clock(profile.quiet_hours_start)
        end = self._parse_clock(profile.quiet_hours_end)
        clock = local.time().replace(tzinfo=None)
        crosses_midnight = start > end
        in_quiet = (clock >= start or clock < end) if crosses_midnight else start <= clock < end
        if not in_quiet:
            return trigger_at
        end_day = local.date()
        if crosses_midnight and clock >= start:
            end_day += timedelta(days=1)
        return datetime.combine(end_day, end, tzinfo=zone)

    def schedule(self, task: Task, *, now: datetime) -> list[Reminder]:
        if task.status != "pending" or task.due_at is None:
            return []
        profile = self.repository.get_profile(task.student_id)
        existing_by_key = {
            (reminder.task_id, reminder.trigger_at): reminder
            for reminder in self.repository.list_reminders()
        }
        created: list[Reminder] = []
        for offset in OFFSETS[task.task_type]:
            trigger = self.move_out_of_quiet_hours(task.due_at - offset, profile)
            if trigger <= now or trigger >= task.due_at:
                continue
            existing = existing_by_key.get((task.id, trigger))
            if existing is not None:
                if existing.status == "skipped":
                    restored = existing.model_copy(
                        update={"status": "pending", "sent_at": None, "failure_reason": None}
                    )
                    created.append(self.repository.save_reminder(restored))
                continue
            reminder = Reminder(
                id=f"reminder-{uuid4().hex}",
                task_id=task.id,
                trigger_at=trigger,
            )
            created.append(self.repository.save_reminder(reminder))
            existing_by_key[(task.id, trigger)] = reminder
        return created

    def due(self, *, student_id: str, at: datetime) -> list[Reminder]:
        due: list[Reminder] = []
        for reminder in self.repository.list_reminders():
            task = self.repository.get_task(reminder.task_id)
            if task is None or task.student_id != student_id:
                continue
            if task.status != "pending":
                if reminder.status == "pending":
                    self.repository.save_reminder(
                        reminder.model_copy(update={"status": "skipped"})
                    )
                continue
            if reminder.status == "pending" and reminder.trigger_at <= at:
                due.append(reminder)
        return sorted(due, key=lambda reminder: reminder.trigger_at)

    def cancel_for_task(self, task_id: str) -> int:
        count = 0
        for reminder in self.repository.list_reminders():
            if reminder.task_id == task_id and reminder.status == "pending":
                self.repository.save_reminder(reminder.model_copy(update={"status": "skipped"}))
                count += 1
        return count

    def mark_sent(self, reminder_id: str, *, sent_at: datetime) -> Reminder:
        reminder = self._get(reminder_id)
        return self.repository.save_reminder(
            reminder.model_copy(
                update={"status": "sent", "sent_at": sent_at, "failure_reason": None}
            )
        )

    def mark_failed(self, reminder_id: str, *, reason: str) -> Reminder:
        reminder = self._get(reminder_id)
        return self.repository.save_reminder(
            reminder.model_copy(
                update={
                    "status": "failed",
                    "failure_reason": reason[:300],
                }
            )
        )

    def retry_failed(self, reminder_id: str, *, retry_at: datetime) -> Reminder:
        reminder = self._get(reminder_id)
        if reminder.status != "failed":
            raise ServiceError("VALIDATION_ERROR", "只有失败提醒可以重试")
        return self.repository.save_reminder(
            reminder.model_copy(
                update={"status": "pending", "trigger_at": retry_at, "failure_reason": None}
            )
        )

    def recover_pending(self, *, at: datetime) -> list[Reminder]:
        """Return persisted pending jobs that a restarted scheduler must requeue."""
        return sorted(
            [
                reminder
                for reminder in self.repository.list_reminders()
                if reminder.status == "pending" and reminder.trigger_at > at
            ],
            key=lambda reminder: reminder.trigger_at,
        )

    def _get(self, reminder_id: str) -> Reminder:
        reminder = next(
            (item for item in self.repository.list_reminders() if item.id == reminder_id),
            None,
        )
        if reminder is None:
            raise ServiceError("VALIDATION_ERROR", "提醒不存在", status_code=404)
        return reminder
