from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from campusmind.services.task.models import ContractModel, Task, require_aware


class Notice(ContractModel):
    id: str
    title: str
    raw_text: str
    audience: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    deadline: datetime | None = None
    actions: list[str] = Field(default_factory=list)
    priority: Literal["critical", "high", "medium", "normal"] = "normal"
    source_type: Literal["demo", "document", "url", "user_input"] = "user_input"
    source_ref: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    needs_confirmation: bool
    created_at: datetime

    _aware_published = field_validator("published_at") (require_aware)
    _aware_deadline = field_validator("deadline") (require_aware)
    _aware_created = field_validator("created_at") (require_aware)


class NoticeCandidate(ContractModel):
    title: str | None = None
    audience: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    deadline: datetime | None = None
    actions: list[str] = Field(default_factory=list)
    priority: Literal["critical", "high", "medium", "normal"] | None = None
    source_type: Literal["demo", "document", "url", "user_input"] = "user_input"
    source_ref: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    _aware_published = field_validator("published_at") (require_aware)
    _aware_deadline = field_validator("deadline") (require_aware)


class NoticeParseCommand(ContractModel):
    text: str
    student_id: str
    reference_time: datetime
    candidate: NoticeCandidate = Field(default_factory=NoticeCandidate)
    student_segments: list[str] = Field(default_factory=list)

    _aware_reference = field_validator("reference_time") (require_aware)


class NoticeParseResult(ContractModel):
    notice: Notice
    tasks: list[Task]
    duplicate: bool
    expired: bool
    applicable: bool
