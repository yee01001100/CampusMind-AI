# AGENT 2 — Data / SQLite / RAG

> 必读：[README](../../README.md) · [Shared Contract](../../contracts/SHARED_CONTRACT.md) · [HANDOFF 模板](../HANDOFF_TEMPLATE.md) · [最终验收](../FINAL_ACCEPTANCE.md)

本角色由一名组员与其 AI 搭档共同承担。组员负责确认范围、检查文件、运行测试和推送分支；AI 负责持续实现、自检并起草 HANDOFF。双方共同对验收结果负责。

## Goal

一次完成 CampusMind 的结构化数据层和校园知识检索层，为 Agent、Service 和 Web 提供稳定、可重复初始化、可追溯的数据来源。

## Input

- `README.md`
- `contracts/SHARED_CONTRACT.md`
- 可公开的模拟校园通知、课表和规章资料
- Python 3.12 环境

## Owns

```text
campusmind/domain/
campusmind/storage/
campusmind/repositories/
data/demo/
data/knowledge/
tests/storage/
tests/rag/
HANDOFF-agent2.md
```

## Must NOT modify

```text
skills/
campusmind/tools/
campusmind/integrations/
campusmind/services/
apps/api/
apps/web/
contracts/SHARED_CONTRACT.md
```

## Must Implement

### 1. Pydantic 领域模型

实现 Shared Contract 中的：

```text
Notice
Course
Task
StudentProfile
Reminder
```

要求：

- 使用明确枚举和字段验证。
- 日期时间必须带时区。
- 对外序列化字段与 Shared Contract 完全一致。
- 不创建 `course_name`、`due_date` 等第二套同义字段。

### 2. SQLite Schema

- 为五个模型建立表或明确映射。
- 开启外键约束。
- 为 `Task.dedupe_key` 建立唯一索引。
- 实现可重复执行的初始化。
- 实现必要的 Repository CRUD。
- 测试数据库与演示数据库分离。
- 不提交本地运行产生的真实数据库文件。

### 3. Repository 接口

至少提供：

```text
NoticeRepository
CourseRepository
TaskRepository
StudentProfileRepository
ReminderRepository
```

必须支持：

- 按学生和日期查询。
- 任务创建与去重。
- 任务完成、恢复和状态查询。
- 按时间范围查询提醒。
- 保存通知原文和来源。

### 4. 演示数据

在 `data/demo/` 提供：

- 1 个模拟学生档案。
- 至少 8 门课程和单双周示例。
- 至少 8 条待办，覆盖不同优先级和状态。
- 至少 5 条校园通知。
- 至少 5 条提醒。
- 至少 2 组时间冲突。

所有数据明确标记为模拟，不包含真实个人信息。

### 5. RAG 资料与检索

在 `data/knowledge/` 准备：

- 2 份教务规章。
- 5 条校园通知。
- 1 份四六级报名说明。
- 1 份考试管理规定。
- 1 份竞赛或奖学金说明。

每份资料必须包含：

```text
source_id
title
source_type
published_at
effective_date
source_ref
is_demo
```

实现知识库导入和检索适配，返回答案片段时同时返回来源元数据。

## Work Sequence

1. 创建本角色分支 `agent/2-data-rag`。
2. 实现公共 Pydantic 模型。
3. 建立 SQLite Schema 和 Repository。
4. 编写可重复初始化和演示数据导入。
5. 建立 RAG 资料与检索测试。
6. 覆盖重复数据、空库、重启和无来源场景。
7. 运行验收命令。
8. 创建 `HANDOFF-agent2.md` 后停止。

## Independence Rules

- 不依赖 Agent Runtime。
- 不依赖前端。
- Service 未完成时直接测试 Repository。
- 不在本角色中实现业务优先级、提醒策略或 HTTP API。

## Required Tests

至少验证：

- 数据库可以重复初始化。
- 外键约束真实生效。
- 重复 `dedupe_key` 不会新增任务。
- 同一通知重复导入不会创建第二份记录。
- 不同学生数据互相隔离。
- 单双周课程查询正确。
- 数据库重启后记录仍存在。
- RAG 有资料时返回来源。
- RAG 无资料时返回 `RAG_NO_SOURCE`，不伪造学校规定。
- 过期资料携带有效期信息。

运行：

```powershell
python -m pytest tests/storage tests/rag -q
```

## Acceptance

Agent 3 即使尚未完成，也可以通过 Repository 和演示数据获得符合 Shared Contract 的结果。数据初始化、查询、去重和 RAG 检索均有自动测试。

## Finish

按 [HANDOFF 模板](../HANDOFF_TEMPLATE.md) 创建：

```text
HANDOFF-agent2.md
```

HANDOFF 必须记录：

- 模型与数据库文件。
- 初始化命令。
- Repository 对外接口。
- 演示数据说明。
- RAG 导入、查询和来源格式。
- 测试命令与真实结果。
- Agent 3/0 的接入步骤。
- 已知限制。

完成 HANDOFF 后停止，不代写 Service、API 或前端。
