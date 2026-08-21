from __future__ import annotations

import asyncio

from campusmind.tools import TOOL_NAMES, CampusToolRegistry, ToolServiceError

from .fakes import FakeCampusService


STUDENT = "student-demo-001"


def run(coro):
    return asyncio.run(coro)


def test_all_five_shared_tools_return_contract_shapes() -> None:
    service = FakeCampusService()
    tools = CampusToolRegistry(service)
    calls = {
        "get_today_brief": {
            "student_id": STUDENT,
            "date": "2026-08-21",
            "timezone": "Asia/Shanghai",
        },
        "parse_notice": {
            "text": "报名通知：截止到 2026-08-22 18:00。",
            "student_id": STUDENT,
            "reference_time": "2026-08-21T09:00:00+08:00",
        },
        "create_task": {
            "student_id": STUDENT,
            "title": "完成模拟报名",
            "description": None,
            "task_type": "registration",
            "priority": "high",
            "due_at": "2026-08-22T18:00:00+08:00",
            "source_notice_id": "notice-demo-001",
            "dedupe_key": "student-demo-001:notice-demo-001:registration",
        },
        "get_courses": {"student_id": STUDENT, "date": "2026-08-21"},
        "complete_task": {"student_id": STUDENT, "task_id": "task-demo-001"},
    }

    results = {name: run(tools.execute(name, calls[name])) for name in TOOL_NAMES}

    assert tuple(results) == TOOL_NAMES
    assert all(result.ok for result in results.values())
    assert results["create_task"].data["created"] is True
    assert results["complete_task"].data["status"] == "completed"


def test_validation_rejects_missing_fields_without_calling_service() -> None:
    service = FakeCampusService()
    result = run(CampusToolRegistry(service).execute("get_courses", {"student_id": ""}))
    assert result.ok is False
    assert result.error.code == "VALIDATION_ERROR"
    assert service.calls == []


def test_validation_rejects_naive_deadline() -> None:
    service = FakeCampusService()
    result = run(
        CampusToolRegistry(service).execute(
            "create_task",
            {
                "student_id": STUDENT,
                "title": "测试",
                "task_type": "general",
                "priority": "normal",
                "dedupe_key": "demo:test",
                "due_at": "2026-08-22T18:00:00",
            },
        )
    )
    assert result.error.code == "VALIDATION_ERROR"
    assert service.calls == []


def test_known_service_error_preserves_stable_code() -> None:
    service = FakeCampusService()
    service.failures["get_courses"] = ToolServiceError(
        "COURSE_NOT_FOUND", "没有模拟课程"
    )
    result = run(
        CampusToolRegistry(service).execute(
            "get_courses", {"student_id": STUDENT, "date": "2026-08-21"}
        )
    )
    assert result.error.code == "COURSE_NOT_FOUND"


def test_unknown_service_error_is_normalized() -> None:
    service = FakeCampusService()
    service.failures["get_courses"] = ToolServiceError("PRIVATE_CODE", "内部错误")
    result = run(
        CampusToolRegistry(service).execute(
            "get_courses", {"student_id": STUDENT, "date": "2026-08-21"}
        )
    )
    assert result.error.code == "AGENT_TOOL_FAILED"
    assert result.error.details["service_code"] == "PRIVATE_CODE"


def test_timeout_is_failure_not_success() -> None:
    service = FakeCampusService()
    service.delays["get_courses"] = 0.05
    result = run(
        CampusToolRegistry(service, default_timeout_seconds=0.005).execute(
            "get_courses", {"student_id": STUDENT, "date": "2026-08-21"}
        )
    )
    assert result.ok is False
    assert result.error.code == "AGENT_TOOL_FAILED"
    assert result.error.details["reason"] == "tool_timeout"


def test_malformed_service_result_is_failure() -> None:
    service = FakeCampusService()
    service.malformed_tool = "get_today_brief"
    result = run(
        CampusToolRegistry(service).execute(
            "get_today_brief",
            {
                "student_id": STUDENT,
                "date": "2026-08-21",
                "timezone": "Asia/Shanghai",
            },
        )
    )
    assert result.error.code == "AGENT_TOOL_FAILED"
    assert result.error.details["reason"] == "invalid_service_result"
