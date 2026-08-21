"""Framework-neutral facade for the future POST /api/v1/chat route."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Mapping
from uuid import uuid4

from campusmind.integrations.deeptutor import (
    AgentRequest,
    CampusMindRuntime,
    DeepSeekChatClient,
    DeepSeekConfig,
    PreferenceMemory,
)
from campusmind.tools import CampusService, CampusToolRegistry


def build_agent_runtime(
    service: CampusService,
    *,
    environ: Mapping[str, str] | None = None,
    model_transport: Any = None,
) -> CampusMindRuntime:
    """Build the runtime without requiring a model key.

    Agent 3 can call this during application startup. With no
    ``DEEPSEEK_API_KEY`` the returned runtime remains a truthful local-rules
    runtime. ``model_transport`` exists for dependency injection in tests.
    """

    config = DeepSeekConfig.from_env(environ)
    model = (
        DeepSeekChatClient(config, transport=model_transport)
        if config is not None
        else None
    )
    return CampusMindRuntime(
        CampusToolRegistry(service), memory=PreferenceMemory(), model=model
    )


class AgentChatFacade:
    def __init__(self, runtime: CampusMindRuntime):
        self.runtime = runtime

    async def chat(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        request = _request_from_payload(payload)
        return (await self.runtime.chat(request)).to_dict()

    async def stream(
        self,
        payload: Mapping[str, Any],
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        request = _request_from_payload(payload)
        async for event in self.runtime.stream_chat(
            request, cancel_event=cancel_event
        ):
            yield event


def _request_from_payload(payload: Mapping[str, Any]) -> AgentRequest:
    context = payload.get("context", {})
    return AgentRequest(
        message=payload.get("message", ""),
        student_id=payload.get("student_id", ""),
        request_id=payload.get("request_id") or f"req-{uuid4().hex}",
        reference_time=payload.get("reference_time"),
        timezone=payload.get("timezone", "Asia/Shanghai"),
        context=context if isinstance(context, Mapping) else {},
    )
