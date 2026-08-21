"""Production composition for SQLite, campus services, Runtime and RAG."""

from __future__ import annotations

import hashlib
import os
import re
from collections.abc import Callable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from campusmind.domain import (
    Course as DomainCourse,
    Notice as DomainNotice,
    Reminder as DomainReminder,
    StudentProfile as DomainStudentProfile,
    Task as DomainTask,
)
from campusmind.repositories import (
    CourseRepository,
    KnowledgeImporter,
    NoticeRepository,
    RAGNoSourceError,
    RAGRetriever,
    ReminderRepository,
    StudentProfileRepository,
    TaskRepository,
)
from campusmind.services.course import Course as ServiceCourse
from campusmind.services.course import CourseService
from campusmind.services.notice import Notice as ServiceNotice
from campusmind.services.notice import NoticeCandidate, NoticeParseCommand, NoticeService
from campusmind.services.reminder import Reminder as ServiceReminder
from campusmind.services.reminder import ReminderService
from campusmind.services.reminder import StudentProfile as ServiceStudentProfile
from campusmind.services.task import (
    ServiceError,
    Task as ServiceTask,
    TaskCreate,
    TaskService,
)
from campusmind.services.task.models import TaskListQuery
from campusmind.storage import SQLiteDatabase, load_demo_data

from .agent import AgentChatFacade, build_agent_runtime
from .chat import ChatRequest
from .main import create_app, shanghai_now

SHANGHAI = ZoneInfo("Asia/Shanghai")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _convert(model: Any, target: type[Any]) -> Any:
    return target.model_validate(model.model_dump(mode="python"))


class SQLiteServiceRepository:
    """Narrow adapter expected by Agent 3, backed by Agent 2 repositories."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database
        self.tasks = TaskRepository(database)
        self.courses = CourseRepository(database)
        self.notices = NoticeRepository(database)
        self.profiles = StudentProfileRepository(database)
        self.reminders = ReminderRepository(database)

    def get_task(self, task_id: str) -> ServiceTask | None:
        task = self.tasks.get(task_id)
        return _convert(task, ServiceTask) if task else None

    def get_task_by_dedupe(self, dedupe_key: str) -> ServiceTask | None:
        task = self.tasks.get_by_dedupe_key(dedupe_key)
        return _convert(task, ServiceTask) if task else None

    def list_tasks(self, student_id: str) -> list[ServiceTask]:
        return [_convert(item, ServiceTask) for item in self.tasks.list_for_student(student_id)]

    def save_task(self, task: ServiceTask) -> ServiceTask:
        stored = self.tasks.save(_convert(task, DomainTask))
        return _convert(stored, ServiceTask)

    def list_courses(self, student_id: str) -> list[ServiceCourse]:
        return [_convert(item, ServiceCourse) for item in self.courses.list_for_student(student_id)]

    def save_course(self, course: ServiceCourse) -> ServiceCourse:
        return _convert(self.courses.save(_convert(course, DomainCourse)), ServiceCourse)

    @staticmethod
    def _source_matches(source_key: str, notice: DomainNotice) -> bool:
        if notice.source_ref == source_key:
            return True
        digest = hashlib.sha256(notice.raw_text.encode("utf-8")).hexdigest()
        return digest == source_key

    def get_notice_by_source(self, source_key: str) -> ServiceNotice | None:
        notice = next(
            (item for item in self.notices.list_all() if self._source_matches(source_key, item)),
            None,
        )
        return _convert(notice, ServiceNotice) if notice else None

    def save_notice(self, source_key: str, notice: ServiceNotice) -> ServiceNotice:
        stored, _ = self.notices.create(_convert(notice, DomainNotice))
        return _convert(stored, ServiceNotice)

    def list_notices(self) -> list[ServiceNotice]:
        return [_convert(item, ServiceNotice) for item in self.notices.list_all()]

    def list_tasks_for_notice(self, notice_id: str) -> list[ServiceTask]:
        return [_convert(item, ServiceTask) for item in self.tasks.list_for_notice(notice_id)]

    def get_profile(self, student_id: str) -> ServiceStudentProfile | None:
        profile = self.profiles.get(student_id)
        return _convert(profile, ServiceStudentProfile) if profile else None

    def save_profile(self, profile: ServiceStudentProfile) -> ServiceStudentProfile:
        stored = self.profiles.save(_convert(profile, DomainStudentProfile))
        return _convert(stored, ServiceStudentProfile)

    def list_reminders(self) -> list[ServiceReminder]:
        return [_convert(item, ServiceReminder) for item in self.reminders.list_all()]

    def save_reminder(self, reminder: ServiceReminder) -> ServiceReminder:
        stored = self.reminders.save(_convert(reminder, DomainReminder))
        return _convert(stored, ServiceReminder)


class IntegratedCampusService:
    """Async Tool surface using the same SQLite-backed services as FastAPI."""

    def __init__(
        self,
        repository: SQLiteServiceRepository,
        rag: RAGRetriever,
        *,
        clock: Callable[[], datetime] = shanghai_now,
    ) -> None:
        self.repository = repository
        self.rag = rag
        self.clock = clock
        self.tasks = TaskService(repository)
        self.courses = CourseService(repository)
        self.reminders = ReminderService(repository)
        self.notices = NoticeService(repository, self.tasks)

    def _brief(self, student_id: str, selected: date) -> dict[str, Any]:
        now = self.clock()
        course_result = self.courses.for_day(student_id, selected, now=now)
        tasks = self.tasks.list(TaskListQuery(student_id=student_id), now=now)
        notice_ids = {task.source_notice_id for task in tasks if task.source_notice_id}
        notices = [item for item in self.repository.list_notices() if item.id in notice_ids]
        conflicts: list[str] = []
        ordered = sorted(course_result.courses, key=lambda item: item.start_time)
        for left, right in zip(ordered, ordered[1:]):
            if left.end_time > right.start_time:
                conflicts.append(
                    f"{left.name}与{right.name}在 {right.start_time}–{left.end_time} 重叠"
                )
        pending = [task for task in tasks if task.status == "pending"]
        suggestions = []
        if pending:
            suggestions.append(f"优先处理：{pending[0].title}")
        return {
            "date": selected.isoformat(),
            "courses": [item.model_dump(mode="json") for item in course_result.courses],
            "tasks": [item.model_dump(mode="json") for item in tasks],
            "notices": [item.model_dump(mode="json") for item in notices],
            "conflicts": conflicts,
            "suggestions": suggestions,
        }

    async def get_today_brief(self, *, student_id: str, date: str, timezone: str):
        if timezone != "Asia/Shanghai":
            raise ServiceError("VALIDATION_ERROR", "timezone 必须为 Asia/Shanghai")
        return self._brief(student_id, selected=date_from_iso(date))

    async def parse_notice(self, *, text: str, student_id: str, reference_time: str):
        result = self.notices.parse(
            NoticeParseCommand(
                text=text,
                student_id=student_id,
                reference_time=datetime.fromisoformat(reference_time.replace("Z", "+00:00")),
                candidate=NoticeCandidate(confidence=0.7),
            )
        )
        return result.notice.model_dump(mode="json")

    async def create_task(self, **task: Any):
        result = self.tasks.create(TaskCreate.model_validate(task), now=self.clock())
        if result.created:
            self.reminders.schedule(result.task, now=self.clock())
        return result.model_dump(mode="json")

    async def get_courses(self, *, student_id: str, date: str):
        result = self.courses.for_day(student_id, date_from_iso(date), now=self.clock())
        return [item.model_dump(mode="json") for item in result.courses]

    async def complete_task(self, *, student_id: str, task_id: str):
        updated = self.tasks.complete(task_id, student_id=student_id, now=self.clock())
        self.reminders.cancel_for_task(task_id)
        return updated.model_dump(mode="json")

    async def search_knowledge(self, *, query: str, student_id: str):
        del student_id
        try:
            matches = self.rag.search(query, as_of=self.clock().date())
        except RAGNoSourceError:
            simplified = re.sub(
                r"(?:学校|校方|规定|政策|要求|是什么|有哪些|怎么办|请问|[？?])",
                "",
                query,
            ).strip()
            if not simplified or simplified == query.strip():
                return {"answer": "", "sources": []}
            try:
                matches = self.rag.search(simplified, as_of=self.clock().date())
            except RAGNoSourceError:
                return {"answer": "", "sources": []}
        sources = []
        for match in matches:
            source = match.source.model_dump(mode="json")
            source["snippet"] = match.snippet
            sources.append(source)
        return {"answer": matches[0].snippet, "sources": sources}


class IntegratedChatFacade:
    def __init__(self, facade: AgentChatFacade, *, clock: Callable[[], datetime]) -> None:
        self.facade = facade
        self.clock = clock

    async def reply(self, request: ChatRequest, brief: Mapping[str, Any]) -> dict[str, Any]:
        del brief
        envelope = await self.facade.chat(
            {
                "student_id": request.student_id,
                "message": request.message,
                "reference_time": self.clock().isoformat(),
                "timezone": "Asia/Shanghai",
            }
        )
        if not envelope["ok"]:
            error = envelope.get("error") or {}
            raise ServiceError(
                error.get("code", "AGENT_TOOL_FAILED"),
                error.get("message", "Agent 执行失败"),
                details=error.get("details", {}),
                status_code=503 if error.get("code") == "MODEL_UNAVAILABLE" else 400,
            )
        return envelope["data"]


def date_from_iso(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ServiceError("VALIDATION_ERROR", "date 必须使用 YYYY-MM-DD") from exc


def _resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def create_integrated_app(
    *,
    database_path: str | Path | None = None,
    demo_directory: str | Path | None = None,
    knowledge_directory: str | Path | None = None,
    clock: Callable[[], datetime] = shanghai_now,
    environ: Mapping[str, str] | None = None,
):
    env = os.environ if environ is None else environ
    model_mode = env.get("CAMPUSMIND_MODEL_MODE", "local-rules").strip().lower()
    if model_mode not in {"local-rules", "deepseek"}:
        raise ValueError("CAMPUSMIND_MODEL_MODE must be local-rules or deepseek")
    runtime_env = dict(env)
    if model_mode == "local-rules":
        runtime_env.pop("DEEPSEEK_API_KEY", None)
    selected_database = _resolve_path(
        database_path or env.get("CAMPUSMIND_DB_PATH", "data/local/campusmind.db")
    )
    database = SQLiteDatabase(selected_database)
    load_demo_data(database, _resolve_path(demo_directory or "data/demo"))
    KnowledgeImporter(database).import_directory(
        _resolve_path(knowledge_directory or "data/knowledge")
    )
    repository = SQLiteServiceRepository(database)
    tool_service = IntegratedCampusService(repository, RAGRetriever(database), clock=clock)
    runtime = build_agent_runtime(tool_service, environ=runtime_env)
    chat = IntegratedChatFacade(AgentChatFacade(runtime), clock=clock)
    api = create_app(repository=repository, chat_facade=chat, clock=clock)
    api.state.database = database
    api.state.integration_mode = "sqlite-runtime-rag"
    api.state.model_mode = model_mode
    return api


app = create_integrated_app()
