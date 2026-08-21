"""Validated asynchronous adapters for the five shared CampusMind tools."""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any, Mapping, Protocol

from .errors import STABLE_ERROR_CODES, ToolServiceError, ToolValidationError
from .models import ToolDefinition, ToolResult


class CampusService(Protocol):
    async def get_today_brief(
        self, *, student_id: str, date: str, timezone: str
    ) -> Mapping[str, Any]: ...

    async def parse_notice(
        self, *, text: str, student_id: str, reference_time: str
    ) -> Mapping[str, Any]: ...

    async def create_task(self, **task: Any) -> Mapping[str, Any]: ...

    async def get_courses(
        self, *, student_id: str, date: str
    ) -> list[Mapping[str, Any]]: ...

    async def complete_task(
        self, *, student_id: str, task_id: str
    ) -> Mapping[str, Any]: ...


TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name="get_today_brief",
        description="获取学生指定日期的课程、任务、通知、冲突和建议。",
        required=("student_id", "date", "timezone"),
        properties={
            "student_id": {"type": "string"},
            "date": {"type": "string", "format": "date"},
            "timezone": {"type": "string"},
        },
    ),
    ToolDefinition(
        name="parse_notice",
        description="解析校园通知；模糊日期会返回需要确认，而不是猜测。",
        required=("text", "student_id", "reference_time"),
        properties={
            "text": {"type": "string"},
            "student_id": {"type": "string"},
            "reference_time": {"type": "string", "format": "date-time"},
        },
    ),
    ToolDefinition(
        name="create_task",
        description="创建校园任务，并通过 dedupe_key 阻止重复任务。",
        required=("student_id", "title", "task_type", "priority", "dedupe_key"),
        properties={
            "student_id": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": ["string", "null"]},
            "task_type": {"type": "string"},
            "priority": {"type": "string"},
            "due_at": {"type": ["string", "null"], "format": "date-time"},
            "source_notice_id": {"type": ["string", "null"]},
            "dedupe_key": {"type": "string"},
        },
    ),
    ToolDefinition(
        name="get_courses",
        description="获取学生指定日期的课程列表。",
        required=("student_id", "date"),
        properties={
            "student_id": {"type": "string"},
            "date": {"type": "string", "format": "date"},
        },
    ),
    ToolDefinition(
        name="complete_task",
        description="将学生的指定任务标记为已完成。",
        required=("student_id", "task_id"),
        properties={
            "student_id": {"type": "string"},
            "task_id": {"type": "string"},
        },
    ),
)

TOOL_NAMES = tuple(definition.name for definition in TOOL_DEFINITIONS)


class CampusToolRegistry:
    """Calls Campus Services without knowing their repository implementation."""

    def __init__(self, service: CampusService, *, default_timeout_seconds: float = 8.0):
        if default_timeout_seconds <= 0:
            raise ValueError("default_timeout_seconds must be positive")
        self.service = service
        self.default_timeout_seconds = default_timeout_seconds

    async def execute(
        self,
        name: str,
        arguments: Mapping[str, Any],
        *,
        timeout_seconds: float | None = None,
    ) -> ToolResult:
        """Validate, execute and normalize one tool call.

        Argument values and service results are deliberately not logged here.
        """

        try:
            normalized = _validate_arguments(name, arguments)
        except ToolValidationError as exc:
            return ToolResult.failure("VALIDATION_ERROR", exc.message, exc.details)

        timeout = timeout_seconds or self.default_timeout_seconds
        if timeout <= 0:
            return ToolResult.failure(
                "VALIDATION_ERROR",
                "Tool timeout must be positive",
                {"field": "timeout_seconds"},
            )

        try:
            value = await asyncio.wait_for(
                self._dispatch(name, normalized), timeout=timeout
            )
            _validate_output(name, value)
            return ToolResult.success(value)
        except TimeoutError:
            return ToolResult.failure(
                "AGENT_TOOL_FAILED",
                "校园工具调用超时，操作未完成",
                {"reason": "tool_timeout", "tool": name},
            )
        except asyncio.CancelledError:
            raise
        except ToolServiceError as exc:
            code = exc.code if exc.code in STABLE_ERROR_CODES else "AGENT_TOOL_FAILED"
            details = dict(exc.details)
            if code != exc.code:
                details["service_code"] = exc.code
            return ToolResult.failure(code, exc.message, details)
        except ToolValidationError as exc:
            return ToolResult.failure(
                "AGENT_TOOL_FAILED",
                "校园服务返回了不兼容的数据",
                {"reason": "invalid_service_result", **dict(exc.details)},
            )
        except Exception:
            return ToolResult.failure(
                "AGENT_TOOL_FAILED",
                "校园工具执行失败，操作未完成",
                {"reason": "service_exception", "tool": name},
            )

    async def _dispatch(self, name: str, arguments: Mapping[str, Any]) -> Any:
        if name == "get_today_brief":
            return await self.service.get_today_brief(**arguments)
        if name == "parse_notice":
            return await self.service.parse_notice(**arguments)
        if name == "create_task":
            return await self.service.create_task(**arguments)
        if name == "get_courses":
            return await self.service.get_courses(**arguments)
        if name == "complete_task":
            return await self.service.complete_task(**arguments)
        raise ToolValidationError("Unknown tool", {"tool": name})


def _required_text(arguments: Mapping[str, Any], field: str) -> str:
    value = arguments.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ToolValidationError(
            f"{field} must be a non-empty string", {"field": field}
        )
    return value.strip()


def _iso_date(value: str, field: str = "date") -> str:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ToolValidationError(
            f"{field} must use YYYY-MM-DD", {"field": field}
        ) from exc
    return value


def _aware_datetime(value: str, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ToolValidationError(
            f"{field} must be ISO 8601", {"field": field}
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ToolValidationError(
            f"{field} must include a timezone", {"field": field}
        )
    return value


def _only_known_fields(arguments: Mapping[str, Any], allowed: set[str]) -> None:
    extras = set(arguments) - allowed
    if extras:
        raise ToolValidationError(
            "Tool arguments contain unknown fields", {"fields": sorted(extras)}
        )


def _validate_arguments(name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    if name not in TOOL_NAMES:
        raise ToolValidationError("Unknown tool", {"tool": name})
    if not isinstance(arguments, Mapping):
        raise ToolValidationError("Tool arguments must be an object")

    if name == "get_today_brief":
        _only_known_fields(arguments, {"student_id", "date", "timezone"})
        timezone = _required_text(arguments, "timezone")
        if timezone != "Asia/Shanghai":
            raise ToolValidationError(
                "timezone must be Asia/Shanghai", {"field": "timezone"}
            )
        return {
            "student_id": _required_text(arguments, "student_id"),
            "date": _iso_date(_required_text(arguments, "date")),
            "timezone": timezone,
        }

    if name == "parse_notice":
        _only_known_fields(arguments, {"text", "student_id", "reference_time"})
        return {
            "text": _required_text(arguments, "text"),
            "student_id": _required_text(arguments, "student_id"),
            "reference_time": _aware_datetime(
                _required_text(arguments, "reference_time"), "reference_time"
            ),
        }

    if name == "create_task":
        allowed = {
            "student_id",
            "title",
            "description",
            "task_type",
            "priority",
            "due_at",
            "source_notice_id",
            "dedupe_key",
        }
        _only_known_fields(arguments, allowed)
        task_type = _required_text(arguments, "task_type")
        if task_type not in {
            "registration",
            "exam",
            "assignment",
            "course",
            "activity",
            "general",
        }:
            raise ToolValidationError("Invalid task_type", {"field": "task_type"})
        priority = _required_text(arguments, "priority")
        if priority not in {"critical", "high", "medium", "normal"}:
            raise ToolValidationError("Invalid priority", {"field": "priority"})
        normalized: dict[str, Any] = {
            "student_id": _required_text(arguments, "student_id"),
            "title": _required_text(arguments, "title"),
            "task_type": task_type,
            "priority": priority,
            "dedupe_key": _required_text(arguments, "dedupe_key"),
        }
        for optional in ("description", "source_notice_id"):
            value = arguments.get(optional)
            if value is not None and not isinstance(value, str):
                raise ToolValidationError(
                    f"{optional} must be a string or null", {"field": optional}
                )
            normalized[optional] = value
        due_at = arguments.get("due_at")
        normalized["due_at"] = (
            _aware_datetime(due_at, "due_at") if due_at is not None else None
        )
        return normalized

    if name == "get_courses":
        _only_known_fields(arguments, {"student_id", "date"})
        return {
            "student_id": _required_text(arguments, "student_id"),
            "date": _iso_date(_required_text(arguments, "date")),
        }

    _only_known_fields(arguments, {"student_id", "task_id"})
    return {
        "student_id": _required_text(arguments, "student_id"),
        "task_id": _required_text(arguments, "task_id"),
    }


NOTICE_FIELDS = {
    "id",
    "title",
    "raw_text",
    "audience",
    "published_at",
    "deadline",
    "actions",
    "priority",
    "source_type",
    "source_ref",
    "confidence",
    "needs_confirmation",
    "created_at",
}

COURSE_FIELDS = {
    "id",
    "student_id",
    "name",
    "teacher",
    "weekday",
    "start_time",
    "end_time",
    "location",
    "start_week",
    "end_week",
    "week_pattern",
    "custom_weeks",
}

TASK_FIELDS = {
    "id",
    "student_id",
    "title",
    "description",
    "task_type",
    "priority",
    "status",
    "due_at",
    "source_notice_id",
    "dedupe_key",
    "created_at",
    "completed_at",
}


def _mapping_with_fields(value: Any, fields: set[str], label: str) -> None:
    if not isinstance(value, Mapping):
        raise ToolValidationError(f"{label} must be an object", {"result": label})
    missing = fields - set(value)
    if missing:
        raise ToolValidationError(
            f"{label} is missing fields", {"result": label, "fields": sorted(missing)}
        )


def _validate_output(name: str, value: Any) -> None:
    if name == "get_today_brief":
        _mapping_with_fields(
            value,
            {"date", "courses", "tasks", "notices", "conflicts", "suggestions"},
            "brief",
        )
        for field in ("courses", "tasks", "notices", "conflicts", "suggestions"):
            if not isinstance(value[field], list):
                raise ToolValidationError(
                    "brief list field has invalid type", {"field": field}
                )
        return
    if name == "parse_notice":
        _mapping_with_fields(value, NOTICE_FIELDS, "notice")
        confidence = value["confidence"]
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ToolValidationError(
                "notice confidence must be between 0 and 1", {"field": "confidence"}
            )
        return
    if name == "create_task":
        _mapping_with_fields(value, {"task", "created", "duplicate_of"}, "task_result")
        _mapping_with_fields(value["task"], TASK_FIELDS, "task")
        if not isinstance(value["created"], bool):
            raise ToolValidationError(
                "created must be boolean", {"field": "created"}
            )
        return
    if name == "get_courses":
        if not isinstance(value, list):
            raise ToolValidationError("courses must be a list", {"result": "courses"})
        for course in value:
            _mapping_with_fields(course, COURSE_FIELDS, "course")
        return
    _mapping_with_fields(value, TASK_FIELDS, "task")
