"""Backward-compatible DeepSeek adapter built on the OpenAI-compatible client."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping

from .model_client import (
    JsonTransport,
    ModelUnavailableError,
    StdlibJsonTransport,
    validate_base_url,
)
from .openai_compatible import OpenAICompatibleChatClient, OpenAICompatibleConfig


@dataclass(frozen=True, slots=True)
class DeepSeekConfig:
    api_key: str = field(repr=False)
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    provider: str = "deepseek"

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> "DeepSeekConfig | None":
        values = os.environ if environ is None else environ
        api_key = values.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            return None
        model = values.get("DEEPSEEK_MODEL", "deepseek-chat").strip()
        if not model:
            raise ValueError("DEEPSEEK_MODEL cannot be empty")
        return cls(
            api_key=api_key,
            base_url=validate_base_url(
                values.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                field_name="DEEPSEEK_BASE_URL",
            ),
            model=model,
        )


class DeepSeekChatClient(OpenAICompatibleChatClient):
    def __init__(
        self,
        config: DeepSeekConfig,
        *,
        transport: JsonTransport | None = None,
        default_timeout_seconds: float = 20.0,
    ) -> None:
        compatible = OpenAICompatibleConfig(
            api_key=config.api_key,
            base_url=config.base_url,
            model=config.model,
            provider="deepseek",
        )
        super().__init__(
            compatible,
            transport=transport,
            default_timeout_seconds=default_timeout_seconds,
        )


__all__ = [
    "DeepSeekChatClient",
    "DeepSeekConfig",
    "JsonTransport",
    "ModelUnavailableError",
    "StdlibJsonTransport",
]
