from __future__ import annotations

import asyncio

import pytest

from campusmind.integrations.deeptutor import (
    AgentRequest,
    CampusMindRuntime,
    MemoryPolicyError,
    PreferenceMemory,
    RequestExecution,
)
from campusmind.tools import CampusToolRegistry

from .fakes import FakeCampusService


STUDENT = "student-demo-001"
REFERENCE = "2026-08-21T09:00:00+08:00"


def run(coro):
    return asyncio.run(coro)


def runtime(service: FakeCampusService | None = None, **kwargs) -> CampusMindRuntime:
    return CampusMindRuntime(CampusToolRegistry(service or FakeCampusService()), **kwargs)


def request(message: str, **kwargs) -> AgentRequest:
    return AgentRequest(
        message=message,
        student_id=STUDENT,
        reference_time=REFERENCE,
        request_id="req-test-001",
        **kwargs,
    )


def test_today_question_calls_brief_and_returns_chinese_trace() -> None:
    service = FakeCampusService()
    response = run(runtime(service).chat(request("今天有什么事情？")))
    assert response.ok is True
    assert service.calls[0][0] == "get_today_brief"
    assert "1 节课" in response.message
    assert response.traces[0].name == "get_today_brief"
    assert response.traces[0].status == "success"
    assert response.traces[0].duration_ms >= 0
    assert response.traces[0].started_at.endswith("+08:00")


def test_empty_today_brief_is_a_real_empty_result() -> None:
    service = FakeCampusService()
    service.empty_brief = True
    response = run(runtime(service).chat(request("今日简报")))
    assert response.ok is True
    assert "0 节课" in response.message
    assert response.data["tasks"] == []


def test_general_chat_does_not_call_campus_tool_without_model() -> None:
    service = FakeCampusService()
    response = run(runtime(service).chat(request("你好，讲个笑话")))
    assert response.ok is True
    assert response.runtime_mode == "local-rules"
    assert "未配置在线模型" in response.message
    assert service.calls == []


def test_ambiguous_notice_requests_confirmation() -> None:
    service = FakeCampusService()
    response = run(
        runtime(service).chat(request("帮我看这个报名通知：下周五截止。"))
    )
    assert response.ok is False
    assert response.error.code == "NOTICE_DATE_AMBIGUOUS"
    assert response.needs_confirmation is True
    assert "补充年份" in response.message


def test_low_confidence_notice_requests_confirmation_even_on_success() -> None:
    response = run(
        runtime().chat(request("帮我看这个低置信度报名通知：请于某日截止。"))
    )
    assert response.ok is True
    assert response.needs_confirmation is True
    assert response.data["confidence"] < 0.75


def test_tool_exception_does_not_become_natural_language_success() -> None:
    service = FakeCampusService()
    service.failures["get_today_brief"] = RuntimeError("database unavailable")
    response = run(runtime(service).chat(request("今天有什么事情？")))
    assert response.ok is False
    assert response.error.code == "AGENT_TOOL_FAILED"
    assert "没有伪造成功" in response.message
    assert response.data is None


def test_rag_without_sources_refuses_to_invent_policy() -> None:
    response = run(runtime().chat(request("学校规定奖学金怎么评？")))
    assert response.ok is False
    assert response.error.code == "RAG_NO_SOURCE"
    assert "无法确认" in response.message
    assert response.traces[0].name == "rag_search"


def test_rag_with_source_returns_answer_and_source() -> None:
    service = FakeCampusService()
    service.rag_sources = [
        {"source_id": "demo-policy", "title": "模拟规定", "is_demo": True}
    ]
    response = run(runtime(service).chat(request("学校规定奖学金怎么评？")))
    assert response.ok is True
    assert response.message == "模拟规则答案"
    assert response.data["sources"][0]["source_id"] == "demo-policy"


def test_repeated_identical_tool_call_is_blocked_per_request() -> None:
    service = FakeCampusService()
    agent = runtime(service)
    execution = RequestExecution()
    arguments = {"student_id": STUDENT, "date": "2026-08-21"}
    first = run(agent.invoke_tool("get_courses", arguments, execution=execution))
    second = run(agent.invoke_tool("get_courses", arguments, execution=execution))
    assert first.ok is True
    assert second.ok is False
    assert second.error.details["reason"] == "tool_call_limit"
    assert len(service.calls) == 1
    assert execution.traces[-1].status == "blocked"


def test_tool_timeout_trace_is_structured() -> None:
    service = FakeCampusService()
    service.delays["get_courses"] = 0.05
    agent = CampusMindRuntime(
        CampusToolRegistry(service, default_timeout_seconds=0.005)
    )
    response = run(agent.chat(request("今天有什么课？")))
    assert response.ok is False
    assert response.traces[0].status == "timeout"
    assert response.traces[0].error_code == "AGENT_TOOL_FAILED"


def test_create_task_requires_explicit_structured_fields() -> None:
    response = run(runtime().chat(request("帮我创建任务")))
    assert response.ok is True
    assert response.needs_confirmation is True
    assert response.traces == ()


def test_duplicate_task_is_not_reported_as_created() -> None:
    service = FakeCampusService()
    agent = runtime(service)
    context = {
        "task": {
            "title": "完成模拟报名",
            "description": None,
            "task_type": "registration",
            "priority": "high",
            "due_at": "2026-08-22T18:00:00+08:00",
            "source_notice_id": "notice-demo-001",
            "dedupe_key": "student-demo-001:notice-demo-001:registration",
        }
    }
    first = run(agent.chat(request("创建任务", context=context)))
    second = run(agent.chat(request("创建任务", context=context)))
    assert first.ok is True
    assert second.ok is False
    assert second.error.code == "TASK_DUPLICATE"
    assert "没有再次创建" in second.message


def test_complete_task_requires_exact_task_id() -> None:
    response = run(runtime().chat(request("这个办完了")))
    assert response.ok is True
    assert response.needs_confirmation is True
    assert "任务 ID" in response.message


def test_memory_allows_preferences_but_rejects_source_of_truth() -> None:
    memory = PreferenceMemory()
    saved = memory.remember(
        STUDENT,
        {
            "major": "计算机科学与技术",
            "interests": ["人工智能"],
            "reminder_preferences": {"assignment": ["P1D"]},
        },
    )
    assert saved["major"] == "计算机科学与技术"
    with pytest.raises(MemoryPolicyError):
        memory.remember(STUDENT, {"tasks": [{"status": "completed"}]})
    with pytest.raises(MemoryPolicyError):
        memory.remember(STUDENT, {"due_at": "2026-08-22T18:00:00+08:00"})
    assert "tasks" not in memory.snapshot(STUDENT)


def test_stream_can_be_interrupted_between_chunks() -> None:
    async def scenario() -> list[dict]:
        event = asyncio.Event()
        events: list[dict] = []
        async for item in runtime().stream_chat(
            request("你好，讲个笑话"), cancel_event=event, chunk_size=5
        ):
            events.append(item)
            if item["event"] == "chunk":
                event.set()
        return events

    events = run(scenario())
    assert events[0]["event"] == "chunk"
    assert events[-1]["event"] == "interrupted"
    assert not any(event["event"] == "done" for event in events)


def test_inflight_tool_can_be_interrupted() -> None:
    async def scenario():
        service = FakeCampusService()
        service.delays["get_today_brief"] = 0.2
        event = asyncio.Event()
        pending = asyncio.create_task(
            runtime(service).chat(request("今天有什么事情？"), cancel_event=event)
        )
        await asyncio.sleep(0.01)
        event.set()
        return await pending

    response = run(scenario())
    assert response.ok is False
    assert response.error.details["reason"] == "interrupted"
    assert response.traces[0].status == "interrupted"
