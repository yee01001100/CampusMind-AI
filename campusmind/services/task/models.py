"""Shared task-facing contracts owned by Agent 3.

Agent 2 can replace the repository implementation without changing these
service inputs or outputs.  They intentionally mirror SHARED_CONTRACT.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Priority = Literal["critical", "high", "medium", "normal"]
TaskStatus = Literal["pending", "completed", "cancelled"]
TaskType = Literal[
    "registration", "exam", "assignment", "course", "activity", "general"
]


def require_aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("datetime must include a timezone offset")
    return value


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ServiceError(Exception):
    """Stable business error consumed by the API adapter."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code


class Task(ContractModel):
    id: str
    student_id: str
    title: str
    description: str | None = None
    task_type: TaskType = "general"
    priority: Priority = "normal"
    status: TaskStatus = "pending"
    due_at: datetime | None = None
    source_notice_id: str | None = None
    dedupe_key: str
    created_at: datetime
    completed_at: datetime | None = None

    _aware_due = field_validator("due_at") (require_aware)
    _aware_created = field_validator("created_at") (require_aware)
    _aware_completed = field_validator("completed_at") (require_aware)

    @model_validator(mode="after")
    def completion_is_consistent(self) -> "Task":
        if self.status == "completed" and self.completed_at is None:
            raise ValueError("completed task requires completed_at")
        if self.status != "completed" and self.completed_at is not None:
            raise ValueError("only completed tasks may have completed_at")
        return self


class TaskCreate(ContractModel):
    student_id: str
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    task_type: TaskType = "general"
    priority: Priority | None = None
    due_at: datetime | None = None
    source_notice_id: str | None = None
    dedupe_key: str = Field(min_length=1, max_length=300)

    _aware_due = field_validator("due_at") (require_aware)


class TaskPatch(ContractModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    priority: Priority | None = None
    status: TaskStatus | None = None
    due_at: datetime | None = None

    _aware_due = field_validator("due_at") (require_aware)


class TaskCreateResult(ContractModel):
    task: Task
    created: bool
    duplicate_of: str | None


class TaskListQuery(ContractModel):
    student_id: str
    status: TaskStatus | None = None
    task_type: TaskType | None = None
    overdue: bool | None = None
    sort: Literal["due_at", "priority", "created_at"] = "due_at"
