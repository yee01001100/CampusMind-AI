"""Pydantic implementations of the five Shared Contract models."""

from __future__ import annotations

from datetime import datetime, time
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class NoticePriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    NORMAL = "normal"


class NoticeSourceType(StrEnum):
    DEMO = "demo"
    DOCUMENT = "document"
    URL = "url"
    USER_INPUT = "user_input"


class WeekPattern(StrEnum):
    ALL = "all"
    ODD = "odd"
    EVEN = "even"
    CUSTOM = "custom"


class TaskType(StrEnum):
    REGISTRATION = "registration"
    EXAM = "exam"
    ASSIGNMENT = "assignment"
    COURSE = "course"
    ACTIVITY = "activity"
    GENERAL = "general"


class TaskStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReminderChannel(StrEnum):
    IN_APP = "in_app"


class ReminderStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


def _require_aware(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("datetime must include a timezone offset")
    return value


def _validate_hhmm(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("time must use HH:mm") from exc
    if parsed.second or parsed.microsecond or len(value) != 5:
        raise ValueError("time must use HH:mm")
    return value


class Notice(_ContractModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)
    audience: list[str]
    published_at: datetime | None = None
    deadline: datetime | None = None
    actions: list[str]
    priority: NoticePriority
    source_type: NoticeSourceType
    source_ref: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    needs_confirmation: bool
    created_at: datetime

    _aware_published_at = field_validator("published_at")(_require_aware)
    _aware_deadline = field_validator("deadline")(_require_aware)
    _aware_created_at = field_validator("created_at")(_require_aware)

    @field_validator("audience", "actions")
    @classmethod
    def non_blank_items(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("list items must not be blank")
        return value

    @model_validator(mode="after")
    def low_confidence_requires_confirmation(self) -> "Notice":
        if self.confidence < 0.75 and not self.needs_confirmation:
            raise ValueError("confidence below 0.75 requires confirmation")
        return self


class Course(_ContractModel):
    id: str = Field(min_length=1)
    student_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    teacher: str | None = None
    weekday: int = Field(ge=1, le=7)
    start_time: str
    end_time: str
    location: str | None = None
    start_week: int = Field(ge=1)
    end_week: int = Field(ge=1)
    week_pattern: WeekPattern
    custom_weeks: list[int] = Field(default_factory=list)

    _valid_start_time = field_validator("start_time")(_validate_hhmm)
    _valid_end_time = field_validator("end_time")(_validate_hhmm)

    @model_validator(mode="after")
    def valid_schedule(self) -> "Course":
        if self.end_week < self.start_week:
            raise ValueError("end_week must be greater than or equal to start_week")
        if self.start_time >= self.end_time:
            raise ValueError("end_time must be after start_time")
        if len(set(self.custom_weeks)) != len(self.custom_weeks):
            raise ValueError("custom_weeks must not contain duplicates")
        if any(week < self.start_week or week > self.end_week for week in self.custom_weeks):
            raise ValueError("custom_weeks must be within start_week and end_week")
        if self.week_pattern == WeekPattern.CUSTOM and not self.custom_weeks:
            raise ValueError("custom week_pattern requires custom_weeks")
        if self.week_pattern != WeekPattern.CUSTOM and self.custom_weeks:
            raise ValueError("custom_weeks is only valid for custom week_pattern")
        return self


class Task(_ContractModel):
    id: str = Field(min_length=1)
    student_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    task_type: TaskType
    priority: NoticePriority
    status: TaskStatus
    due_at: datetime | None = None
    source_notice_id: str | None = None
    dedupe_key: str = Field(min_length=1)
    created_at: datetime
    completed_at: datetime | None = None

    _aware_due_at = field_validator("due_at")(_require_aware)
    _aware_created_at = field_validator("created_at")(_require_aware)
    _aware_completed_at = field_validator("completed_at")(_require_aware)

    @model_validator(mode="after")
    def completed_timestamp_matches_status(self) -> "Task":
        if self.status == TaskStatus.COMPLETED and self.completed_at is None:
            raise ValueError("completed tasks require completed_at")
        if self.status != TaskStatus.COMPLETED and self.completed_at is not None:
            raise ValueError("only completed tasks may have completed_at")
        return self


class StudentProfile(_ContractModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    major: str | None = None
    grade: str | None = None
    timezone: str = "Asia/Shanghai"
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    interests: list[str] = Field(default_factory=list)
    reminder_preferences: dict[str, Any] = Field(default_factory=dict)

    _valid_quiet_start = field_validator("quiet_hours_start")(_validate_hhmm)
    _valid_quiet_end = field_validator("quiet_hours_end")(_validate_hhmm)

    @field_validator("timezone")
    @classmethod
    def timezone_exists(cls, value: str) -> str:
        # Asia/Shanghai is the frozen project timezone. Accept it even on
        # minimal Windows Python installs that do not bundle the IANA database.
        if value == "Asia/Shanghai":
            return value
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be an IANA timezone") from exc
        return value

    @model_validator(mode="after")
    def quiet_hours_are_paired(self) -> "StudentProfile":
        if (self.quiet_hours_start is None) != (self.quiet_hours_end is None):
            raise ValueError("quiet hours start and end must be provided together")
        return self


class Reminder(_ContractModel):
    id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    trigger_at: datetime
    channel: ReminderChannel
    status: ReminderStatus
    sent_at: datetime | None = None
    failure_reason: str | None = None

    _aware_trigger_at = field_validator("trigger_at")(_require_aware)
    _aware_sent_at = field_validator("sent_at")(_require_aware)

    @model_validator(mode="after")
    def status_details_are_consistent(self) -> "Reminder":
        if self.status == ReminderStatus.SENT and self.sent_at is None:
            raise ValueError("sent reminders require sent_at")
        if self.status != ReminderStatus.SENT and self.sent_at is not None:
            raise ValueError("only sent reminders may have sent_at")
        if self.status == ReminderStatus.FAILED and not self.failure_reason:
            raise ValueError("failed reminders require failure_reason")
        if self.status != ReminderStatus.FAILED and self.failure_reason is not None:
            raise ValueError("failure_reason is only valid for failed reminders")
        return self
