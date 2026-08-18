# AGENT 1 — DeepTutor / Runtime

> 必读：[README](../../README.md) · [Shared Contract](../../contracts/SHARED_CONTRACT.md) · [HANDOFF 模板](../HANDOFF_TEMPLATE.md) · [最终验收](../FINAL_ACCEPTANCE.md)

本角色由一名组员与其 AI 搭档共同承担。组员负责确认范围、检查文件、运行测试和推送分支；AI 负责持续实现、自检并起草 HANDOFF。双方共同对验收结果负责。

## Goal

一次完成 CampusMind 的 DeepTutor 接入层：让 Agent 能根据用户意图选择校园 Tool，正确处理结果和失败状态，并保留可用于 Debug 与答辩的调用轨迹。

## Input

- `README.md`
- `contracts/SHARED_CONTRACT.md`
- Agent 2/3 尚未完成时，由本角色按公共契约创建的 Fake Repository/Service
- DeepTutor 官方扩展接口

## Owns

```text
skills/campusmind/
campusmind/tools/
campusmind/integrations/deeptutor/
apps/api/agent/
tests/agent/
HANDOFF-agent1.md
```

## Must NOT modify

```text
campusmind/domain/
campusmind/storage/
campusmind/repositories/
campusmind/services/
apps/web/
data/
contracts/SHARED_CONTRACT.md
docs/agents/AGENT-2.md
docs/agents/AGENT-3.md
docs/agents/AGENT-4.md
```

禁止修改 DeepTutor 核心来规避扩展接口。优先使用 Skill、MCP Tool、公开 SDK 或适配层。

## Must Implement

### 1. CampusMind Skill

创建 `skills/campusmind/SKILL.md`，明确：

- 哪些请求属于校园事务。
- 何时调用 `get_today_brief`、`parse_notice`、`create_task`、`get_courses`、`complete_task`。
- 何时使用 RAG。
- 何时读写学生偏好 Memory。
- 日期、对象和截止时间不明确时必须询问用户。
- 禁止从模型记忆编造课表、任务、截止时间和学校规定。
- Tool 返回失败时不得在自然语言中伪造成功。

### 2. Tool 适配层

实现 Shared Contract 中的五个 Tool：

```text
get_today_brief
parse_notice
create_task
get_courses
complete_task
```

每个 Tool 必须：

- 使用固定输入输出模型。
- 校验必要字段。
- 将底层异常转为稳定错误码。
- 支持异步执行。
- 不直接访问前端状态。
- 不把密钥或完整敏感输入写入日志。

### 3. Agent Runtime

- 初始化 DeepTutor。
- 注册 CampusMind Skill 与 Tool。
- 支持普通 Chat 和校园 Tool 调用。
- 将 Tool 名称、开始时间、结果状态和耗时写入结构化轨迹。
- 支持流式回复中断、模型超时和 Tool 超时。
- 保证同一用户请求不会无上限重复调用 Tool。

### 4. Memory 边界

允许进入 Memory：

- 专业、年级、兴趣、偏好、提醒习惯。

禁止只存在 Memory：

- 课表、任务状态、准确截止时间、正式学校规定。

## Work Sequence

1. 创建本角色分支 `agent/1-runtime`。
2. 建立最小 DeepTutor 启动验证。
3. 使用 Fake Service 注册一个 Tool 并保存调用轨迹。
4. 实现五个 Tool 的适配层。
5. 编写 CampusMind Skill。
6. 增加错误、超时、空数据和确认流程测试。
7. 运行验收命令。
8. 创建 `HANDOFF-agent1.md` 后停止。

## Stub / Mock

Agent 3 未完成时，可以在 `tests/agent/fakes/` 创建遵循 Shared Contract 的 Fake Service。

Fake 必须覆盖：

- 正常今日简报。
- 空数据。
- 模糊通知时间。
- 重复任务。
- Tool 失败和超时。

不得在 `campusmind/services/` 中代写 Agent 3 的实现。

## Required Tests

至少验证：

- “今天有什么事情”调用 `get_today_brief`。
- 普通闲聊不误调用校园 Tool。
- 模糊日期触发用户确认。
- Tool 失败时不伪造结果。
- RAG 无来源时返回无法确认。
- 重复 Tool 调用受到限制。
- Tool 轨迹包含名称、状态和耗时。
- Memory 不保存准确课表和任务状态。

运行：

```powershell
python -m pytest tests/agent -q
```

如果项目提供统一检查命令，也必须一并运行。

## Acceptance

本角色完成时，使用 Fake Service 也必须能够真实演示：

```text
用户问题
→ DeepTutor Agent
→ 选择 CampusMind Tool
→ 接收结构化结果
→ 输出中文回答
→ 保存 Tool Trace
```

测试全部通过，不存在无说明 TODO、空函数和永远成功的占位返回。

## Finish

按 [HANDOFF 模板](../HANDOFF_TEMPLATE.md) 创建仓库根目录下的：

```text
HANDOFF-agent1.md
```

HANDOFF 必须记录：

- DeepTutor 的接入方式和版本。
- 创建/修改文件。
- Tool 输入输出。
- 测试命令和真实结果。
- Fake Service 的位置和替换方法。
- 已知限制。
- Agent 0 的集成步骤。

完成 HANDOFF 后停止，不继续扩展 README 之外的能力。
