from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta
from typing import Protocol
from uuid import uuid4
from zoneinfo import ZoneInfo

from campusmind.services.task import ServiceError, TaskCreate, TaskService

from .models import Notice, NoticeCandidate, NoticeParseCommand, NoticeParseResult


class NoticeRepository(Protocol):
    def get_notice_by_source(self, source_key: str) -> Notice | None: ...
    def save_notice(self, source_key: str, notice: Notice) -> Notice: ...
    def list_tasks_for_notice(self, notice_id: str) -> list: ...


WEEKDAYS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "日": 7, "天": 7}


class NoticeService:
    def __init__(
        self,
        repository: NoticeRepository,
        task_service: TaskService,
        *,
        timezone: str = "Asia/Shanghai",
    ) -> None:
        self.repository = repository
        self.task_service = task_service
        self.timezone = ZoneInfo(timezone)

    def parse(self, command: NoticeParseCommand) -> NoticeParseResult:
        text = command.text.strip()
        if not text:
            raise ServiceError("NOTICE_EMPTY", "通知正文为空")

        reference_time = command.reference_time.astimezone(self.timezone)

        source_key = command.candidate.source_ref or hashlib.sha256(text.encode("utf-8")).hexdigest()
        existing = self.repository.get_notice_by_source(source_key)
        if existing is not None:
            return NoticeParseResult(
                notice=existing,
                tasks=self.repository.list_tasks_for_notice(existing.id),
                duplicate=True,
                expired=bool(existing.deadline and existing.deadline < reference_time),
                applicable=True,
            )

        deadline = command.candidate.deadline
        if deadline is not None:
            deadline = deadline.astimezone(self.timezone)
        else:
            deadline = self._extract_deadline(text, reference_time)
        audience = command.candidate.audience or self._extract_audience(text)
        applicable = self._is_applicable(audience, command.student_segments)
        if not applicable:
            raise ServiceError(
                "NOTICE_NOT_APPLICABLE",
                "通知不适用当前学生",
                details={"audience": audience},
            )
        actions = command.candidate.actions or self._extract_actions(text)
        confidence = command.candidate.confidence
        if confidence is None:
            confidence = 0.9 if deadline is not None else 0.7
        needs_confirmation = confidence < 0.75 or deadline is None
        expired = bool(deadline and deadline < reference_time)
        priority = command.candidate.priority or self.task_service.priority_for(
            deadline, reference_time
        )
        notice_id = f"notice-{uuid4().hex}"
        notice = Notice(
            id=notice_id,
            title=(command.candidate.title or self._title(text)),
            raw_text=text,
            audience=audience,
            published_at=command.candidate.published_at,
            deadline=deadline,
            actions=actions,
            priority=priority,
            source_type=command.candidate.source_type,
            source_ref=command.candidate.source_ref,
            confidence=confidence,
            needs_confirmation=needs_confirmation,
            created_at=reference_time,
        )
        self.repository.save_notice(source_key, notice)

        tasks = []
        if not expired and not needs_confirmation:
            for index, action in enumerate(actions):
                result = self.task_service.create(
                    TaskCreate(
                        student_id=command.student_id,
                        title=action,
                        description=f"来自通知：{notice.title}",
                        task_type=self._task_type(text, action),
                        priority=priority,
                        due_at=deadline,
                        source_notice_id=notice.id,
                        dedupe_key=f"{command.student_id}:{notice.id}:{index}:{self._slug(action)}",
                    ),
                    now=reference_time,
                )
                tasks.append(result.task)
        return NoticeParseResult(
            notice=notice,
            tasks=tasks,
            duplicate=False,
            expired=expired,
            applicable=True,
        )

    def _extract_deadline(self, text: str, reference: datetime) -> datetime | None:
        clock_match = re.search(r"(?P<hour>[01]?\d|2[0-3])[:：](?P<minute>[0-5]\d)", text)
        hour = int(clock_match.group("hour")) if clock_match else 23
        minute = int(clock_match.group("minute")) if clock_match else 59

        relative = re.search(r"本周([一二三四五六日天])", text)
        if relative:
            target_weekday = WEEKDAYS[relative.group(1)]
            day = reference.date() + timedelta(days=target_weekday - reference.isoweekday())
            return datetime.combine(
                day, datetime.min.time().replace(hour=hour, minute=minute), tzinfo=self.timezone
            )

        broad_explicit = re.search(
            r"(?P<year>20\d{2})[年/-](?P<month>\d{1,2})[月/-](?P<day>\d{1,2})日?",
            text,
        )
        if broad_explicit:
            try:
                return datetime(
                    int(broad_explicit.group("year")),
                    int(broad_explicit.group("month")),
                    int(broad_explicit.group("day")),
                    hour,
                    minute,
                    tzinfo=self.timezone,
                )
            except ValueError as exc:
                raise ServiceError(
                    "VALIDATION_ERROR", "通知日期无效", details={"field": "deadline"}
                ) from exc

        month_day = re.search(
            r"(?<!\d)(?P<month>1[0-2]|0?[1-9])月(?P<day>3[01]|[12]\d|0?[1-9])日",
            text,
        )
        if month_day:
            raise ServiceError(
                "NOTICE_DATE_AMBIGUOUS",
                "无法确认通知中的年份",
                details={"field": "deadline"},
            )
        return None

    @staticmethod
    def _extract_audience(text: str) -> list[str]:
        match = re.search(r"(20\d{2}级(?:本科生|研究生|学生))", text)
        return [match.group(1)] if match else []

    @staticmethod
    def _is_applicable(audience: list[str], student_segments: list[str]) -> bool:
        return not audience or not student_segments or bool(set(audience) & set(student_segments))

    @staticmethod
    def _extract_actions(text: str) -> list[str]:
        action_match = re.search(r"(?:行动|事项|要求)[：:](.+)", text)
        if action_match:
            actions = [part.strip(" 。") for part in re.split(r"[；;]", action_match.group(1))]
            return [action for action in actions if action]
        specific_verbs = ["报名", "提交", "缴费", "签到", "参加"]
        found = [verb for verb in specific_verbs if verb in text]
        if found:
            return [f"完成{verb}" for verb in found[:3]]
        if "完成" in text:
            return ["完成通知事项"]
        return ["查看并处理通知"]

    @staticmethod
    def _task_type(text: str, action: str) -> str:
        combined = text + action
        if "报名" in combined:
            return "registration"
        if "考试" in combined:
            return "exam"
        if "作业" in combined or "提交" in combined:
            return "assignment"
        if "课程" in combined or "上课" in combined:
            return "course"
        if "活动" in combined or "参加" in combined:
            return "activity"
        return "general"

    @staticmethod
    def _title(text: str) -> str:
        first_line = text.splitlines()[0].strip(" #【】")
        return (first_line[:80] or "校园通知")

    @staticmethod
    def _slug(value: str) -> str:
        return hashlib.sha1(value.encode("utf-8"), usedforsecurity=False).hexdigest()[:12]
