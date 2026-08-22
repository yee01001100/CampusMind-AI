from __future__ import annotations

import asyncio
from typing import Any, Mapping

import pytest

from apps.api.agent import build_agent_runtime
from campusmind.integrations.deeptutor import (
    AgentRequest,
    AnthropicChatClient,
    AnthropicConfig,
    ModelUnavailableError,
    OpenAICompatibleChatClient,
    OpenAICompatibleConfig,
)

from .fakes import FakeCampusService


def run(coro):
    return asyncio.run(coro)


class RecordingTransport:
    def __init__(self, response: Mapping[str, Any]):
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def post_json(self, url, *, headers, payload, timeout_seconds):
        self.calls.append(
            {"url": url, "headers": headers, "payload": payload, "timeout": timeout_seconds}
        )
        return self.response


def test_openai_environment_uses_chat_completions_protocol() -> None:
    transport = RecordingTransport(
        {"choices": [{"message": {"content": "OpenAI 模拟回复"}}]}
    )
    config = OpenAICompatibleConfig.from_openai_env(
        {
            "OPENAI_API_KEY": "test-openai-key-not-secret",
            "OPENAI_BASE_URL": "https://api.openai.example/v1",
            "OPENAI_MODEL": "gpt-test",
        }
    )
    assert config is not None
    client = OpenAICompatibleChatClient(config, transport=transport)

    content = run(client.complete([{"role": "user", "content": "你好"}]))

    call = transport.calls[0]
    assert content == "OpenAI 模拟回复"
    assert client.provider == "openai"
    assert call["url"] == "https://api.openai.example/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer test-openai-key-not-secret"
    assert call["payload"] == {
        "model": "gpt-test",
        "messages": [{"role": "user", "content": "你好"}],
        "stream": False,
    }
    assert "test-openai-key-not-secret" not in repr(config)


def test_generic_openai_compatible_environment_requires_base_url_and_model() -> None:
    config = OpenAICompatibleConfig.from_compatible_env(
        {
            "MODEL_API_KEY": "test-compatible-key-not-secret",
            "MODEL_BASE_URL": "https://gateway.example/v1",
            "MODEL_NAME": "compatible-model",
        }
    )

    assert config is not None
    assert config.provider == "openai-compatible"
    assert config.base_url == "https://gateway.example/v1"
    assert config.model == "compatible-model"
    assert "test-compatible-key-not-secret" not in repr(config)


def test_anthropic_environment_uses_native_messages_protocol() -> None:
    transport = RecordingTransport(
        {
            "content": [
                {"type": "thinking", "thinking": "not exposed"},
                {"type": "text", "text": "Anthropic 模拟回复"},
                {"type": "text", "text": "第二段"},
            ]
        }
    )
    config = AnthropicConfig.from_env(
        {
            "ANTHROPIC_API_KEY": "test-anthropic-key-not-secret",
            "ANTHROPIC_BASE_URL": "https://api.anthropic.example/v1",
            "ANTHROPIC_MODEL": "claude-test",
            "ANTHROPIC_VERSION": "2023-06-01",
            "ANTHROPIC_MAX_TOKENS": "768",
        }
    )
    assert config is not None
    client = AnthropicChatClient(config, transport=transport)

    content = run(
        client.complete(
            [
                {"role": "system", "content": "只回答模拟内容"},
                {"role": "user", "content": "你好"},
            ]
        )
    )

    call = transport.calls[0]
    assert content == "Anthropic 模拟回复\n第二段"
    assert client.provider == "anthropic"
    assert call["url"] == "https://api.anthropic.example/v1/messages"
    assert call["headers"]["x-api-key"] == "test-anthropic-key-not-secret"
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    assert "Authorization" not in call["headers"]
    assert call["payload"] == {
        "model": "claude-test",
        "max_tokens": 768,
        "system": "只回答模拟内容",
        "messages": [{"role": "user", "content": "你好"}],
    }
    assert "test-anthropic-key-not-secret" not in repr(config)


@pytest.mark.parametrize(
    "environ,response,expected_mode,expected_trace",
    [
        (
            {
                "CAMPUSMIND_MODEL_MODE": "openai",
                "OPENAI_API_KEY": "test-openai-key-not-secret",
                "OPENAI_MODEL": "gpt-test",
            },
            {"choices": [{"message": {"content": "OpenAI Runtime"}}]},
            "openai",
            "openai_chat",
        ),
        (
            {
                "CAMPUSMIND_MODEL_MODE": "anthropic",
                "ANTHROPIC_API_KEY": "test-anthropic-key-not-secret",
                "ANTHROPIC_MODEL": "claude-test",
            },
            {"content": [{"type": "text", "text": "Anthropic Runtime"}]},
            "anthropic",
            "anthropic_chat",
        ),
    ],
)
def test_runtime_reports_selected_provider(
    environ, response, expected_mode, expected_trace
) -> None:
    transport = RecordingTransport(response)
    runtime = build_agent_runtime(
        FakeCampusService(), environ=environ, model_transport=transport
    )

    result = run(
        runtime.chat(
            AgentRequest(
                message="你好，介绍一下自己",
                student_id="student-demo-001",
                reference_time="2026-08-21T09:00:00+08:00",
            )
        )
    )

    assert result.ok is True
    assert result.runtime_mode == expected_mode
    assert result.traces[0].name == expected_trace
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "mode,expected_variable",
    [
        ("deepseek", "DEEPSEEK_API_KEY"),
        ("openai", "OPENAI_API_KEY"),
        ("openai-compatible", "MODEL_API_KEY"),
        ("anthropic", "ANTHROPIC_API_KEY"),
    ],
)
def test_explicit_provider_mode_requires_its_key(mode, expected_variable) -> None:
    with pytest.raises(ValueError, match=expected_variable):
        build_agent_runtime(
            FakeCampusService(), environ={"CAMPUSMIND_MODEL_MODE": mode}
        )


def test_local_rules_does_not_infer_provider_from_any_key() -> None:
    runtime = build_agent_runtime(
        FakeCampusService(),
        environ={
            "DEEPSEEK_API_KEY": "test-deepseek-key-not-secret",
            "OPENAI_API_KEY": "test-openai-key-not-secret",
            "ANTHROPIC_API_KEY": "test-anthropic-key-not-secret",
            "MODEL_API_KEY": "test-compatible-key-not-secret",
        },
    )

    assert runtime.model is None


def test_provider_rejects_invalid_or_empty_responses() -> None:
    config = AnthropicConfig(
        api_key="test-anthropic-key-not-secret", model="claude-test"
    )
    client = AnthropicChatClient(config, transport=RecordingTransport({"content": []}))

    with pytest.raises(ModelUnavailableError):
        run(client.complete([{"role": "user", "content": "你好"}]))
