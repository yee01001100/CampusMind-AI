from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from campusmind.services.task.models import ContractModel, require_aware


class StudentProfile(ContractModel):
    id: str
    name: str
    major: str | None = None
    grade: str | None = None
    timezone: str = "Asia/Shanghai"
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    interests: list[str] = Field(default_factory=list)
    reminder_preferences: dict[str, Any] = Field(default_factory=dict)

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def validate_optional_clock(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                datetime.strptime(value, "%H:%M")
            except ValueError as exc:
                raise ValueError("quiet hours must use HH:mm") from exc
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("unknown IANA timezone") from exc
        return value


class Reminder(ContractModel):
    id: str
    task_id: str
    trigger_at: datetime
    channel: Literal["in_app"] = "in_app"
    status: Literal["pending", "sent", "skipped", "failed"] = "pending"
    sent_at: datetime | None = None
    failure_reason: str | None = None
    _aware_trigger = field_validator("trigger_at") (require_aware)
    _aware_sent = field_validator("sent_at") (require_aware)

    @model_validator(mode="after")
    def validate_status_fields(self) -> "Reminder":
        if self.status == "sent" and self.sent_at is None:
            raise ValueError("sent reminder requires sent_at")
        if self.status != "sent" and self.sent_at is not None:
            raise ValueError("only sent reminders may have sent_at")
        if self.status == "failed" and not self.failure_reason:
            raise ValueError("failed reminder requires failure_reason")
        return self
