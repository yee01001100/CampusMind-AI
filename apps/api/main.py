"""FastAPI composition root for the nine frozen CampusMind endpoints."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any, Literal
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from campusmind.services.course import CourseService
from campusmind.services.notice import NoticeParseCommand, NoticeService
from campusmind.services.reminder import ReminderService
from campusmind.services.task import ServiceError, TaskCreate, TaskPatch, TaskService
from campusmind.services.task.models import TaskListQuery

from .chat import ChatRequest, RuleBasedChatFacade
from .fakes import InMemoryRepository

SHANGHAI = ZoneInfo("Asia/Shanghai")
DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def shanghai_now() -> datetime:
    return datetime.now(SHANGHAI)


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req-{uuid4().hex}")


def success(request: Request, data: Any, *, status_code: int = 200) -> JSONResponse:
    current_request_id = request_id(request)
    return JSONResponse(
        status_code=status_code,
        headers={"X-Request-ID": current_request_id},
        content=jsonable_encoder(
            {"ok": True, "data": data, "error": None, "request_id": current_request_id}
        ),
    )


def failure(
    request: Request,
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    status_code: int,
) -> JSONResponse:
    current_request_id = request_id(request)
    return JSONResponse(
        status_code=status_code,
        headers={"X-Request-ID": current_request_id},
        content=jsonable_encoder(
            {
                "ok": False,
                "data": None,
                "error": {"code": code, "message": message, "details": details or {}},
                "request_id": current_request_id,
            }
        ),
    )


class ServiceContainer:
    def __init__(self, repository: InMemoryRepository) -> None:
        self.repository = repository
        self.tasks = TaskService(repository)
        self.courses = CourseService(repository)
        self.reminders = ReminderService(repository)
        self.notices = NoticeService(repository, self.tasks)


def create_app(
    *,
    repository: InMemoryRepository | None = None,
    chat_facade: RuleBasedChatFacade | None = None,
    clock: Callable[[], datetime] = shanghai_now,
) -> FastAPI:
    repo = repository or InMemoryRepository()
    services = ServiceContainer(repo)
    chat = chat_facade or RuleBasedChatFacade()
    api = FastAPI(
        title="CampusMind API",
        version="0.1.0",
        description="Campus service/API slice. Storage and Agent runtime are replaceable adapters.",
    )
    api.state.services = services
    api.state.repository = repo
    api.state.chat_facade = chat
    api.state.clock = clock
    api.add_middleware(
        CORSMiddleware,
        allow_origins=list(DEV_ORIGINS),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    @api.middleware("http")
    async def attach_request_id(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "").strip()
        request.state.request_id = incoming[:128] if incoming else f"req-{uuid4().hex}"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @api.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError):
        return failure(
            request,
            code=exc.code,
            message=exc.message,
            details=exc.details,
            status_code=exc.status_code,
        )

    @api.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        fields = [".".join(str(part) for part in item["loc"]) for item in exc.errors()]
        return failure(
            request,
            code="VALIDATION_ERROR",
            message="输入字段无效",
            details={"fields": fields},
            status_code=422,
        )

    @api.exception_handler(Exception)
    async def internal_error_handler(request: Request, exc: Exception):
        return failure(
            request,
            code="INTERNAL_ERROR",
            message="服务暂时不可用",
            details={},
            status_code=500,
        )

    def build_brief(student_id: str, day: date, now: datetime) -> dict[str, Any]:
        course_result = services.courses.for_day(student_id, day, now=now)
        tasks = services.tasks.list(TaskListQuery(student_id=student_id), now=now)
        notices = [
            item
            for item in repo.list_notices()
            if any(task.source_notice_id == item.id for task in tasks)
        ]
        return {
            "date": day.isoformat(),
            "courses": course_result.courses,
            "tasks": tasks,
            "notices": notices,
            "conflicts": [],
            "suggestions": ["先处理高优先级任务"] if tasks else [],
        }

    @api.get("/api/health", tags=["system"])
    async def health(request: Request):
        return success(
            request,
            {"status": "ok", "service": "campusmind-api", "timezone": "Asia/Shanghai"},
        )

    @api.get("/api/v1/brief/today", tags=["brief"])
    async def today_brief(
        request: Request,
        student_id: str,
        day: date | None = Query(default=None, alias="date"),
    ):
        now = clock()
        return success(request, build_brief(student_id, day or now.date(), now))

    @api.post("/api/v1/notices/parse", tags=["notices"])
    async def parse_notice(request: Request, body: NoticeParseCommand):
        result = services.notices.parse(body)
        reminders = []
        for task in result.tasks:
            reminders.extend(services.reminders.schedule(task, now=body.reference_time))
        payload = result.model_dump()
        payload["reminders"] = reminders
        return success(request, payload, status_code=201 if not result.duplicate else 200)

    @api.get("/api/v1/courses/today", tags=["courses"])
    async def today_courses(
        request: Request,
        student_id: str,
        day: date | None = Query(default=None, alias="date"),
    ):
        now = clock()
        return success(
            request, services.courses.for_day(student_id, day or now.date(), now=now)
        )

    @api.post("/api/v1/tasks", tags=["tasks"])
    async def create_task(request: Request, body: TaskCreate):
        now = clock()
        result = services.tasks.create(body, now=now)
        reminders = services.reminders.schedule(result.task, now=now) if result.created else []
        payload = result.model_dump()
        payload["reminders"] = reminders
        return success(request, payload, status_code=201 if result.created else 200)

    @api.get("/api/v1/tasks", tags=["tasks"])
    async def list_tasks(
        request: Request,
        student_id: str,
        status: Literal["pending", "completed", "cancelled"] | None = None,
        task_type: Literal[
            "registration", "exam", "assignment", "course", "activity", "general"
        ]
        | None = None,
        overdue: bool | None = None,
        sort: Literal["due_at", "priority", "created_at"] = "due_at",
    ):
        query = TaskListQuery(
            student_id=student_id,
            status=status,
            task_type=task_type,
            overdue=overdue,
            sort=sort,
        )
        return success(request, services.tasks.list(query, now=clock()))

    @api.patch("/api/v1/tasks/{task_id}", tags=["tasks"])
    async def patch_task(
        request: Request,
        task_id: str,
        body: TaskPatch,
        student_id: str | None = None,
    ):
        now = clock()
        updated = services.tasks.update(task_id, body, now=now, student_id=student_id)
        if updated.status in {"completed", "cancelled"}:
            services.reminders.cancel_for_task(updated.id)
        elif updated.status == "pending":
            services.reminders.schedule(updated, now=now)
        return success(request, updated)

    @api.get("/api/v1/reminders/due", tags=["reminders"])
    async def due_reminders(
        request: Request,
        student_id: str,
        at: datetime | None = None,
    ):
        selected_at = at or clock()
        if selected_at.tzinfo is None:
            raise ServiceError(
                "VALIDATION_ERROR",
                "at 必须包含时区偏移",
                details={"field": "at"},
            )
        return success(request, services.reminders.due(student_id=student_id, at=selected_at))

    @api.post("/api/v1/chat", tags=["chat"])
    async def chat_endpoint(request: Request, body: ChatRequest):
        now = clock()
        brief = build_brief(body.student_id, now.date(), now)
        return success(request, chat.reply(body, jsonable_encoder(brief)))

    return api


app = create_app()
