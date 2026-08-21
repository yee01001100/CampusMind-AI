# HANDOFF — Agent 1

## Identity

- Role: Agent 1 / DeepTutor、Campus Tool 与 Runtime
- Team member: CampusMind 组员 1（待组长替换为实际姓名）
- AI partner: Codex `/root/agent1_runtime`
- Branch: `agent/1-runtime`
- Base commit: `089bb8314cf34ed385dc158df288ca321d5bbfea` (`day0-baseline` peeled commit)
- Final implementation commit: `ddc03affe1380812189a25b76996157892834b06`
- Finished at: `2026-08-21T19:57:03+08:00`

## Goal Result

Agent 1 的 Must Implement 已完成：五个 Shared Contract Tool 均有异步校验、调用、结果校验、超时和稳定错误映射；规则 Runtime 能把校园意图路由到真实 Fake Service，返回中文结果并保存不含参数/结果的结构化 Trace。Runtime 还实现了重复调用上限、Tool/模型中断、模型超时、RAG 无来源拒答和 Memory 白名单。DeepTutor 通过不修改核心的公开 Host 注册桥接，当前环境未安装 DeepTutor，因此仅用 Fake Host 验证注册；DeepSeek 使用 OpenAI-compatible 可选适配，测试只用 Fake Transport，未发送真实请求。无 `DEEPSEEK_API_KEY` 时明确运行在 `local-rules` 模式，不冒充在线模型成功。

## Created Files

- `skills/campusmind/SKILL.md`
- `campusmind/tools/__init__.py`
- `campusmind/tools/errors.py`
- `campusmind/tools/models.py`
- `campusmind/tools/registry.py`
- `campusmind/integrations/deeptutor/__init__.py`
- `campusmind/integrations/deeptutor/bridge.py`
- `campusmind/integrations/deeptutor/deepseek.py`
- `campusmind/integrations/deeptutor/memory.py`
- `campusmind/integrations/deeptutor/runtime.py`
- `apps/api/agent/__init__.py`
- `apps/api/agent/facade.py`
- `tests/agent/__init__.py`
- `tests/agent/fakes/__init__.py`
- `tests/agent/fakes/service.py`
- `tests/agent/test_tools.py`
- `tests/agent/test_runtime.py`
- `tests/agent/test_integrations.py`

## Modified Files

- `requirements/agent-1.txt`

## Public Interfaces

### Campus Tool Registry

- Name: `CampusToolRegistry.execute`
- Import / URL: `from campusmind.tools import CampusToolRegistry`
- Input: Tool 名称、JSON-compatible 参数对象、可选 `timeout_seconds`
- Output: `ToolResult(ok, data, error)`；可用 `to_dict()` 序列化
- Error: 输入错误为 `VALIDATION_ERROR`；稳定 Service 错误码原样传递；超时/未知异常/错误结果为 `AGENT_TOOL_FAILED`
- Example: `await tools.execute("get_courses", {"student_id": "student-demo-001", "date": "2026-08-21"})`

五个已注册 Tool：

| Tool | Input | Successful data |
| --- | --- | --- |
| `get_today_brief` | `student_id`, `date`, `timezone` | `date/courses/tasks/notices/conflicts/suggestions` |
| `parse_notice` | `text`, `student_id`, `reference_time` | Shared Contract `Notice` |
| `create_task` | Task 创建字段 | `task`, `created`, `duplicate_of` |
| `get_courses` | `student_id`, `date` | Shared Contract `Course[]` |
| `complete_task` | `student_id`, `task_id` | 更新后的 Shared Contract `Task` |

### Agent Runtime

- Name: `CampusMindRuntime.chat`, `stream_chat`, `invoke_tool`
- Import / URL: `from campusmind.integrations.deeptutor import CampusMindRuntime, AgentRequest`
- Input: `AgentRequest(message, student_id, request_id, reference_time, timezone, context)`
- Output: `AgentResponse` 或流事件 `chunk/done/interrupted`
- Error: Shared Contract 错误对象；失败操作的 `data` 为 `null`，不会生成成功措辞
- Example: `await runtime.chat(AgentRequest(message="今天有什么事情？", student_id="student-demo-001"))`

### DeepTutor Bridge

- Name: `DeepTutorBridge.initialize`
- Import / URL: `from campusmind.integrations.deeptutor import DeepTutorBridge`
- Input: 可选公开 Host，需实现 `register_skill` 和 `register_tool`
- Output: `BridgeStatus(available, registered_tools, deeptutor_version, reason)`
- Error: 未安装/未暴露受支持 Host factory 时返回 `available=False`，不伪造初始化成功
- Example: `DeepTutorBridge(tools).initialize(host)`

### Optional DeepSeek Provider

- Name: `DeepSeekConfig.from_env`, `DeepSeekChatClient.complete`
- Import / URL: `from campusmind.integrations.deeptutor import DeepSeekConfig, DeepSeekChatClient`
- Input: OpenAI-compatible `messages`;配置仅读取环境变量
- Output: 非空模型文本
- Error: 超时、HTTP/传输错误和错误响应统一为 `ModelUnavailableError`，Runtime 输出 `MODEL_UNAVAILABLE`
- Example: `config = DeepSeekConfig.from_env(); client = DeepSeekChatClient(config) if config else None`

### API Integration Facade

- Name: `build_agent_runtime`, `AgentChatFacade.chat`, `AgentChatFacade.stream`
- Import / URL: `from apps.api.agent import build_agent_runtime, AgentChatFacade`
- Input: Agent 3 的 `CampusService` 实现与 `/api/v1/chat` payload
- Output: Shared Contract 成功/失败 envelope
- Error: 与 Runtime 相同
- Example: `facade = AgentChatFacade(build_agent_runtime(service))`

### Preference Memory

- Name: `PreferenceMemory.remember`, `snapshot`, `forget`
- Import / URL: `from campusmind.integrations.deeptutor import PreferenceMemory`
- Input: 学生 ID 和专业、年级、兴趣、偏好、提醒习惯、静默时段
- Output: 深拷贝后的偏好快照
- Error: 课表、任务状态、准确截止时间、学校规定和未知字段抛出 `MemoryPolicyError`
- Example: `memory.remember(student_id, {"interests": ["人工智能"]})`

## Contract Compliance

- [x] 使用 Shared Contract 公共字段
- [x] 未创建第二套同义字段
- [x] 未修改 Must NOT modify 目录
- [x] 分支从 `day0-baseline` 创建
- [x] 时区与时间格式正确
- [x] 未提交真实个人数据或密钥

本地 Windows Python 没有 `tzdata`，因此实现严格接受项目冻结的 `Asia/Shanghai`，并使用固定 `+08:00` 时区对象输出带偏移 ISO 8601；没有放宽为无时区时间。

## Commands

### Install

Agent 1 没有新增必装 PyPI 依赖：

```powershell
python -m pip install -e ".[dev]"
```

DeepTutor 由 Agent 0 以官方公开扩展 Host 接入；不得把核心复制到本模块。DeepSeek 不需要 SDK。

### Run

```powershell
python -c "from apps.api.agent import build_agent_runtime; print('Agent runtime import OK')"
```

FastAPI 路由由 Agent 3 持有；其启动时把真实 Service 传给 `build_agent_runtime(service)`，再让 `/api/v1/chat` 调用 `AgentChatFacade`。

### Test

```powershell
D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe scripts\check_day0.py
D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe scripts\check_contracts.py
D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe -m pytest tests\agent -q
D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe -X dev -m pytest -q
```

## Test Results

- Command: `...python.exe scripts\check_day0.py`
- Exit code: `0`
- Passed: Day 0 baseline check `PASS` on Python `3.12.13`
- Failed: `0`
- Skipped: `0`
- Important output: `PASS: Day 0 baseline is ready on Python 3.12`

- Command: `...python.exe scripts\check_contracts.py`
- Exit code: `0`
- Passed: `5` model examples and `2` API envelopes
- Failed: `0`
- Skipped: `0`
- Important output: `PASS: 5 model examples and 2 API envelopes match the frozen contract`

- Command: `...python.exe -m pytest tests\agent -q`
- Exit code: `0`
- Passed: `32`
- Failed: `0`
- Skipped: `0`
- Important output: `32 passed in 0.36s`

- Command: `...python.exe -X dev -m pytest -q`
- Exit code: `0`
- Passed: `36`（Agent 1 `32` + Day 0 contract `4`）
- Failed: `0`
- Skipped: `0`
- Important output: `36 passed in 0.86s`

- Command: credential pattern scan over all Agent 1 owned files
- Exit code: `0`
- Passed: `0` credential-like matches
- Failed: `0`
- Skipped: `0`
- Important output: empty

## Stub / Mock

| Path | Simulates | Must be replaced by | Replacement step |
| --- | --- | --- | --- |
| `tests/agent/fakes/service.py` | Agent 3 Campus Service 的正常、空数据、模糊通知、重复任务、失败、超时和 RAG 场景 | Agent 3 `CampusService` 实现 | 在应用启动处把真实 Service 传入 `build_agent_runtime`; Fake 只保留在测试中 |
| `tests/agent/test_integrations.py::FakeDeepTutorHost` | DeepTutor 的公开 Skill/Tool 注册 Host | 官方 DeepTutor Host | 将官方 Host 传给 `DeepTutorBridge.initialize(host)`；如官方方法签名不同，只在 `bridge.py` 做最薄适配 |
| `tests/agent/test_integrations.py::FakeTransport` | DeepSeek OpenAI-compatible JSON 响应、延迟和超时 | `StdlibJsonTransport` | 配置环境变量后不要传 `model_transport`; 上线前用已轮换的密钥做一次受控 smoke test |

## Environment Variables

| Name | Required | Secret | Purpose | Example without secret |
| --- | --- | --- | --- | --- |
| `DEEPSEEK_API_KEY` | 否；仅在线模型需要 | 是 | DeepSeek Bearer 凭据；必须在聊天中出现过的值之外重新轮换 | `<set-in-local-environment>` |
| `DEEPSEEK_BASE_URL` | 否 | 否 | OpenAI-compatible 基地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 否 | 否 | 模型名称 | `deepseek-chat` |

任何变量缺失时不读取 `.env` 文件；`DEEPSEEK_API_KEY` 缺失会明确使用 `local-rules`，不会触发网络。

## Known Limitations

1. 当前验收环境未安装 DeepTutor，版本为 `N/A`。已通过 Fake Host 验证 Skill 和五个 Tool 的公开注册行为，但 Agent 0 仍需根据所选 DeepTutor 官方版本确认其 Host factory/方法签名。
2. 按安全要求没有使用聊天中曾暴露的 DeepSeek 密钥，也没有发真实模型请求。上线前必须轮换密钥，并通过环境变量做受控 smoke test。
3. `stream_chat` 提供可中断的结构化分块事件，但 DeepSeek 适配当前使用非流式 `/chat/completions` 响应后分块，不是提供方 token 级流式传输。
4. 无模型时的本地规则路由只覆盖 Execution Packet 的校园意图；`create_task` 需要上层在 `context.task` 提供已确认结构化字段，不会从模糊自然语言猜截止时间。
5. RAG 通过 Service 可选方法 `search_knowledge(query, student_id)` 接入；未接 Agent 2/3 或来源为空时稳定返回 `RAG_NO_SOURCE`。

## Integration Steps for Agent 0

1. 合并 `agent/1-runtime`，以实现提交 `ddc03affe1380812189a25b76996157892834b06` 为代码基准。
2. Agent 1 无额外 PyPI 依赖；安装 Agent 2/3 依赖后运行统一 `pip check`。
3. 保留 `tests/agent/fakes/service.py` 作为测试 Fake；生产启动必须把 Agent 3 真实 Service 传入 `build_agent_runtime`。
4. 选定并安装官方 DeepTutor 版本，把公开 Host 传给 `DeepTutorBridge.initialize`，核对返回的五个 `registered_tools`。
5. 轮换已经暴露过的提供方密钥，只通过 `DEEPSEEK_API_KEY` 配置；可选配置 `DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL`。不要把任何值提交到仓库。
6. 让 Agent 3 的 `POST /api/v1/chat` 调用 `AgentChatFacade.chat`；如采用 SSE/流式响应，转发 `AgentChatFacade.stream` 事件和断连 `cancel_event`。
7. 让 Agent 2/3 Service 实现 `search_knowledge(query, student_id)`，只在 `sources` 非空时返回回答。
8. 运行 `python scripts/check_day0.py`、`python scripts/check_contracts.py`、`python -m pytest tests/agent -q` 和全量测试。
9. 演示“今天有什么事情？”并确认 Trace 为 `get_today_brief/success`；再演示模糊通知、重复任务、RAG 无来源、Tool 超时和模型不可用，确认均未伪造成功。

## Behaviors That Must Not Break

- “今天有什么事情？”必须调用 `get_today_brief`，普通闲聊不得误调校园 Tool。
- Tool/模型失败、超时和中断不得产生成功话术或非空成功数据。
- `parse_notice` 后必须确认，模糊日期和低置信度不得直接创建任务。
- 同一请求的相同 Tool 参数不得重复执行；Trace 必须含名称、带时区开始时间、状态和耗时，但不含参数、通知正文、密钥或结果。
- Memory 不得成为课表、任务状态、准确截止时间或学校正式规定的唯一来源。
- DeepSeek 凭据只能来自环境变量；无密钥时必须明确为本地规则模式。

## Remaining Blockers

无。DeepTutor 安装、Agent 2/3 Service/RAG 替换和轮换后的 DeepSeek 在线 smoke test 是 Agent 0 的明确集成步骤，不影响 Agent 1 的独立 Fake Service 验收。

## Final Statement

COMPLETE — 全部 Agent 1 验收通过，可以交给 Agent 0。
