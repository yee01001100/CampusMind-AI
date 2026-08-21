# HANDOFF — Agent 3

## Identity

- Role: Agent 3 / Campus Service + FastAPI
- Team member: Agent 3 组员（姓名未提供）
- AI partner: `/root/agent3_service_api`
- Branch: `agent/3-service-api`
- Base commit: `089bb8314cf34ed385dc158df288ca321d5bbfea` (`day0-baseline`)
- Final implementation commit: `3b6f0ee406ab2539d702d9c3d9f3b007629f80d2`
- Handoff commit: 本文所在的后续纯文档提交
- Finished at: `2026-08-21T20:14:28+08:00`

## Goal Result

Agent 3 的四类业务 Service 与 Shared Contract 冻结的 9 个 FastAPI 操作均已实现。通知输入可以经过校验、时间标准化、适用性判断和去重后创建一个或多个任务；任务可以进入今日简报、完成后停止提醒。课表支持单双周、自定义周、下一节、空闲时间和冲突检测，提醒支持默认规则、勿扰时段、去重、重启恢复、失败状态和重试。Agent 2/Agent 1 尚未合并的部分使用明确标识、可注入替换的内存 Repository 与本地 Chat Facade；没有越界实现 domain/storage/runtime，也没有读取、记录或提交真实密钥。全部 Agent 3 测试及 Day 0 契约测试已通过。

## Created Files

- `campusmind/services/notice/{__init__.py,models.py,service.py}`
- `campusmind/services/course/{__init__.py,models.py,service.py}`
- `campusmind/services/task/{__init__.py,models.py,service.py}`
- `campusmind/services/reminder/{__init__.py,models.py,service.py}`
- `apps/api/{__init__.py,main.py,fakes.py,chat.py}`
- `tests/services/{__init__.py,conftest.py,test_notice_service.py,test_course_service.py,test_task_reminder_service.py}`
- `tests/services/fakes/__init__.py`
- `tests/api/{__init__.py,conftest.py,test_api_contract.py}`
- `HANDOFF-agent3.md`

## Modified Files

- `requirements/agent-3.txt`

## Public Interfaces

### Notice Service

- Name: `NoticeService.parse`
- Import: `from campusmind.services.notice import NoticeService, NoticeParseCommand`
- Input: `NoticeParseCommand(text, student_id, reference_time, candidate, student_segments)`
- Output: `NoticeParseResult(notice, tasks, duplicate, expired, applicable)`
- Error: `NOTICE_EMPTY`, `NOTICE_DATE_AMBIGUOUS`, `NOTICE_NOT_APPLICABLE`, `VALIDATION_ERROR`
- Behavior: 支持 `本周五`、带年份绝对日期、多行动项、过期通知、受众判断和重复来源；低置信度不创建任务。

### Course Service

- Name: `CourseService.for_day`, `free_time`, `detect_conflicts`
- Import: `from campusmind.services.course import CourseService, Course, TimeBlock`
- Input: 学生、日期和可选当前时间；冲突检测使用带时区 `TimeBlock[]`
- Output: `CourseDayResult`、`FreeSlot[]`、`CourseConflict[]`
- Error: Pydantic 校验错误；没有课程是正常空列表，不抛异常。
- Behavior: 学期起始日由构造参数注入，默认演示值为 `2026-08-17`。

### Task Service

- Name: `TaskService.create`, `list`, `update`, `complete`, `restore`, `cancel`
- Import: `from campusmind.services.task import TaskService, TaskCreate, TaskPatch`
- Input: 严格遵循 Shared Contract 字段的任务创建/更新模型
- Output: 创建返回 `{task, created, duplicate_of}`；列表和更新返回公共 `Task` 模型。
- Error: `TASK_DUPLICATE`, `TASK_NOT_FOUND`, `VALIDATION_ERROR`
- Behavior: `dedupe_key` 唯一，自动计算优先级，保存来源通知和 `completed_at`，支持逾期筛选。

### Reminder Service

- Name: `ReminderService.schedule`, `due`, `cancel_for_task`, `mark_sent`, `mark_failed`, `retry_failed`, `recover_pending`
- Import: `from campusmind.services.reminder import ReminderService, Reminder, StudentProfile`
- Input: 公共 `Task`、`StudentProfile` 与带时区时间
- Output: 严格使用公共 `Reminder` 字段的提醒列表/提醒对象
- Error: `VALIDATION_ERROR`
- Behavior: 覆盖报名、考试、作业、课程、活动默认偏移；勿扰时间移到结束点；完成/取消任务的待发提醒标为 `skipped`。

### FastAPI

- App: `apps.api.main:app`
- Factory: `apps.api.main.create_app(repository=..., chat_facade=..., clock=...)`
- Success envelope: `{ok: true, data, error: null, request_id}`
- Failure envelope: `{ok: false, data: null, error: {code, message, details}, request_id}`
- Request ID: 接受可选 `X-Request-ID`，响应 body 和 header 保持一致。

| Method | URL | Main input | Main output |
| --- | --- | --- | --- |
| GET | `/api/health` | 无 | 服务和时区状态 |
| GET | `/api/v1/brief/today` | `student_id`, `date?` | courses/tasks/notices/conflicts/suggestions |
| POST | `/api/v1/notices/parse` | `NoticeParseCommand` | notice/tasks/reminders 与重复/过期状态 |
| GET | `/api/v1/courses/today` | `student_id`, `date?` | 当日课表、下一节与空闲时间 |
| POST | `/api/v1/tasks` | `TaskCreate` | task/created/duplicate_of/reminders |
| GET | `/api/v1/tasks` | 学生、状态、类型、逾期、排序筛选 | `Task[]` |
| PATCH | `/api/v1/tasks/{task_id}` | `TaskPatch`, `student_id?` | 更新后的 `Task` |
| GET | `/api/v1/reminders/due` | `student_id`, `at?` | 到期且仍有效的 `Reminder[]` |
| POST | `/api/v1/chat` | `student_id`, `message` | 可替换 Chat Facade 的回复 |

OpenAPI: `/openapi.json`；Swagger UI: `/docs`。CORS 只允许 `http://localhost:5173` 和 `http://127.0.0.1:5173`，没有无说明的 `*`。

## Contract Compliance

- [x] 使用 Shared Contract 公共字段
- [x] 未创建第二套同义字段
- [x] 未修改 Must NOT modify 目录
- [x] 分支从 `day0-baseline` 创建
- [x] 时区与时间格式正确
- [x] 未提交真实个人数据或密钥

公共 `Task` 与 `Reminder` API 输出没有添加包装字段；逾期状态只作为筛选计算，不改变冻结公共模型。所有运行数据均为明确的 `student-demo-001` 模拟数据。

## Commands

### Install

```powershell
D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe -m pip install -r requirements\agent-3.txt
```

### Run

```powershell
D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

### Test

```powershell
D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe scripts\check_day0.py
D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe -m pytest tests\contract tests\services tests\api -q
D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe -m pip check
```

## Test Results

- Command: `python scripts/check_day0.py`
- Exit code: `0`
- Important output: `PASS: Day 0 baseline is ready on Python 3.12`

- Command: `python -m pytest tests/contract tests/services tests/api -q`
- Exit code: `0`
- Passed: `79`
- Failed: `0`
- Skipped: `0`
- Important output: `79 passed, 1 warning in 0.25s`
- Warning: FastAPI 当前 `TestClient` 转发的 Starlette 上游提示 `httpx` 入口未来弃用；不影响运行和验收。

- Command: `python -m pip check`
- Exit code: `0`
- Important output: `No broken requirements found.`

覆盖数量包括：20 条通知正常样本、5 条模糊/无效日期、10 组课表查询、5 组冲突、5 组重复任务、5 类提醒规则，以及 9 个 API 的成功/失败 envelope、空列表、CORS、OpenAPI、未知异常脱敏和完整纵切。

## Stub / Mock

| Path | Simulates | Must be replaced by | Replacement step |
| --- | --- | --- | --- |
| `apps/api/fakes.py` | Agent 2 尚未合并时的任务/课程/通知/提醒/学生内存 Repository | Agent 2 SQLite Repository adapter | 实现同名窄接口方法，将实例传给 `create_app(repository=adapter)`；服务代码和路由无需改写。 |
| `tests/services/fakes/__init__.py` | 测试对内存 Repository 的稳定入口 | 不替换，保留为单元测试 Fake | 集成测试另加 SQLite fixture，现有单元测试继续使用 Fake。 |
| `apps/api/chat.py` | Agent 1 尚未合并时的本地规则 Chat Facade | Agent 1 DeepTutor/Tool adapter | 实现 `reply(ChatRequest, brief) -> dict` 或由 Agent 0 建立适配器，传给 `create_app(chat_facade=adapter)`。 |

Repository adapter 必需方法：`get_task`, `get_task_by_dedupe`, `list_tasks`, `save_task`, `list_courses`, `get_notice_by_source`, `save_notice`, `list_notices`, `list_tasks_for_notice`, `get_profile`, `list_reminders`, `save_reminder`。持久化实现必须继续保证 `dedupe_key` 唯一和带时区时间语义。

## Environment Variables

当前 Agent 3 模块不要求环境变量，也不访问模型密钥。Agent 0 接入真实模型时，密钥只能从未提交的环境配置读取，不能写入代码、日志或 HANDOFF。

## Known Limitations

1. 默认 Repository 是进程内存 Stub，服务重启后数据本身不会持久化；`recover_pending` 已实现，只有换成 Agent 2 持久化 Repository 后才能跨进程恢复。
2. 通知解析器是确定性中文日期/动作规则，用于独立验收；复杂自然语言抽取应由 Agent 1 模型生成 `NoticeCandidate` 后仍交给本 Service 校验。
3. `/api/v1/chat` 明确返回 `mode=local_stub`，不伪装成真实模型；Agent 0 必须换接 Agent 1 Runtime。
4. 提醒只实现 `in_app` 状态机，不含外部消息通道，符合当前冻结契约。

## Integration Steps for Agent 0

1. 将 `agent/3-service-api` 合并到 `agent/0-integration`，不要只拣 Service 而遗漏测试与本 HANDOFF。
2. 安装 `requirements/agent-3.txt`；随后由 Agent 0 将最终兼容版本整理进根 `pyproject.toml`。
3. 为 Agent 2 Repository 写一个满足上述窄方法的 adapter，并通过 `create_app(repository=adapter)` 注入；不要让 Service 直接依赖 SQLite session。
4. 为 Agent 1 Runtime 写 Chat Facade adapter，通过 `create_app(chat_facade=adapter)` 注入；模型不可跳过 Notice/Task Service 的校验和去重。
5. 保持 `Asia/Shanghai`，配置前端开发来源后运行 `uvicorn apps.api.main:app --host 127.0.0.1 --port 8000`。
6. 先运行本 HANDOFF 的 79 项测试，再增加 SQLite 集成测试和 Agent Tool → API 测试。
7. 验证纵切：通知输入 → 创建任务 → 今日简报 → 完成任务 → `/reminders/due` 返回空列表。

## Behaviors That Must Not Break

- 所有成功和失败响应都有相同 envelope，body/header 的 `request_id` 一致。
- `raw_text` 必须保留原通知，模糊年份不能猜测。
- 相同通知来源和 `dedupe_key` 不得重复创建任务。
- 空课表/任务/提醒是 `200` 空列表，不能变成 `500`。
- 未知异常必须映射 `INTERNAL_ERROR`，不能向响应泄露异常文字或堆栈。
- 已完成或取消任务不得继续产生到期提醒。
- API 公共模型必须保持 Shared Contract 字段和带时区时间格式。
- 不得把 CORS 改成未说明的全开放配置。

## Remaining Blockers

无。Agent 2 持久化 Repository 与 Agent 1 Runtime 的替换属于既定集成步骤，不阻塞 Agent 3 独立验收。

## Final Statement

COMPLETE — 全部 Agent 3 验收通过，可以交给 Agent 0。
