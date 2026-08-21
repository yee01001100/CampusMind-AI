"""Dependency-free input/result models for the CampusMind tool contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ToolError:
    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    data: Any = None
    error: ToolError | None = None

    @classmethod
    def success(cls, data: Any) -> "ToolResult":
        return cls(ok=True, data=data)

    @classmethod
    def failure(
        cls,
        code: str,
        message: str,
        details: Mapping[str, Any] | None = None,
    ) -> "ToolResult":
        return cls(
            ok=False,
            error=ToolError(code=code, message=message, details=details or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error.to_dict() if self.error else None,
        }


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    description: str
    required: tuple[str, ...]
    properties: Mapping[str, Mapping[str, Any]]

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": dict(self.properties),
                    "required": list(self.required),
                    "additionalProperties": False,
                },
            },
        }


@dataclass(frozen=True, slots=True)
class ToolTrace:
    name: str
    started_at: str
    status: str
    duration_ms: int
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
