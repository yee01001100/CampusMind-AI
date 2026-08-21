"""Explicitly bounded preference memory for the Agent runtime."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


ALLOWED_MEMORY_FIELDS = frozenset(
    {
        "major",
        "grade",
        "interests",
        "preferences",
        "reminder_preferences",
        "quiet_hours_start",
        "quiet_hours_end",
    }
)

FORBIDDEN_MEMORY_FIELDS = frozenset(
    {
        "courses",
        "course_schedule",
        "tasks",
        "task_status",
        "deadlines",
        "due_at",
        "school_rules",
        "official_regulations",
    }
)


class MemoryPolicyError(ValueError):
    """Raised when durable memory would become a source of record."""


class PreferenceMemory:
    """Small in-memory store that only accepts stable student preferences."""

    def __init__(self) -> None:
        self._profiles: dict[str, dict[str, Any]] = {}

    def remember(self, student_id: str, values: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(student_id, str) or not student_id.strip():
            raise MemoryPolicyError("student_id must be a non-empty string")
        if not isinstance(values, Mapping):
            raise MemoryPolicyError("memory values must be an object")
        fields = set(values)
        forbidden = fields & FORBIDDEN_MEMORY_FIELDS
        unknown = fields - ALLOWED_MEMORY_FIELDS - FORBIDDEN_MEMORY_FIELDS
        if forbidden or unknown:
            rejected = sorted(forbidden | unknown)
            raise MemoryPolicyError(
                "memory cannot store source-of-truth fields: " + ", ".join(rejected)
            )
        profile = self._profiles.setdefault(student_id.strip(), {})
        profile.update(deepcopy(dict(values)))
        return deepcopy(profile)

    def snapshot(self, student_id: str) -> dict[str, Any]:
        return deepcopy(self._profiles.get(student_id, {}))

    def forget(self, student_id: str) -> None:
        self._profiles.pop(student_id, None)
