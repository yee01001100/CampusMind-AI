"""OpenAI-compatible Chat Completions client and environment configuration."""

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
class OpenAICompatibleConfig:
    api_key: str = field(repr=False)
    base_url: str
    model: str
    provider: str = "openai-compatible"

    @classmethod
    def from_openai_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> "OpenAICompatibleConfig | None":
        values = os.environ if environ is None else environ
        api_key = values.get("OPENAI_API_KEY", "").strip()
        if not api_key:
            return None
        return cls._validated(
            api_key=api_key,
            base_url=values.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=values.get("OPENAI_MODEL", ""),
            provider="openai",
            field_prefix="OPENAI",
        )

    @classmethod
    def from_compatible_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> "OpenAICompatibleConfig | None":
        values = os.environ if environ is None else environ
        api_key = values.get("MODEL_API_KEY", "").strip()
        if not api_key:
            return None
        return cls._validated(
            api_key=api_key,
            base_url=values.get("MODEL_BASE_URL", ""),
            model=values.get("MODEL_NAME", ""),
            provider="openai-compatible",
            field_prefix="MODEL",
        )

    @classmethod
    def _validated(
        cls,
        *,
        api_key: str,
        base_url: str,
        model: str,
        provider: str,
        field_prefix: str,
    ) -> "OpenAICompatibleConfig":
        selected_model = model.strip()
        if not selected_model:
            model_field = "OPENAI_MODEL" if field_prefix == "OPENAI" else "MODEL_NAME"
            raise ValueError(f"{model_field} cannot be empty")
        url_field = "OPENAI_BASE_URL" if field_prefix == "OPENAI" else "MODEL_BASE_URL"
        return cls(
            api_key=api_key,
            base_url=validate_base_url(base_url, field_name=url_field),
            model=selected_model,
            provider=provider,
        )


class OpenAICompatibleChatClient:
    """Calls providers implementing the OpenAI Chat Completions schema."""

    def __init__(
        self,
        config: OpenAICompatibleConfig,
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
        payload = {
            "model": self._config.model,
            "messages": validate_messages(messages),
            "stream": False,
        }
        try:
            response = await asyncio.wait_for(
                self._transport.post_json(
                    f"{self._config.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._config.api_key}",
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
            raise ModelUnavailableError(
                f"{self._config.provider} model unavailable"
            ) from exc

        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelUnavailableError(
                f"{self._config.provider} returned an invalid response"
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise ModelUnavailableError(
                f"{self._config.provider} returned an empty response"
            )
        return content.strip()
