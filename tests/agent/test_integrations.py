from __future__ import annotations

import asyncio
from typing import Any, Mapping

import pytest

from apps.api.agent import AgentChatFacade, build_agent_runtime
from campusmind.integrations.deeptutor import (
    AgentRequest,
    DeepSeekChatClient,
    DeepSeekConfig,
    DeepTutorBridge,
    ModelUnavailableError,
)
from campusmind.tools import TOOL_NAMES, CampusToolRegistry

from .fakes import FakeCampusService


def run(coro):
    return asyncio.run(coro)


class FakeTransport:
    def __init__(self, response: Mapping[str, Any] | None = None, delay: float = 0):
        self.response = response or {
            "choices": [{"message": {"content": "这是模拟模型回复"}}]
        }
        self.delay = delay
        self.calls: list[dict[str, Any]] = []

    async def post_json(self, url, *, headers, payload, timeout_seconds):
        self.calls.append(
            {"url": url, "headers": headers, "payload": payload, "timeout": timeout_seconds}
        )
        if self.delay:
            await asyncio.sleep(self.delay)
        return self.response


class FakeDeepTutorHost:
    def __init__(self) -> None:
        self.skill: tuple[str, str] | None = None
        self.tools: dict[str, tuple[dict, Any]] = {}

    def register_skill(self, name, instructions):
        self.skill = (name, instructions)

    def register_tool(self, name, schema, handler):
        self.tools[name] = (schema, handler)


def test_deepseek_is_optional_when_key_is_absent() -> None:
    assert DeepSeekConfig.from_env({}) is None
    runtime = build_agent_runtime(FakeCampusService(), environ={})
    assert runtime.model is None


def test_deepseek_uses_fake_openai_compatible_transport() -> None:
    transport = FakeTransport()
    config = DeepSeekConfig.from_env(
        {
            "DEEPSEEK_API_KEY": "test-key-not-a-secret",
            "DEEPSEEK_BASE_URL": "https://example.invalid/v1",
            "DEEPSEEK_MODEL": "deepseek-chat-test",
        }
    )
    client = DeepSeekChatClient(config, transport=transport)
    content = run(client.complete([{"role": "user", "content": "你好"}]))
    assert content == "这是模拟模型回复"
    assert transport.calls[0]["url"] == "https://example.invalid/v1/chat/completions"
    assert transport.calls[0]["payload"]["model"] == "deepseek-chat-test"
    assert "test-key-not-a-secret" not in repr(config)


def test_deepseek_timeout_is_reported_without_fallback_claim() -> None:
    config = DeepSeekConfig("test-key-not-a-secret")
    client = DeepSeekChatClient(config, transport=FakeTransport(delay=0.05))
    with pytest.raises(ModelUnavailableError):
        run(
            client.complete(
                [{"role": "user", "content": "你好"}], timeout_seconds=0.005
            )
        )


def test_runtime_uses_deepseek_only_for_general_chat() -> None:
    transport = FakeTransport()
    runtime = build_agent_runtime(
        FakeCampusService(),
        environ={"DEEPSEEK_API_KEY": "test-key-not-a-secret"},
        model_transport=transport,
    )
    response = run(
        runtime.chat(
            AgentRequest(
                message="你好，讲个笑话",
                student_id="student-demo-001",
                reference_time="2026-08-21T09:00:00+08:00",
            )
        )
    )
    assert response.ok is True
    assert response.runtime_mode == "deepseek"
    assert response.traces[0].name == "deepseek_chat"
    assert len(transport.calls) == 1


def test_campus_intent_does_not_send_source_of_truth_request_to_model() -> None:
    transport = FakeTransport()
    runtime = build_agent_runtime(
        FakeCampusService(),
        environ={"DEEPSEEK_API_KEY": "test-key-not-a-secret"},
        model_transport=transport,
    )
    response = run(
        runtime.chat(
            AgentRequest(
                message="今天有什么事情？",
                student_id="student-demo-001",
                reference_time="2026-08-21T09:00:00+08:00",
            )
        )
    )
    assert response.ok is True
    assert response.traces[0].name == "get_today_brief"
    assert transport.calls == []


def test_runtime_model_failure_is_not_rewritten_as_success() -> None:
    transport = FakeTransport(delay=0.05)
    config = DeepSeekConfig("test-key-not-a-secret")
    model = DeepSeekChatClient(config, transport=transport)
    from campusmind.integrations.deeptutor import CampusMindRuntime

    runtime = CampusMindRuntime(
        CampusToolRegistry(FakeCampusService()),
        model=model,
        model_timeout_seconds=0.005,
    )
    response = run(
        runtime.chat(
            AgentRequest(
                message="你好，讲个笑话",
                student_id="student-demo-001",
                reference_time="2026-08-21T09:00:00+08:00",
            )
        )
    )
    assert response.ok is False
    assert response.error.code == "MODEL_UNAVAILABLE"
    assert "没有伪造" in response.message
    assert response.traces[0].name == "deepseek_chat"


def test_inflight_model_call_can_be_interrupted() -> None:
    async def scenario():
        model = DeepSeekChatClient(
            DeepSeekConfig("test-key-not-a-secret"),
            transport=FakeTransport(delay=0.2),
        )
        from campusmind.integrations.deeptutor import CampusMindRuntime

        runtime = CampusMindRuntime(
            CampusToolRegistry(FakeCampusService()), model=model
        )
        event = asyncio.Event()
        pending = asyncio.create_task(
            runtime.chat(
                AgentRequest(
                    message="你好，讲个笑话",
                    student_id="student-demo-001",
                    reference_time="2026-08-21T09:00:00+08:00",
                ),
                cancel_event=event,
            )
        )
        await asyncio.sleep(0.01)
        event.set()
        return await pending

    response = run(scenario())
    assert response.ok is False
    assert response.error.details["reason"] == "interrupted"
    assert response.traces[0].status == "interrupted"


def test_deeptutor_bridge_registers_skill_and_exact_five_tools() -> None:
    service = FakeCampusService()
    host = FakeDeepTutorHost()
    status = DeepTutorBridge(CampusToolRegistry(service)).initialize(host)
    assert status.available is True
    assert status.registered_tools == TOOL_NAMES
    assert set(host.tools) == set(TOOL_NAMES)
    assert host.skill and host.skill[0] == "campusmind"
    assert "Never invent" in host.skill[1]
    result = run(
        host.tools["get_courses"][1](
            {"student_id": "student-demo-001", "date": "2026-08-21"}
        )
    )
    assert result["ok"] is True


def test_chat_facade_returns_shared_envelope() -> None:
    facade = AgentChatFacade(build_agent_runtime(FakeCampusService(), environ={}))
    payload = {
        "message": "今天有什么事情？",
        "student_id": "student-demo-001",
        "reference_time": "2026-08-21T09:00:00+08:00",
        "request_id": "req-facade-001",
    }
    result = run(facade.chat(payload))
    assert result["ok"] is True
    assert result["error"] is None
    assert result["request_id"] == "req-facade-001"
    assert result["data"]["traces"][0]["name"] == "get_today_brief"
