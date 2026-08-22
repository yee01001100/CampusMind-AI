"""Anthropic Messages API client and environment configuration."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from .model_client import (
    JsonTransport,
    ModelUnavailableError,
    StdlibJsonTransport,
    positive_timeout,
    validate_base_url,
    validate_messages,
)


@dataclass(frozen=True, slots=True)
class AnthropicConfig:
    api_key: str = field(repr=False)
    model: str
    base_url: str = "https://api.anthropic.com/v1"
    api_version: str = "2023-06-01"
    max_tokens: int = 1024
    provider: str = "anthropic"

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> "AnthropicConfig | None":
        values = os.environ if environ is None else environ
        api_key = values.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            return None
        model = values.get("ANTHROPIC_MODEL", "").strip()
        if not model:
            raise ValueError("ANTHROPIC_MODEL cannot be empty")
        api_version = values.get("ANTHROPIC_VERSION", "2023-06-01").strip()
        if not api_version:
            raise ValueError("ANTHROPIC_VERSION cannot be empty")
        try:
            max_tokens = int(values.get("ANTHROPIC_MAX_TOKENS", "1024"))
        except ValueError as exc:
            raise ValueError("ANTHROPIC_MAX_TOKENS must be an integer") from exc
        if max_tokens <= 0:
            raise ValueError("ANTHROPIC_MAX_TOKENS must be positive")
        return cls(
            api_key=api_key,
            model=model,
            base_url=validate_base_url(
                values.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
                field_name="ANTHROPIC_BASE_URL",
            ),
            api_version=api_version,
            max_tokens=max_tokens,
        )


class AnthropicChatClient:
    """Calls Anthropic's native Messages API without an SDK dependency."""

    def __init__(
        self,
        config: AnthropicConfig,
        *,
        transport: JsonTransport | None = None,
        default_timeout_seconds: float = 20.0,
    ) -> None:
        self._config = config
        self._transport = transport or StdlibJsonTransport()
        self._default_timeout_seconds = default_timeout_seconds

    @property
    def provider(self) -> str:
        return self._config.provider

    @property
    def model(self) -> str:
        return self._config.model

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        timeout_seconds: float | None = None,
    ) -> str:
        timeout = positive_timeout(timeout_seconds, self._default_timeout_seconds)
        normalized = validate_messages(messages)
        system = "\n\n".join(
            item["content"] for item in normalized if item["role"] == "system"
        )
        provider_messages = [
            item for item in normalized if item["role"] in {"user", "assistant"}
        ]
        if not provider_messages:
            raise ValueError("Anthropic messages require a user or assistant message")
        payload: dict[str, object] = {
            "model": self._config.model,
            "max_tokens": self._config.max_tokens,
            "messages": provider_messages,
        }
        if system:
            payload["system"] = system

        try:
            response = await asyncio.wait_for(
                self._transport.post_json(
                    f"{self._config.base_url}/messages",
                    headers={
                        "x-api-key": self._config.api_key,
                        "anthropic-version": self._config.api_version,
                        "Content-Type": "application/json",
                    },
                    payload=payload,
                    timeout_seconds=timeout,
                ),
                timeout=timeout,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise ModelUnavailableError("anthropic model unavailable") from exc

        try:
            blocks = response["content"]
            texts = [
                block["text"].strip()
                for block in blocks
                if isinstance(block, Mapping)
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
                and block["text"].strip()
            ]
        except (KeyError, TypeError) as exc:
            raise ModelUnavailableError("anthropic returned an invalid response") from exc
        if not texts:
            raise ModelUnavailableError("anthropic returned an empty response")
        return "\n".join(texts)
