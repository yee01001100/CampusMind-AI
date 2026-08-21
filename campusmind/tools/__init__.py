"""Public CampusMind tool adapter API."""

from .errors import ToolServiceError
from .models import ToolDefinition, ToolError, ToolResult, ToolTrace
from .registry import TOOL_DEFINITIONS, TOOL_NAMES, CampusService, CampusToolRegistry

__all__ = [
    "CampusService",
    "CampusToolRegistry",
    "TOOL_DEFINITIONS",
    "TOOL_NAMES",
    "ToolDefinition",
    "ToolError",
    "ToolResult",
    "ToolServiceError",
    "ToolTrace",
]
