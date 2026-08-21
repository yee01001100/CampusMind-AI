"""Stable errors shared by the CampusMind tool boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


STABLE_ERROR_CODES = frozenset(
    {
        "VALIDATION_ERROR",
        "STUDENT_NOT_FOUND",
        "NOTICE_EMPTY",
        "NOTICE_DATE_AMBIGUOUS",
        "NOTICE_NOT_APPLICABLE",
        "TASK_DUPLICATE",
        "TASK_NOT_FOUND",
        "COURSE_NOT_FOUND",
        "RAG_NO_SOURCE",
        "AGENT_TOOL_FAILED",
        "MODEL_UNAVAILABLE",
        "INTERNAL_ERROR",
    }
)


@dataclass(slots=True)
class ToolServiceError(Exception):
    """An expected service failure that is safe to expose at the tool boundary."""

    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)


@dataclass(slots=True)
class ToolValidationError(Exception):
    """Invalid tool arguments or an incompatible service result."""

    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)
