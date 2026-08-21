"""Small replaceable chat facade until Agent 1 supplies the real runtime."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from campusmind.services.task.models import ContractModel


class ChatRequest(ContractModel):
    student_id: str
    message: str = Field(min_length=1, max_length=2000)


class RuleBasedChatFacade:
    """Routes demo questions to API data without pretending to be an LLM."""

    def reply(self, request: ChatRequest, brief: dict[str, Any]) -> dict[str, Any]:
        normalized = request.message.strip().lower()
        asks_today = any(token in normalized for token in ("今天", "today", "什么事", "安排"))
        if asks_today:
            course_count = len(brief["courses"])
            task_count = len(brief["tasks"])
            return {
                "answer": f"今天有 {course_count} 节课、{task_count} 个任务。",
                "mode": "local_stub",
                "tool_calls": ["get_today_brief"],
                "brief": brief,
            }
        return {
            "answer": "当前本地演示助手可查询今日课程和任务；真实模型由 Agent 0 接入。",
            "mode": "local_stub",
            "tool_calls": [],
            "brief": None,
        }
