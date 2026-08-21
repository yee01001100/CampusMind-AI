"""Contract-compatible fake for Agent 1; replace with Agent 3 services."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any

from campusmind.tools import ToolServiceError


NOW = "2026-08-21T09:00:00+08:00"


def task(task_id: str = "task-demo-001", *, status: str = "pending") -> dict[str, Any]:
    return {
        "id": task_id,
        "student_id": "student-demo-001",
        "title": "完成模拟报名",
        "description": "仅用于自动化测试",
        "task_type": "registration",
        "priority": "high",
        "status": status,
        "due_at": "2026-08-22T18:00:00+08:00",
        "source_notice_id": "notice-demo-001",
        "dedupe_key": "student-demo-001:notice-demo-001:registration",
        "created_at": NOW,
        "completed_at": NOW if status == "completed" else None,
    }


def notice(*, needs_confirmation: bool = False) -> dict[str, Any]:
    return {
        "id": "notice-demo-001",
        "title": "模拟报名通知",
        "raw_text": "【模拟数据】请完成报名。",
        "audience": ["模拟学生"],
        "published_at": NOW,
        "deadline": None if needs_confirmation else "2026-08-22T18:00:00+08:00",
        "actions": ["完成模拟报名"],
        "priority": "high",
        "source_type": "demo",
        "source_ref": "demo://notice-demo-001",
        "confidence": 0.6 if needs_confirmation else 0.95,
        "needs_confirmation": needs_confirmation,
        "created_at": NOW,
    }


def course() -> dict[str, Any]:
    return {
        "id": "course-demo-001",
        "student_id": "student-demo-001",
        "name": "人工智能导论",
        "teacher": "模拟教师",
        "weekday": 5,
        "start_time": "10:00",
        "end_time": "11:35",
        "location": "模拟教学楼 A101",
        "start_week": 1,
        "end_week": 16,
        "week_pattern": "all",
        "custom_weeks": [],
    }


class FakeCampusService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.delays: dict[str, float] = {}
        self.failures: dict[str, Exception] = {}
        self.empty_brief = False
        self.rag_sources: list[dict[str, Any]] = []
        self.malformed_tool: str | None = None
        self.created_keys: set[str] = set()

    async def _before(self, name: str, arguments: dict[str, Any]) -> None:
        self.calls.append((name, deepcopy(arguments)))
        if self.delays.get(name):
            await asyncio.sleep(self.delays[name])
        if name in self.failures:
            raise self.failures[name]

    async def get_today_brief(
        self, *, student_id: str, date: str, timezone: str
    ) -> dict[str, Any]:
        await self._before(
            "get_today_brief",
            {"student_id": student_id, "date": date, "timezone": timezone},
        )
        if self.malformed_tool == "get_today_brief":
            return {"date": date}
        return {
            "date": date,
            "courses": [] if self.empty_brief else [course()],
            "tasks": [] if self.empty_brief else [task()],
            "notices": [],
            "conflicts": [],
            "suggestions": [],
        }

    async def parse_notice(
        self, *, text: str, student_id: str, reference_time: str
    ) -> dict[str, Any]:
        await self._before(
            "parse_notice",
            {
                "text": text,
                "student_id": student_id,
                "reference_time": reference_time,
            },
        )
        if "下周五" in text or "哪年" in text:
            raise ToolServiceError(
                "NOTICE_DATE_AMBIGUOUS",
                "无法确认模拟通知中的日期",
                {"field": "deadline"},
            )
        if "低置信度" in text:
            return notice(needs_confirmation=True)
        return notice()

    async def create_task(self, **values: Any) -> dict[str, Any]:
        await self._before("create_task", values)
        key = values["dedupe_key"]
        value = task()
        value.update({key: values[key] for key in values if key in value})
        if key in self.created_keys:
            raise ToolServiceError(
                "TASK_DUPLICATE", "模拟任务已存在", {"duplicate_of": value["id"]}
            )
        self.created_keys.add(key)
        return {"task": value, "created": True, "duplicate_of": None}

    async def get_courses(self, *, student_id: str, date: str) -> list[dict[str, Any]]:
        await self._before("get_courses", {"student_id": student_id, "date": date})
        return [course()]

    async def complete_task(self, *, student_id: str, task_id: str) -> dict[str, Any]:
        await self._before(
            "complete_task", {"student_id": student_id, "task_id": task_id}
        )
        if task_id == "task-missing":
            raise ToolServiceError("TASK_NOT_FOUND", "模拟任务不存在")
        return task(task_id, status="completed")

    async def search_knowledge(self, *, query: str, student_id: str) -> dict[str, Any]:
        await self._before(
            "rag_search", {"query": query, "student_id": student_id}
        )
        return {
            "answer": "模拟规则答案",
            "sources": deepcopy(self.rag_sources),
        }
