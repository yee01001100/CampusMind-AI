"""Public-host adapter for registering CampusMind extensions in DeepTutor."""

from __future__ import annotations

import importlib
import importlib.metadata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable, Protocol

from campusmind.tools import TOOL_DEFINITIONS, CampusToolRegistry


class DeepTutorHost(Protocol):
    def register_skill(self, name: str, instructions: str) -> None: ...

    def register_tool(
        self,
        name: str,
        schema: dict[str, Any],
        handler: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class BridgeStatus:
    available: bool
    registered_tools: tuple[str, ...]
    deeptutor_version: str | None
    reason: str | None = None


class DeepTutorBridge:
    """Registers extensions without patching or vendoring DeepTutor internals."""

    def __init__(self, tools: CampusToolRegistry, *, skill_path: Path | None = None):
        self._tools = tools
        self._skill_path = skill_path or _default_skill_path()

    def initialize(self, host: DeepTutorHost | None = None) -> BridgeStatus:
        """Register with a supplied host, or discover a supported public host.

        Absence of DeepTutor is reported as unavailable. It is not presented as a
        successful online/model initialization.
        """

        version: str | None = None
        if host is None:
            host, version = _discover_host()
            if host is None:
                return BridgeStatus(
                    available=False,
                    registered_tools=(),
                    deeptutor_version=version,
                    reason="DeepTutor host is not installed or exposes no supported host factory",
                )

        instructions = self._skill_path.read_text(encoding="utf-8")
        host.register_skill("campusmind", instructions)
        registered: list[str] = []
        for definition in TOOL_DEFINITIONS:
            name = definition.name

            async def handler(arguments: dict[str, Any], tool_name: str = name) -> dict[str, Any]:
                return (await self._tools.execute(tool_name, arguments)).to_dict()

            host.register_tool(name, definition.to_openai_schema(), handler)
            registered.append(name)
        return BridgeStatus(
            available=True,
            registered_tools=tuple(registered),
            deeptutor_version=version,
        )


def _default_skill_path() -> Path:
    return Path(__file__).resolve().parents[3] / "skills" / "campusmind" / "SKILL.md"


def _discover_host() -> tuple[DeepTutorHost | None, str | None]:
    try:
        module = importlib.import_module("deeptutor")
    except ImportError:
        return None, None
    try:
        version = importlib.metadata.version("deeptutor")
    except importlib.metadata.PackageNotFoundError:
        version = getattr(module, "__version__", None)
    factory = getattr(module, "create_extension_host", None)
    if not callable(factory):
        return None, version
    candidate = factory()
    if not callable(getattr(candidate, "register_skill", None)) or not callable(
        getattr(candidate, "register_tool", None)
    ):
        return None, version
    return candidate, version
