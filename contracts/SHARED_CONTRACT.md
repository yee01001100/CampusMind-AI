# CampusMind Shared Contract

> 返回 [README](../README.md) · 查看 [最终验收](../docs/FINAL_ACCEPTANCE.md) · 使用 [HANDOFF 模板](../docs/HANDOFF_TEMPLATE.md)

本文是五个人机搭档的共同施工契约：4 名组员分别与 AI 组成 Agent 1–4，1 名组长与主 AI 组成 Agent 0。成员对范围、测试和提交负责，AI 对施工、自检和 HANDOFF 负责；两者共同对交付结果负责。所有搭档开工前必须完整阅读。除 Stage 0 明确修改外，任何搭档不得自行更改本文定义的字段、API、错误码、技术栈和目录边界。

## 1. 契约优先级

发生冲突时按以下顺序执行：

1. 本文的公共模型、API 和禁止事项。
2. 当前 Agent 的 Execution Packet。
3. README 的项目目标与流程。
4. Agent 自己的实现偏好。

如果契约无法实现：

- 不得创建第二套字段或 API。
- 在自己的 `HANDOFF-agentN.md` 中记录问题、影响和推荐处理方式。
- 使用最小 Stub/Mock 继续完成可独立验证的部分。
- 由 Agent 0 在集成阶段决定是否修改契约。

## 2. 固定技术栈

| 层级 | 固定选择 |
| --- | --- |
| Python | 3.12 |
| Agent Runtime | DeepTutor |
| Backend | FastAPI + Pydantic |
| Database | SQLite |
| Frontend | React + Vite + TypeScript |
| Tests | Pytest + 前端单元测试 + 浏览器流程测试 |
| Timezone | Asia/Shanghai |

禁止子 Agent：

- 更换数据库。
- 把 FastAPI 换成其他服务框架。
- 把 React/Vite 换成其他前端框架。
- 修改 DeepTutor 核心代码来规避扩展接口。
- 引入与当前目标无关的大型基础设施。

## 3. 全局时间规则

- 所有后端时间使用带时区 ISO 8601，例如 `2026-08-18T18:00:00+08:00`。
- SQLite 中不得只保存“周五”“下午三点”等自然语言时间。
- 相对时间必须结合 `reference_time` 和 `Asia/Shanghai` 解析。
- 年份、日期或时区无法确认时，返回确认状态，不得猜测。
- 前端可以本地化显示，但 API 中保持标准格式。

## 4. 公共模型

### 4.1 Notice

```text
id: string
title: string
raw_text: string
audience: string[]
published_at: datetime | null
deadline: datetime | null
actions: string[]
priority: critical | high | medium | normal
source_type: demo | document | url | user_input
source_ref: string | null
confidence: number  # 0.0–1.0
needs_confirmation: boolean
created_at: datetime
```

约束：

- `raw_text` 保留原通知，不用模型摘要覆盖。
- `confidence < 0.75` 或关键时间不明确时，`needs_confirmation=true`。
- 一条通知可以包含多个 `actions`。

### 4.2 Course

```text
id: string
student_id: string
name: string
teacher: string | null
weekday: integer  # 1–7
start_time: string  # HH:mm
end_time: string  # HH:mm
location: string | null
start_week: integer
end_week: integer
week_pattern: all | odd | even | custom
custom_weeks: integer[]
```

### 4.3 Task

```text
id: string
student_id: string
title: string
description: string | null
task_type: registration | exam | assignment | course | activity | general
priority: critical | high | medium | normal
status: pending | completed | cancelled
due_at: datetime | null
source_notice_id: string | null
dedupe_key: string
created_at: datetime
completed_at: datetime | null
```

约束：

- `dedupe_key` 必须唯一。
- 相同学生、来源和行动不得重复创建。
- 任务完成后必须保存 `completed_at`。

### 4.4 StudentProfile

```text
id: string
name: string
major: string | null
grade: string | null
timezone: string  # 默认 Asia/Shanghai
quiet_hours_start: string | null
quiet_hours_end: string | null
interests: string[]
reminder_preferences: object
```

### 4.5 Reminder

```text
id: string
task_id: string
trigger_at: datetime
channel: in_app
status: pending | sent | skipped | failed
sent_at: datetime | null
failure_reason: string | null
```

## 5. 公共 API

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

### 5.1 成功响应

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "request_id": "req-001"
}
```

### 5.2 失败响应

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "NOTICE_DATE_AMBIGUOUS",
    "message": "无法确认通知中的年份",
    "details": {}
  },
  "request_id": "req-001"
}
```

前端只能依赖稳定的 `error.code`，不得解析 `message` 判断业务状态。

## 6. 最低错误码

| Code | 含义 |
| --- | --- |
| `VALIDATION_ERROR` | 输入字段无效 |
| `STUDENT_NOT_FOUND` | 学生不存在 |
| `NOTICE_EMPTY` | 通知正文为空 |
| `NOTICE_DATE_AMBIGUOUS` | 年份或截止时间不明确 |
| `NOTICE_NOT_APPLICABLE` | 通知不适用当前学生 |
| `TASK_DUPLICATE` | 任务已存在 |
| `TASK_NOT_FOUND` | 任务不存在 |
| `COURSE_NOT_FOUND` | 指定日期没有课程 |
| `RAG_NO_SOURCE` | 知识库没有可靠来源 |
| `AGENT_TOOL_FAILED` | Agent Tool 执行失败 |
| `MODEL_UNAVAILABLE` | 模型不可用或超时 |
| `INTERNAL_ERROR` | 未分类内部错误 |

Agent 3 可以新增更具体的错误码，但不得改变以上含义。新增项必须写入 HANDOFF。

## 7. Tool 契约

### get_today_brief

输入：`student_id`、`date`、`timezone`。

输出：

```json
{
  "date": "2026-08-18",
  "courses": [],
  "tasks": [],
  "notices": [],
  "conflicts": [],
  "suggestions": []
}
```

### parse_notice

输入：`text`、`student_id`、`reference_time`。

输出必须兼容 `Notice`，并包含 `confidence` 与 `needs_confirmation`。

### create_task

输入必须兼容 `Task` 创建字段。输出包含：

```json
{
  "task": {},
  "created": true,
  "duplicate_of": null
}
```

### get_courses

输入：`student_id`、`date`。输出：`Course[]`。

### complete_task

输入：`student_id`、`task_id`。输出：更新后的 `Task`。

## 8. Stub 与 Mock 契约

当其他 Agent 的模块尚未完成时：

- Agent 1 使用遵循公共模型的 Fake Repository/Service。
- Agent 2 不依赖 Agent Runtime 或前端。
- Agent 3 使用内存 Repository Stub 验证 Service/API。
- Agent 4 使用固定 JSON Mock 验证页面。
- Stub/Mock 放在当前 Agent 自己拥有的测试或 mock 目录。
- 不得把 Stub 当成最终生产实现。
- HANDOFF 必须列出仍在使用的 Stub/Mock 及替换位置。

## 9. 目录所有权

| Agent | Owns | Must NOT modify |
| --- | --- | --- |
| 1 | `skills/`、`campusmind/tools/`、`campusmind/integrations/`、`tests/agent/` | `domain/`、`storage/`、`services/`、`apps/web/` |
| 2 | `campusmind/domain/`、`storage/`、`repositories/`、`data/`、`tests/storage/`、`tests/rag/` | `skills/`、`services/`、`apps/api/`、`apps/web/` |
| 3 | `campusmind/services/`、`apps/api/`、`tests/services/`、`tests/api/` | `domain/`、`storage/`、`skills/`、`apps/web/` |
| 4 | `apps/web/` | `campusmind/`、`skills/`、`apps/api/` |
| 0 | 集成所需全项目 | 不得无必要重写已通过测试的模块 |

## 10. 数据与安全契约

- 只使用明确标识的模拟学生数据。
- 不读取、提交或记录真实校园账号、Cookie、密码和 Token。
- `.env`、数据库运行文件、日志中的密钥必须被忽略。
- RAG 资料必须保存 `source_id`、标题、有效日期、路径/URL 和模拟标记。
- 无可靠来源时返回 `RAG_NO_SOURCE`。
- Agent 输出不能把模型记忆当作学校正式规定。

## 11. Git 与分支契约

推荐分支：

```text
agent/1-runtime
agent/2-data-rag
agent/3-service-api
agent/4-web
agent/0-integration
```

规则：

- 每个 Agent 使用独立 worktree 或独立克隆。
- 子 Agent 不得直接推送目标仓库 `main`。
- 子 Agent 只提交自己拥有的文件和 HANDOFF。
- Commit 使用 `feat:`、`fix:`、`test:`、`docs:` 等清晰前缀。
- Agent 0 按 HANDOFF 顺序合并到 `agent/0-integration`。
- 最终只将集成分支推到目标仓库预览分支，未经确认不合并 `main`。

如果使用双远程：

```text
origin = 用户自己的 Agent 施工仓库
target = yee01001100/CampusMind-AI
```

独立且无 fork 关系的仓库不能直接创建跨仓 PR，但具备目标仓库推送权限时，可以将本地集成提交推到 `target` 的新分支。

## 12. 统一完成条件

子 Agent 只有同时满足以下条件才可以停止：

- 完成 Execution Packet 的全部 Must Implement。
- 运行并通过规定测试。
- 正常、空数据和异常路径均有覆盖。
- 没有修改 Must NOT modify 的目录。
- 没有遗留无说明的 TODO、空函数或占位返回。
- 创建 `HANDOFF-agentN.md`。
- HANDOFF 包含文件、接口、测试、Stub/Mock、限制和集成步骤。

禁止以“基础框架已完成”“主体已经实现”“下一步可以继续”为结束结论。

## 13. 契约变更

只有 Stage 0 或 Agent 0 集成阶段可以修改本契约。修改时必须：

1. 说明旧值、新值和原因。
2. 标出受影响的 Agent 与文件。
3. 同时更新 Mock、测试和调用方。
4. 在最终交付说明中记录。

---

下一步：根据身份进入对应的 [Agent Execution Packet](../README.md#先读这里)。
