"""Optional DeepSeek OpenAI-compatible chat adapter.

Secrets are read from the environment at runtime and never included in repr,
exceptions, traces or request payload snapshots.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence
from urllib import error, request
from urllib.parse import urlparse


class ModelUnavailableError(RuntimeError):
    """The optional model could not return a usable response."""


class JsonTransport(Protocol):
    async def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


class StdlibJsonTransport:
    """Minimal async wrapper over urllib; no SDK or secret-bearing global state."""

    async def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]:
        def send() -> Mapping[str, Any]:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            req = request.Request(url, data=body, headers=dict(headers), method="POST")
            try:
                with request.urlopen(req, timeout=timeout_seconds) as response:
                    decoded = json.loads(response.read().decode("utf-8"))
            except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                raise ModelUnavailableError("DeepSeek request failed") from exc
            if not isinstance(decoded, Mapping):
                raise ModelUnavailableError("DeepSeek returned an invalid response")
            return decoded

        return await asyncio.to_thread(send)


@dataclass(frozen=True, slots=True)
class DeepSeekConfig:
    api_key: str = field(repr=False)
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> "DeepSeekConfig | None":
        values = os.environ if environ is None else environ
        api_key = values.get("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            return None
        base_url = values.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip()
        model = values.get("DEEPSEEK_MODEL", "deepseek-chat").strip()
        _validate_base_url(base_url)
        if not model:
            raise ValueError("DEEPSEEK_MODEL cannot be empty")
        return cls(api_key=api_key, base_url=base_url.rstrip("/"), model=model)


class DeepSeekChatClient:
    """Calls DeepSeek only when an explicit configuration exists."""

    def __init__(
        self,
        config: DeepSeekConfig,
        *,
        transport: JsonTransport | None = None,
        default_timeout_seconds: float = 20.0,
    ) -> None:
        self._config = config
        self._transport = transport or StdlibJsonTransport()
        self._default_timeout_seconds = default_timeout_seconds

    @property
    def model(self) -> str:
        return self._config.model

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        timeout_seconds: float | None = None,
    ) -> str:
        timeout = timeout_seconds or self._default_timeout_seconds
        if timeout <= 0:
            raise ValueError("timeout_seconds must be positive")
        normalized = _validate_messages(messages)
        url = f"{self._config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._config.model,
            "messages": normalized,
            "stream": False,
        }
        try:
            response = await asyncio.wait_for(
                self._transport.post_json(
                    url,
                    headers=headers,
                    payload=payload,
                    timeout_seconds=timeout,
                ),
                timeout=timeout,
            )
        except (TimeoutError, ModelUnavailableError) as exc:
            raise ModelUnavailableError("DeepSeek model unavailable") from exc
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise ModelUnavailableError("DeepSeek model unavailable") from exc

        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ModelUnavailableError("DeepSeek returned an invalid response") from exc
        if not isinstance(content, str) or not content.strip():
            raise ModelUnavailableError("DeepSeek returned an empty response")
        return content.strip()


def _validate_base_url(value: str) -> None:
    parsed = urlparse(value)
    local_http = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
    if parsed.scheme != "https" and not local_http:
        raise ValueError("DEEPSEEK_BASE_URL must use HTTPS (or local HTTP for testing)")
    if not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("DEEPSEEK_BASE_URL is invalid")


def _validate_messages(
    messages: Sequence[Mapping[str, str]],
) -> list[dict[str, str]]:
    if not messages:
        raise ValueError("messages cannot be empty")
    normalized: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content")
        if role not in {"system", "user", "assistant"}:
            raise ValueError("message role is invalid")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("message content cannot be empty")
        normalized.append({"role": role, "content": content.strip()})
    return normalized
