"""Shared protocol and transport primitives for optional chat providers."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Mapping, Protocol, Sequence
from urllib import error, request
from urllib.parse import urlparse


class ModelUnavailableError(RuntimeError):
    """The optional model provider could not return a usable response."""


class JsonTransport(Protocol):
    async def post_json(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> Mapping[str, Any]: ...


class ChatModelClient(Protocol):
    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    async def complete(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        timeout_seconds: float | None = None,
    ) -> str: ...


class StdlibJsonTransport:
    """Small async JSON transport with no provider SDK or global secret state."""

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
                raise ModelUnavailableError("model request failed") from exc
            if not isinstance(decoded, Mapping):
                raise ModelUnavailableError("model returned an invalid response")
            return decoded

        return await asyncio.to_thread(send)


def validate_base_url(value: str, *, field_name: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    local_http = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}
    if parsed.scheme != "https" and not local_http:
        raise ValueError(f"{field_name} must use HTTPS (or local HTTP for testing)")
    if not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError(f"{field_name} is invalid")
    return normalized


def validate_messages(
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


def positive_timeout(value: float | None, default: float) -> float:
    selected = default if value is None else value
    if selected <= 0:
        raise ValueError("timeout_seconds must be positive")
    return selected
