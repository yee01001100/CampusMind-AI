"""CampusMind chat runtime with deterministic campus routing and safe fallback."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import Any, AsyncIterator, Mapping
from uuid import uuid4

from campusmind.tools import CampusToolRegistry, ToolError, ToolResult, ToolTrace

from .memory import PreferenceMemory
from .model_client import ChatModelClient, ModelUnavailableError


SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")


@dataclass(slots=True)
class AgentRequest:
    message: str
    student_id: str
    request_id: str = field(default_factory=lambda: f"req-{uuid4().hex}")
    reference_time: str | None = None
    timezone: str = "Asia/Shanghai"
    context: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AgentResponse:
    ok: bool
    message: str
    request_id: str
    data: Any = None
    error: ToolError | None = None
    traces: tuple[ToolTrace, ...] = ()
    needs_confirmation: bool = False
    runtime_mode: str = "local-rules"

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "data": {
                "message": self.message,
                "result": self.data,
                "traces": [trace.to_dict() for trace in self.traces],
                "needs_confirmation": self.needs_confirmation,
                "runtime_mode": self.runtime_mode,
            }
            if self.ok
            else None,
            "error": self.error.to_dict() if self.error else None,
            "request_id": self.request_id,
        }


@dataclass(slots=True)
class RequestExecution:
    total_calls: int = 0
    signatures: dict[str, int] = field(default_factory=dict)
    traces: list[ToolTrace] = field(default_factory=list)


class CampusMindRuntime:
    """Routes campus intents first and uses an optional model for general chat.

    This keeps source-of-truth operations deterministic. A model response can
    never substitute for a failed Tool call.
    """

    def __init__(
        self,
        tools: CampusToolRegistry,
        *,
        memory: PreferenceMemory | None = None,
        model: ChatModelClient | None = None,
        max_total_tool_calls: int = 4,
        max_identical_tool_calls: int = 1,
        model_timeout_seconds: float = 20.0,
    ) -> None:
        if max_total_tool_calls < 1 or max_identical_tool_calls < 1:
            raise ValueError("Tool call limits must be positive")
        self.tools = tools
        self.memory = memory or PreferenceMemory()
        self.model = model
        self.max_total_tool_calls = max_total_tool_calls
        self.max_identical_tool_calls = max_identical_tool_calls
        self.model_timeout_seconds = model_timeout_seconds

    async def chat(
        self,
        request: AgentRequest,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> AgentResponse:
        invalid = _validate_request(request)
        if invalid:
            return AgentResponse(
                ok=False,
                message="请求字段无效，未执行任何校园操作。",
                request_id=request.request_id,
                error=ToolError("VALIDATION_ERROR", invalid, {}),
            )
        if cancel_event and cancel_event.is_set():
            return _interrupted_response(request.request_id)

        execution = RequestExecution()
        text = request.message.strip()
        reference_time = request.reference_time or datetime.now(SHANGHAI).isoformat()
        current_date = datetime.fromisoformat(
            reference_time.replace("Z", "+00:00")
        ).astimezone(SHANGHAI).date().isoformat()

        if _is_today_brief(text):
            result = await self.invoke_tool(
                "get_today_brief",
                {
                    "student_id": request.student_id,
                    "date": current_date,
                    "timezone": request.timezone,
                },
                execution=execution,
                cancel_event=cancel_event,
            )
            return _tool_response(
                request,
                result,
                execution,
                success_message=_brief_message(result),
            )

        if _is_course_query(text):
            result = await self.invoke_tool(
                "get_courses",
                {"student_id": request.student_id, "date": current_date},
                execution=execution,
                cancel_event=cancel_event,
            )
            return _tool_response(
                request,
                result,
                execution,
                success_message=_courses_message(result),
            )

        if _is_notice_request(text):
            result = await self.invoke_tool(
                "parse_notice",
                {
                    "text": text,
                    "student_id": request.student_id,
                    "reference_time": reference_time,
                },
                execution=execution,
                cancel_event=cancel_event,
            )
            if result.ok and result.data.get("needs_confirmation"):
                return AgentResponse(
                    ok=True,
                    message="通知中的日期或对象还不够明确，请确认后我再创建任务。",
                    request_id=request.request_id,
                    data=result.data,
                    traces=tuple(execution.traces),
                    needs_confirmation=True,
                )
            return _tool_response(
                request,
                result,
                execution,
                success_message="通知已解析；请先核对解析结果，再决定是否创建任务。",
                force_confirmation=result.ok,
            )

        if _is_complete_request(text):
            task_id = _task_id_from(text) or request.context.get("task_id")
            if not isinstance(task_id, str) or not task_id.strip():
                return AgentResponse(
                    ok=True,
                    message="请告诉我要完成的任务 ID；我不会猜测任务。",
                    request_id=request.request_id,
                    needs_confirmation=True,
                )
            result = await self.invoke_tool(
                "complete_task",
                {"student_id": request.student_id, "task_id": task_id},
                execution=execution,
                cancel_event=cancel_event,
            )
            return _tool_response(
                request,
                result,
                execution,
                success_message="任务已标记为完成。",
            )

        if _is_create_request(text):
            task = request.context.get("task")
            if not isinstance(task, Mapping):
                return AgentResponse(
                    ok=True,
                    message="请补充任务标题、类型、优先级和唯一标识；截止时间不明确时也请确认。",
                    request_id=request.request_id,
                    needs_confirmation=True,
                )
            arguments = dict(task)
            arguments["student_id"] = request.student_id
            result = await self.invoke_tool(
                "create_task",
                arguments,
                execution=execution,
                cancel_event=cancel_event,
            )
            return _tool_response(
                request,
                result,
                execution,
                success_message="任务已创建。",
            )

        if _is_rag_query(text):
            result = await self._query_knowledge(
                text,
                request.student_id,
                execution=execution,
                cancel_event=cancel_event,
            )
            return _tool_response(
                request,
                result,
                execution,
                success_message=(
                    result.data.get("answer", "已找到有来源的校园资料。")
                    if result.ok
                    else ""
                ),
            )

        if self.model is not None:
            return await self._model_chat(request, execution, cancel_event)
        return AgentResponse(
            ok=True,
            message="你好！我可以查今日安排、课程，解析通知，或协助创建和完成任务。当前未配置在线模型，普通闲聊使用本地规则回复。",
            request_id=request.request_id,
            runtime_mode="local-rules",
        )

    async def invoke_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
        *,
        execution: RequestExecution | None = None,
        cancel_event: asyncio.Event | None = None,
        timeout_seconds: float | None = None,
    ) -> ToolResult:
        execution = execution or RequestExecution()
        signature = f"{name}:{json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)}"
        if execution.total_calls >= self.max_total_tool_calls or execution.signatures.get(
            signature, 0
        ) >= self.max_identical_tool_calls:
            result = ToolResult.failure(
                "AGENT_TOOL_FAILED",
                "已阻止同一请求中的重复校园工具调用",
                {"reason": "tool_call_limit", "tool": name},
            )
            execution.traces.append(
                ToolTrace(
                    name=name,
                    started_at=datetime.now(SHANGHAI).isoformat(),
                    status="blocked",
                    duration_ms=0,
                    error_code="AGENT_TOOL_FAILED",
                )
            )
            return result

        execution.total_calls += 1
        execution.signatures[signature] = execution.signatures.get(signature, 0) + 1
        started_at = datetime.now(SHANGHAI).isoformat()
        start = perf_counter()
        call = asyncio.create_task(
            self.tools.execute(name, arguments, timeout_seconds=timeout_seconds)
        )
        interrupted = False
        if cancel_event is not None:
            waiter = asyncio.create_task(cancel_event.wait())
            done, _ = await asyncio.wait(
                {call, waiter}, return_when=asyncio.FIRST_COMPLETED
            )
            if waiter in done and cancel_event.is_set() and call not in done:
                interrupted = True
                call.cancel()
                await asyncio.gather(call, return_exceptions=True)
            waiter.cancel()
            await asyncio.gather(waiter, return_exceptions=True)
        if interrupted:
            result = ToolResult.failure(
                "AGENT_TOOL_FAILED",
                "请求已中断，校园操作未完成",
                {"reason": "interrupted", "tool": name},
            )
        else:
            result = await call

        status = "success" if result.ok else _failure_status(result)
        duration_ms = max(0, round((perf_counter() - start) * 1000))
        execution.traces.append(
            ToolTrace(
                name=name,
                started_at=started_at,
                status=status,
                duration_ms=duration_ms,
                error_code=result.error.code if result.error else None,
            )
        )
        return result

    async def _query_knowledge(
        self,
        query: str,
        student_id: str,
        *,
        execution: RequestExecution,
        cancel_event: asyncio.Event | None,
    ) -> ToolResult:
        method = getattr(self.tools.service, "search_knowledge", None)
        if not callable(method):
            return _append_immediate_trace(
                execution,
                "rag_search",
                ToolResult.failure(
                    "RAG_NO_SOURCE",
                    "知识库中没有可核验的资料，我无法确认学校规定",
                    {"reason": "rag_not_integrated"},
                ),
            )
        started_at = datetime.now(SHANGHAI).isoformat()
        start = perf_counter()
        try:
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError
            data = await asyncio.wait_for(
                method(query=query, student_id=student_id),
                timeout=self.tools.default_timeout_seconds,
            )
            if not isinstance(data, Mapping) or not data.get("sources"):
                result = ToolResult.failure(
                    "RAG_NO_SOURCE",
                    "知识库中没有可靠来源，我无法确认学校规定",
                    {"reason": "empty_sources"},
                )
            else:
                result = ToolResult.success(dict(data))
        except asyncio.CancelledError:
            result = ToolResult.failure(
                "AGENT_TOOL_FAILED", "请求已中断", {"reason": "interrupted"}
            )
        except TimeoutError:
            result = ToolResult.failure(
                "AGENT_TOOL_FAILED", "知识库检索超时", {"reason": "tool_timeout"}
            )
        except Exception:
            result = ToolResult.failure(
                "AGENT_TOOL_FAILED", "知识库检索失败", {"reason": "service_exception"}
            )
        execution.traces.append(
            ToolTrace(
                name="rag_search",
                started_at=started_at,
                status="success" if result.ok else _failure_status(result),
                duration_ms=max(0, round((perf_counter() - start) * 1000)),
                error_code=result.error.code if result.error else None,
            )
        )
        return result

    async def _model_chat(
        self,
        request: AgentRequest,
        execution: RequestExecution,
        cancel_event: asyncio.Event | None,
    ) -> AgentResponse:
        assert self.model is not None
        provider = self.model.provider
        trace_name = f"{provider.replace('-', '_')}_chat"
        started_at = datetime.now(SHANGHAI).isoformat()
        start = perf_counter()
        try:
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError
            model_call = asyncio.create_task(
                self.model.complete(
                    [
                        {
                            "role": "system",
                            "content": (
                                "你是 CampusMind。普通聊天可以自然回答；课表、任务、截止时间和学校规定"
                                "必须来自工具或可靠来源，绝不能凭模型记忆编造。"
                            ),
                        },
                        {"role": "user", "content": request.message},
                    ],
                    timeout_seconds=self.model_timeout_seconds,
                )
            )
            if cancel_event is not None:
                waiter = asyncio.create_task(cancel_event.wait())
                done, _ = await asyncio.wait(
                    {model_call, waiter}, return_when=asyncio.FIRST_COMPLETED
                )
                if waiter in done and cancel_event.is_set() and model_call not in done:
                    model_call.cancel()
                    await asyncio.gather(model_call, return_exceptions=True)
                    raise asyncio.CancelledError
                waiter.cancel()
                await asyncio.gather(waiter, return_exceptions=True)
            content = await model_call
            trace = ToolTrace(
                name=trace_name,
                started_at=started_at,
                status="success",
                duration_ms=max(0, round((perf_counter() - start) * 1000)),
            )
            execution.traces.append(trace)
            return AgentResponse(
                ok=True,
                message=content,
                request_id=request.request_id,
                traces=tuple(execution.traces),
                runtime_mode=provider,
            )
        except asyncio.CancelledError:
            execution.traces.append(
                ToolTrace(
                    name=trace_name,
                    started_at=started_at,
                    status="interrupted",
                    duration_ms=max(0, round((perf_counter() - start) * 1000)),
                    error_code="MODEL_UNAVAILABLE",
                )
            )
            return _interrupted_response(
                request.request_id,
                tuple(execution.traces),
                runtime_mode=provider,
            )
        except ModelUnavailableError:
            execution.traces.append(
                ToolTrace(
                    name=trace_name,
                    started_at=started_at,
                    status="timeout",
                    duration_ms=max(0, round((perf_counter() - start) * 1000)),
                    error_code="MODEL_UNAVAILABLE",
                )
            )
            return AgentResponse(
                ok=False,
                message="在线模型当前不可用，我没有伪造回复。校园工具仍可单独使用。",
                request_id=request.request_id,
                error=ToolError(
                    "MODEL_UNAVAILABLE",
                    "在线模型不可用或超时",
                    {"provider": provider},
                ),
                traces=tuple(execution.traces),
                runtime_mode=provider,
            )

    async def stream_chat(
        self,
        request: AgentRequest,
        *,
        cancel_event: asyncio.Event | None = None,
        chunk_size: int = 12,
    ) -> AsyncIterator[dict[str, Any]]:
        if chunk_size < 1:
            raise ValueError("chunk_size must be positive")
        response = await self.chat(request, cancel_event=cancel_event)
        for offset in range(0, len(response.message), chunk_size):
            if cancel_event and cancel_event.is_set():
                yield {"event": "interrupted", "request_id": request.request_id}
                return
            yield {
                "event": "chunk",
                "request_id": request.request_id,
                "text": response.message[offset : offset + chunk_size],
            }
            await asyncio.sleep(0)
        yield {"event": "done", "response": response.to_dict()}


def _validate_request(request: AgentRequest) -> str | None:
    if not isinstance(request.message, str) or not request.message.strip():
        return "message must be a non-empty string"
    if not isinstance(request.student_id, str) or not request.student_id.strip():
        return "student_id must be a non-empty string"
    if request.timezone != "Asia/Shanghai":
        return "timezone must be Asia/Shanghai"
    if request.reference_time:
        try:
            parsed = datetime.fromisoformat(request.reference_time.replace("Z", "+00:00"))
        except ValueError:
            return "reference_time must use ISO 8601"
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return "reference_time must include a timezone"
    return None


def _is_today_brief(text: str) -> bool:
    normalized = text.lower()
    exact = ("今天有什么事情", "今天有什么事", "今日简报", "today brief")
    return any(value in normalized for value in exact) or (
        "今天" in normalized and any(word in normalized for word in ("安排", "事项", "待办"))
    )


def _is_course_query(text: str) -> bool:
    normalized = text.lower()
    return any(value in normalized for value in ("课表", "有什么课", "上什么课", "我的课程"))


def _is_notice_request(text: str) -> bool:
    return "通知" in text and any(
        value in text for value in ("解析", "帮我看", "报名", "截止", "请于", "要求")
    )


def _is_complete_request(text: str) -> bool:
    return any(value in text for value in ("完成任务", "标记完成", "已经做完", "办完了"))


def _is_create_request(text: str) -> bool:
    return any(value in text for value in ("创建任务", "添加任务", "加入待办"))


def _is_rag_query(text: str) -> bool:
    return any(value in text for value in ("学校规定", "学校政策", "奖学金规定", "校规", "官方要求"))


def _task_id_from(text: str) -> str | None:
    match = re.search(r"\btask[-_][A-Za-z0-9_-]+\b", text)
    return match.group(0) if match else None


def _failure_status(result: ToolResult) -> str:
    reason = result.error.details.get("reason") if result.error else None
    if reason in {"tool_timeout", "model_timeout"}:
        return "timeout"
    if reason == "interrupted":
        return "interrupted"
    if reason == "tool_call_limit":
        return "blocked"
    return "error"


def _brief_message(result: ToolResult) -> str:
    if not result.ok:
        return ""
    data = result.data
    return (
        f"今天有 {len(data['courses'])} 节课、{len(data['tasks'])} 项任务、"
        f"{len(data['notices'])} 条通知。详情来自校园工具。"
    )


def _courses_message(result: ToolResult) -> str:
    if not result.ok:
        return ""
    return f"当天共有 {len(result.data)} 节课，课程信息来自校园工具。"


def _tool_response(
    request: AgentRequest,
    result: ToolResult,
    execution: RequestExecution,
    *,
    success_message: str,
    force_confirmation: bool = False,
) -> AgentResponse:
    if result.ok:
        return AgentResponse(
            ok=True,
            message=success_message,
            request_id=request.request_id,
            data=result.data,
            traces=tuple(execution.traces),
            needs_confirmation=force_confirmation,
        )
    error = result.error or ToolError("INTERNAL_ERROR", "未知错误", {})
    messages = {
        "NOTICE_DATE_AMBIGUOUS": "通知日期不明确，请补充年份和准确截止时间后再继续。",
        "TASK_DUPLICATE": "检测到重复任务，没有再次创建。",
        "TASK_NOT_FOUND": "没有找到该任务，未修改任何任务。",
        "RAG_NO_SOURCE": "知识库没有可靠来源，我无法确认该学校规定。",
        "AGENT_TOOL_FAILED": "校园工具执行失败，操作未完成；我没有伪造成功结果。",
    }
    return AgentResponse(
        ok=False,
        message=messages.get(error.code, error.message),
        request_id=request.request_id,
        error=error,
        traces=tuple(execution.traces),
        needs_confirmation=error.code == "NOTICE_DATE_AMBIGUOUS",
    )


def _append_immediate_trace(
    execution: RequestExecution, name: str, result: ToolResult
) -> ToolResult:
    execution.traces.append(
        ToolTrace(
            name=name,
            started_at=datetime.now(SHANGHAI).isoformat(),
            status=_failure_status(result),
            duration_ms=0,
            error_code=result.error.code if result.error else None,
        )
    )
    return result


def _interrupted_response(
    request_id: str,
    traces: tuple[ToolTrace, ...] = (),
    *,
    runtime_mode: str = "local-rules",
) -> AgentResponse:
    return AgentResponse(
        ok=False,
        message="请求已中断，没有把未完成的操作当作成功。",
        request_id=request_id,
        error=ToolError(
            "AGENT_TOOL_FAILED", "请求已中断", {"reason": "interrupted"}
        ),
        traces=traces,
        runtime_mode=runtime_mode,
    )
