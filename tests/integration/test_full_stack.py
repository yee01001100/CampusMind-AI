from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from apps.api.integration import SQLiteServiceRepository, create_integrated_app


SHANGHAI = ZoneInfo("Asia/Shanghai")
FIXED_NOW = datetime(2026, 8, 21, 9, 0, tzinfo=SHANGHAI)
STUDENT_ID = "student-demo-001"


@pytest.fixture()
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "campusmind.sqlite3"


@pytest.fixture()
def client(database_path: Path) -> TestClient:
    app = create_integrated_app(database_path=database_path, clock=lambda: FIXED_NOW)
    return TestClient(app, raise_server_exceptions=False)


def unwrap(response):
    payload = response.json()
    assert response.status_code < 400, payload
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["request_id"] == response.headers["X-Request-ID"]
    return payload["data"]


def test_integrated_app_uses_sqlite_demo_data(client: TestClient):
    health = unwrap(client.get("/api/health"))
    assert health["status"] == "ok"
    assert isinstance(client.app.state.repository, SQLiteServiceRepository)

    brief = unwrap(
        client.get(
            "/api/v1/brief/today",
            params={"student_id": STUDENT_ID, "date": "2026-08-21"},
        )
    )
    assert brief["courses"][0]["name"] == "职业生涯规划"
    assert len(brief["tasks"]) == 8
    assert brief["notices"]
    assert brief["suggestions"]


def test_integrated_app_requires_explicit_online_model_opt_in(database_path: Path):
    app = create_integrated_app(
        database_path=database_path,
        clock=lambda: FIXED_NOW,
        environ={"DEEPSEEK_API_KEY": "test-key-not-a-secret"},
    )
    guarded_client = TestClient(app, raise_server_exceptions=False)

    response = unwrap(
        guarded_client.post(
            "/api/v1/chat",
            json={"student_id": STUDENT_ID, "message": "你好"},
        )
    )

    assert app.state.model_mode == "local-rules"
    assert response["runtime_mode"] == "local-rules"


def test_notice_to_task_is_deduplicated_and_persisted(
    client: TestClient, database_path: Path
):
    notice_text = "2026年8月22日18:00前，要求：提交模拟报名材料"
    body = {
        "text": notice_text,
        "student_id": STUDENT_ID,
        "reference_time": FIXED_NOW.isoformat(),
        "candidate": {"confidence": 0.7},
    }
    first = unwrap(client.post("/api/v1/notices/parse", json=body))
    assert first["duplicate"] is False
    assert first["notice"]["raw_text"] == notice_text
    assert first["notice"]["needs_confirmation"] is True
    assert first["tasks"] == []

    notice = first["notice"]
    create_body = {
        "student_id": STUDENT_ID,
        "title": notice["actions"][0],
        "description": f"来自通知 {notice['id']}",
        "task_type": "registration",
        "priority": notice["priority"],
        "due_at": notice["deadline"],
        "source_notice_id": notice["id"],
        "dedupe_key": f"{STUDENT_ID}:{notice['id']}:registration",
    }
    created = unwrap(client.post("/api/v1/tasks", json=create_body))
    assert created["created"] is True
    task_id = created["task"]["id"]
    repeated_task = unwrap(client.post("/api/v1/tasks", json=create_body))
    assert repeated_task["created"] is False
    assert repeated_task["duplicate_of"] == task_id

    duplicate = unwrap(client.post("/api/v1/notices/parse", json=body))
    assert duplicate["duplicate"] is True
    assert duplicate["tasks"][0]["id"] == task_id

    due_before_completion = unwrap(
        client.get(
            "/api/v1/reminders/due",
            params={
                "student_id": STUDENT_ID,
                "at": "2026-08-22T16:00:00+08:00",
            },
        )
    )
    assert any(item["task_id"] == task_id for item in due_before_completion)

    completed = unwrap(
        client.patch(
            f"/api/v1/tasks/{task_id}",
            params={"student_id": STUDENT_ID},
            json={"status": "completed"},
        )
    )
    assert completed["status"] == "completed"
    assert completed["completed_at"] is not None
    due_after_completion = unwrap(
        client.get(
            "/api/v1/reminders/due",
            params={
                "student_id": STUDENT_ID,
                "at": "2026-08-22T16:00:00+08:00",
            },
        )
    )
    assert not any(item["task_id"] == task_id for item in due_after_completion)

    restarted = TestClient(
        create_integrated_app(database_path=database_path, clock=lambda: FIXED_NOW),
        raise_server_exceptions=False,
    )
    tasks = unwrap(restarted.get("/api/v1/tasks", params={"student_id": STUDENT_ID}))
    assert next(item for item in tasks if item["id"] == task_id)["status"] == "completed"


def test_restoring_task_reactivates_its_future_reminders(client: TestClient):
    created = unwrap(
        client.post(
            "/api/v1/tasks",
            json={
                "student_id": STUDENT_ID,
                "title": "恢复提醒演示",
                "task_type": "assignment",
                "priority": "normal",
                "due_at": "2026-08-28T18:00:00+08:00",
                "dedupe_key": "integration:restore-reminders",
            },
        )
    )
    task_id = created["task"]["id"]
    reminder_ids = {item["id"] for item in created["reminders"]}

    unwrap(
        client.patch(
            f"/api/v1/tasks/{task_id}",
            params={"student_id": STUDENT_ID},
            json={"status": "completed"},
        )
    )
    unwrap(
        client.patch(
            f"/api/v1/tasks/{task_id}",
            params={"student_id": STUDENT_ID},
            json={"status": "pending"},
        )
    )

    repository = client.app.state.repository
    restored = [
        item
        for item in repository.list_reminders()
        if item.task_id == task_id and item.status == "pending"
    ]
    assert {item.id for item in restored} == reminder_ids


def test_agent_today_brief_calls_real_sqlite_service(client: TestClient):
    data = unwrap(
        client.post(
            "/api/v1/chat",
            json={"student_id": STUDENT_ID, "message": "今天有什么事情？"},
        )
    )
    assert data["runtime_mode"] == "local-rules"
    assert data["result"]["courses"][0]["id"] == "course-demo-007"
    assert data["traces"][0]["name"] == "get_today_brief"
    assert data["traces"][0]["status"] == "success"


def test_agent_rag_returns_sources_and_refuses_unknown_rules(client: TestClient):
    sourced = unwrap(
        client.post(
            "/api/v1/chat",
            json={"student_id": STUDENT_ID, "message": "奖学金规定是什么？"},
        )
    )
    assert sourced["result"]["sources"]
    assert sourced["result"]["sources"][0]["is_demo"] is True

    missing = client.post(
        "/api/v1/chat",
        json={"student_id": STUDENT_ID, "message": "学校规定火星停车怎么办？"},
    )
    payload = missing.json()
    assert missing.status_code == 400
    assert payload["ok"] is False
    assert payload["error"]["code"] == "RAG_NO_SOURCE"


@pytest.mark.parametrize("round_number", [1, 2, 3])
def test_four_core_scenarios_are_repeatable(client: TestClient, round_number: int):
    brief = unwrap(
        client.post(
            "/api/v1/chat",
            json={"student_id": STUDENT_ID, "message": "今天有什么事情？"},
        )
    )
    assert brief["traces"][0]["status"] == "success"

    notice_text = f"2026年8月28日18:00前，要求：提交第{round_number}轮模拟材料"
    parsed = unwrap(
        client.post(
            "/api/v1/notices/parse",
            json={
                "text": notice_text,
                "student_id": STUDENT_ID,
                "reference_time": FIXED_NOW.isoformat(),
                "candidate": {"confidence": 0.7},
            },
        )
    )
    assert parsed["notice"]["needs_confirmation"] is True
    notice = parsed["notice"]
    created = unwrap(
        client.post(
            "/api/v1/tasks",
            json={
                "student_id": STUDENT_ID,
                "title": notice["actions"][0],
                "description": f"来自通知 {notice['id']}",
                "task_type": "assignment",
                "priority": notice["priority"],
                "due_at": notice["deadline"],
                "source_notice_id": notice["id"],
                "dedupe_key": f"{STUDENT_ID}:{notice['id']}:round-{round_number}",
            },
        )
    )
    assert created["created"] is True

    rag = unwrap(
        client.post(
            "/api/v1/chat",
            json={"student_id": STUDENT_ID, "message": "奖学金规定是什么？"},
        )
    )
    assert rag["result"]["sources"]

    task_id = created["task"]["id"]
    updated = unwrap(
        client.patch(
            f"/api/v1/tasks/{task_id}",
            params={"student_id": STUDENT_ID},
            json={"status": "completed"},
        )
    )
    assert updated["status"] == "completed"
