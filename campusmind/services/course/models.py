from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from campusmind.services.task.models import ContractModel, require_aware


class Course(ContractModel):
    id: str
    student_id: str
    name: str
    teacher: str | None = None
    weekday: int = Field(ge=1, le=7)
    start_time: str
    end_time: str
    location: str | None = None
    start_week: int = Field(ge=1)
    end_week: int = Field(ge=1)
    week_pattern: Literal["all", "odd", "even", "custom"] = "all"
    custom_weeks: list[int] = Field(default_factory=list)

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_hhmm(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("time must use HH:mm") from exc
        return value

    @model_validator(mode="after")
    def validate_range(self) -> "Course":
        if self.start_time >= self.end_time:
            raise ValueError("course start_time must be before end_time")
        if self.start_week > self.end_week:
            raise ValueError("course start_week must not exceed end_week")
        if self.week_pattern == "custom" and not self.custom_weeks:
            raise ValueError("custom week pattern requires custom_weeks")
        return self


class TimeBlock(ContractModel):
    id: str
    title: str
    kind: Literal["course", "exam", "task"]
    start_at: datetime
    end_at: datetime

    _aware_start = field_validator("start_at") (require_aware)
    _aware_end = field_validator("end_at") (require_aware)

    @model_validator(mode="after")
    def validate_range(self) -> "TimeBlock":
        if self.start_at >= self.end_at:
            raise ValueError("time block start_at must be before end_at")
        return self


class CourseConflict(ContractModel):
    left_id: str
    right_id: str
    overlap_minutes: int


class FreeSlot(ContractModel):
    start_at: datetime
    end_at: datetime
    minutes: int

    _aware_start = field_validator("start_at") (require_aware)
    _aware_end = field_validator("end_at") (require_aware)


class CourseDayResult(ContractModel):
    date: date
    week: int | None
    courses: list[Course]
    next_course: Course | None = None
    free_slots: list[FreeSlot] = Field(default_factory=list)
