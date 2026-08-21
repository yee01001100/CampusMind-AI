from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from apps.api.main import create_app

from .conftest import NOW


def assert_envelope(response, *, ok: bool) -> dict:
    payload = response.json()
    assert set(payload) == {"ok", "data", "error", "request_id"}
    assert payload["ok"] is ok
    assert payload["request_id"].startswith("req-")
    assert response.headers["X-Request-ID"] == payload["request_id"]
    if ok:
        assert payload["error"] is None
    else:
        assert payload["data"] is None
        assert set(payload["error"]) == {"code", "message", "details"}
    return payload


def test_health_and_request_id_passthrough(client) -> None:
    response = client.get("/api/health", headers={"X-Request-ID": "req-browser-001"})
    payload = assert_envelope(response, ok=True)
    assert payload["request_id"] == "req-browser-001"
    assert payload["data"]["timezone"] == "Asia/Shanghai"


def test_all_nine_operations_exist_in_openapi(client) -> None:
    schema = client.get("/openapi.json").json()
    operations = {
        (method, path)
        for path, item in schema["paths"].items()
        for method in item
        if method in {"get", "post", "patch"}
    }
    assert operations == {
        ("get", "/api/health"),
        ("get", "/api/v1/brief/today"),
        ("post", "/api/v1/notices/parse"),
        ("get", "/api/v1/courses/today"),
        ("post", "/api/v1/tasks"),
        ("get", "/api/v1/tasks"),
        ("patch", "/api/v1/tasks/{task_id}"),
        ("get", "/api/v1/reminders/due"),
        ("post", "/api/v1/chat"),
    }


def test_courses_and_empty_lists_are_not_500(client) -> None:
    present = client.get(
        "/api/v1/courses/today",
        params={"student_id": "student-demo-001", "date": "2026-08-18"},
    )
    assert assert_envelope(present, ok=True)["data"]["courses"][0]["id"] == "course-demo-001"
    empty = client.get(
        "/api/v1/courses/today",
        params={"student_id": "student-demo-001", "date": "2026-08-19"},
    )
    assert empty.status_code == 200
    assert assert_envelope(empty, ok=True)["data"]["courses"] == []


def test_task_create_list_duplicate_patch_and_due_reminders(client) -> None:
    body = {
        "student_id": "student-demo-001",
        "title": "提交课程作业",
        "task_type": "assignment",
        "due_at": (NOW + timedelta(days=4)).isoformat(),
        "source_notice_id": "notice-demo-001",
        "dedupe_key": "student-demo-001:assignment:one",
    }
    created = client.post("/api/v1/tasks", json=body)
    created_payload = assert_envelope(created, ok=True)["data"]
    assert created.status_code == 201
    assert created_payload["created"] is True
    task_id = created_payload["task"]["id"]

    duplicate = client.post("/api/v1/tasks", json=body)
    assert duplicate.status_code == 200
    assert assert_envelope(duplicate, ok=True)["data"]["duplicate_of"] == task_id

    listed = client.get("/api/v1/tasks", params={"student_id": "student-demo-001"})
    assert len(assert_envelope(listed, ok=True)["data"]) == 1

    completed = client.patch(
        f"/api/v1/tasks/{task_id}",
        params={"student_id": "student-demo-001"},
        json={"status": "completed"},
    )
    assert assert_envelope(completed, ok=True)["data"]["status"] == "completed"
    due = client.get(
        "/api/v1/reminders/due",
        params={"student_id": "student-demo-001", "at": (NOW + timedelta(days=5)).isoformat()},
    )
    assert assert_envelope(due, ok=True)["data"] == []


def test_notice_to_brief_to_complete_end_to_end(client) -> None:
    parsed = client.post(
        "/api/v1/notices/parse",
        json={
            "text": "模拟报名：请在 2026年8月22日 18:00 完成报名",
            "student_id": "student-demo-001",
            "reference_time": NOW.isoformat(),
            "student_segments": ["2026级本科生"],
            "candidate": {"source_type": "demo", "confidence": 0.96},
        },
    )
    data = assert_envelope(parsed, ok=True)["data"]
    assert len(data["tasks"]) == 1
    task_id = data["tasks"][0]["id"]

    brief = client.get("/api/v1/brief/today", params={"student_id": "student-demo-001"})
    brief_data = assert_envelope(brief, ok=True)["data"]
    assert any(item["id"] == task_id for item in brief_data["tasks"])
    assert brief_data["notices"][0]["raw_text"].startswith("模拟报名")

    completed = client.patch(f"/api/v1/tasks/{task_id}", json={"status": "completed"})
    assert assert_envelope(completed, ok=True)["data"]["completed_at"] is not None
    due = client.get(
        "/api/v1/reminders/due",
        params={"student_id": "student-demo-001", "at": "2026-08-23T00:00:00+08:00"},
    )
    assert assert_envelope(due, ok=True)["data"] == []


def test_chat_uses_replaceable_local_facade(client) -> None:
    response = client.post(
        "/api/v1/chat",
        json={"student_id": "student-demo-001", "message": "今天有什么事情？"},
    )
    data = assert_envelope(response, ok=True)["data"]
    assert data["mode"] == "local_stub"
    assert data["tool_calls"] == ["get_today_brief"]
    assert "1 节课" in data["answer"]


def test_stable_business_and_validation_errors(client) -> None:
    empty_notice = client.post(
        "/api/v1/notices/parse",
        json={"text": "", "student_id": "student-demo-001", "reference_time": NOW.isoformat()},
    )
    assert empty_notice.status_code == 400
    assert assert_envelope(empty_notice, ok=False)["error"]["code"] == "NOTICE_EMPTY"

    ambiguous = client.post(
        "/api/v1/notices/parse",
        json={"text": "请在8月22日报名", "student_id": "student-demo-001", "reference_time": NOW.isoformat()},
    )
    assert assert_envelope(ambiguous, ok=False)["error"]["code"] == "NOTICE_DATE_AMBIGUOUS"

    missing = client.patch("/api/v1/tasks/does-not-exist", json={"status": "completed"})
    assert missing.status_code == 404
    assert assert_envelope(missing, ok=False)["error"]["code"] == "TASK_NOT_FOUND"

    invalid = client.post("/api/v1/tasks", json={"student_id": "student-demo-001"})
    assert invalid.status_code == 422
    assert assert_envelope(invalid, ok=False)["error"]["code"] == "VALIDATION_ERROR"


def test_unknown_exception_is_sanitized(api_repository, monkeypatch) -> None:
    app = create_app(repository=api_repository, clock=lambda: NOW)
    monkeypatch.setattr(
        app.state.services.courses,
        "for_day",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("secret stack detail")),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/brief/today", params={"student_id": "student-demo-001"})
    payload = assert_envelope(response, ok=False)
    assert response.status_code == 500
    assert payload["error"]["code"] == "INTERNAL_ERROR"
    assert "secret stack detail" not in response.text
    assert "traceback" not in response.text.lower()


def test_framework_404_and_405_use_the_shared_error_envelope(client) -> None:
    missing = client.get("/api/v1/not-a-real-route")
    wrong_method = client.get("/api/v1/chat")

    assert missing.status_code == 404
    assert assert_envelope(missing, ok=False)["error"]["code"] == "NOT_FOUND"
    assert wrong_method.status_code == 405
    assert assert_envelope(wrong_method, ok=False)["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_cors_is_limited_to_documented_dev_origins(client) -> None:
    allowed = client.options(
        "/api/v1/tasks",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    qa_allowed = client.options(
        "/api/v1/tasks",
        headers={
            "Origin": "http://127.0.0.1:4173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert qa_allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:4173"
    blocked = client.options(
        "/api/v1/tasks",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in blocked.headers
