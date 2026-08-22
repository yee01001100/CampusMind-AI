"""Framework-neutral facade for the future POST /api/v1/chat route."""

from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncIterator, Mapping
from uuid import uuid4

from campusmind.integrations.deeptutor import (
    AgentRequest,
    AnthropicChatClient,
    AnthropicConfig,
    CampusMindRuntime,
    DeepSeekChatClient,
    DeepSeekConfig,
    OpenAICompatibleChatClient,
    OpenAICompatibleConfig,
    PreferenceMemory,
)
from campusmind.tools import CampusService, CampusToolRegistry


def build_agent_runtime(
    service: CampusService,
    *,
    environ: Mapping[str, str] | None = None,
    model_transport: Any = None,
) -> CampusMindRuntime:
    """Build the runtime with an explicit, optional model provider.

    ``CAMPUSMIND_MODEL_MODE`` defaults to ``local-rules`` and never infers a
    provider from a stray key. ``model_transport`` is dependency injection for
    protocol tests; production uses the standard-library HTTPS transport.
    """

    values = os.environ if environ is None else environ
    mode = values.get("CAMPUSMIND_MODEL_MODE", "local-rules").strip().lower()
    if mode == "local-rules":
        model = None
    elif mode == "deepseek":
        config = DeepSeekConfig.from_env(values)
        if config is None:
            raise ValueError("DEEPSEEK_API_KEY is required for deepseek mode")
        model = DeepSeekChatClient(config, transport=model_transport)
    elif mode == "openai":
        config = OpenAICompatibleConfig.from_openai_env(values)
        if config is None:
            raise ValueError("OPENAI_API_KEY is required for openai mode")
        model = OpenAICompatibleChatClient(config, transport=model_transport)
    elif mode == "openai-compatible":
        config = OpenAICompatibleConfig.from_compatible_env(values)
        if config is None:
            raise ValueError("MODEL_API_KEY is required for openai-compatible mode")
        model = OpenAICompatibleChatClient(config, transport=model_transport)
    elif mode == "anthropic":
        config = AnthropicConfig.from_env(values)
        if config is None:
            raise ValueError("ANTHROPIC_API_KEY is required for anthropic mode")
        model = AnthropicChatClient(config, transport=model_transport)
    else:
        raise ValueError(
            "CAMPUSMIND_MODEL_MODE must be local-rules, deepseek, openai, "
            "openai-compatible, or anthropic"
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
