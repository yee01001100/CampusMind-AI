# AGENT 3 — Campus Service / FastAPI

> 必读：[README](../../README.md) · [Shared Contract](../../contracts/SHARED_CONTRACT.md) · [HANDOFF 模板](../HANDOFF_TEMPLATE.md) · [最终验收](../FINAL_ACCEPTANCE.md)

本角色由一名组员与其 AI 搭档共同承担。组员负责确认范围、检查文件、运行测试和推送分支；AI 负责持续实现、自检并起草 HANDOFF。双方共同对验收结果负责。

## Goal

一次完成通知、课表、任务和提醒的业务服务与 FastAPI 接口。所有业务判断可测试，所有响应遵循 Shared Contract。

## Input

- `README.md`
- `contracts/SHARED_CONTRACT.md`
- Agent 2 尚未完成时，由本角色创建的内存 Repository Stub
- Agent 4 使用的公共 API 契约

## Owns

```text
campusmind/services/notice/
campusmind/services/course/
campusmind/services/task/
campusmind/services/reminder/
apps/api/
tests/services/
tests/api/
requirements/agent-3.txt
HANDOFF-agent3.md
```

## Must NOT modify

```text
campusmind/domain/
campusmind/storage/
campusmind/repositories/
campusmind/integrations/
campusmind/tools/
skills/
apps/web/
data/
contracts/SHARED_CONTRACT.md
pyproject.toml
requirements/agent-1.txt
requirements/agent-2.txt
tests/contract/
```

## Must Implement

### 1. Notice Service

流程固定为：

```text
原始通知
→ 接收候选字段
→ Pydantic 校验
→ 日期与时区标准化
→ 检查适用对象
→ 计算确认状态
→ 生成一个或多个任务
```

必须处理：

- 空通知。
- “本周五”等相对日期。
- 缺少年份。
- 报名开始和报名截止同时存在。
- 一条通知包含多个行动事项。
- 通知已过期。
- 通知不适用当前学生。
- 同一通知重复导入。

### 2. Course Service

- 查询今日课程。
- 查询下一节课程。
- 支持单双周和自定义周次。
- 计算两个课程之间的空闲时间。
- 检测课程、考试和待办冲突。
- 没有课程时返回空结果，不使用异常替代正常空状态。

### 3. Task Service

- 创建任务并通过 `dedupe_key` 去重。
- 查询、筛选和排序任务。
- 完成、恢复和取消任务。
- 计算逾期状态。
- 保留来源通知。

默认优先级：

| 条件 | 优先级 |
| --- | --- |
| 已逾期或不可补办 | critical |
| 24 小时内截止 | high |
| 3 天内截止 | medium |
| 超过 3 天 | normal |

### 4. Reminder Service

默认规则：

| 类型 | 提醒时间 |
| --- | --- |
| 报名截止 | 7 天、3 天、1 天、3 小时前 |
| 考试 | 7 天、3 天、1 天前 |
| 作业 | 3 天、1 天、3 小时前 |
| 课程 | 30 分钟前 |
| 普通活动 | 1 天、2 小时前 |

还必须处理：

- 勿扰时段。
- 已完成和取消任务。
- 重复提醒。
- 服务重启后的恢复。
- 发送失败状态与重试。

### 5. FastAPI

实现 Shared Contract 中全部公共 API：

```text
GET   /api/health
GET   /api/v1/brief/today
POST  /api/v1/notices/parse
GET   /api/v1/courses/today
POST  /api/v1/tasks
GET   /api/v1/tasks
PATCH /api/v1/tasks/{task_id}
GET   /api/v1/reminders/due
POST  /api/v1/chat
```

要求：

- 统一成功和失败响应。
- 每个响应包含 `request_id`。
- 使用固定错误码。
- OpenAPI 可以启动并生成。
- CORS 仅配置开发所需来源，不使用无说明的全开放配置。
- 不在路由中堆叠业务逻辑。

## Work Sequence

1. 从 `day0-baseline` 创建本角色分支 `agent/3-service-api`。
2. 使用 Python 3.12 运行 `python scripts/check_day0.py`。
3. 使用内存 Repository Stub 建立 Service 接口。
4. 完成 Notice、Course、Task、Reminder Service。
5. 实现 FastAPI 路由和异常映射。
6. 生成并检查 OpenAPI。
7. 覆盖正常、空数据、错误和重复请求。
8. 运行验收命令。
9. 创建 `HANDOFF-agent3.md` 后停止。

## Stub / Mock

Agent 2 未完成时，在 `tests/services/fakes/` 创建内存 Repository，字段必须严格遵循 Shared Contract。

不得进入 `campusmind/domain/` 或 `storage/` 代写 Agent 2 的实现。HANDOFF 必须说明如何替换为真实 Repository。

## Required Tests

至少验证：

- 20 条通知校验样本。
- 10 组课表查询。
- 5 组时间冲突。
- 5 种重复任务。
- 5 种无效或模糊日期。
- 已完成任务不再产生提醒。
- 所有 API 成功/失败响应符合契约。
- 空列表不是 500 错误。
- 未知异常转换为 `INTERNAL_ERROR` 且不泄露堆栈。

运行：

```powershell
python -m pytest tests/services tests/api -q
```

## Acceptance

即使 Agent 1/2/4 未完成，也能通过内存 Repository 和 API TestClient 真实跑通：

```text
通知输入
→ 校验
→ 创建任务
→ 今日简报查询
→ 完成任务
→ 停止提醒
```

## Finish

按 [HANDOFF 模板](../HANDOFF_TEMPLATE.md) 创建：

```text
HANDOFF-agent3.md
```

HANDOFF 必须记录：

- Service 与路由文件。
- API 输入输出和错误码。
- Repository Stub 与替换方法。
- 启动命令。
- 测试命令与真实结果。
- Agent 1/2/4/0 的接入步骤。
- 已知限制。

完成 HANDOFF 后停止，不代写数据层、Agent 或前端。
