# AGENT 4 — React / Vite / H5

> 必读：[README](../../README.md) · [Shared Contract](../../contracts/SHARED_CONTRACT.md) · [HANDOFF 模板](../HANDOFF_TEMPLATE.md) · [最终验收](../FINAL_ACCEPTANCE.md)

本角色由一名组员与其 AI 搭档共同承担。组员负责确认范围、检查文件、运行测试和推送分支；AI 负责持续实现、自检并起草 HANDOFF。双方共同对验收结果负责。

## Goal

一次完成 CampusMind 响应式 H5。先使用严格遵循 Shared Contract 的 Mock 独立开发，再通过单一 API 层切换到真实后端。

## Input

- `README.md`
- `contracts/SHARED_CONTRACT.md`
- Shared Contract 中的 API、模型和错误码
- Agent 3 尚未完成时的本地 Mock

## Owns

```text
apps/web/
HANDOFF-agent4.md
```

## Must NOT modify

```text
campusmind/
skills/
apps/api/
data/
contracts/SHARED_CONTRACT.md
```

不得为了前端方便修改后端字段。发现契约问题时记录到 HANDOFF，并在 `apps/web/src/api/` 内做最小适配。

## Must Implement

### 1. 工程基础

- React + Vite + TypeScript。
- 开发、构建、测试和预览命令。
- 环境变量示例，不提交真实 API 地址或密钥。
- API Client 与页面组件分离。
- 类型与 Shared Contract 对齐。

### 2. 今日简报

首屏必须清楚展示：

- 当前日期。
- 下一节课程。
- 今日任务完成情况。
- 最高优先级事项。
- 最新通知。
- 时间冲突。
- Agent 建议。

### 3. 通知解析

必须展示：

- 原通知正文。
- 标题、对象、截止时间、行动事项和优先级。
- 置信度与来源。
- 不确定字段的人工确认。
- “确认并创建任务”结果。
- 重复任务提示。

### 4. 课表与待办

课表：

- 今日课程和下一节课。
- 时间、地点和周次。
- 空闲时间与冲突提示。

待办：

- 日期和优先级分组。
- 完成、恢复和取消。
- 来源通知。
- 提醒时间。
- 逾期状态。

### 5. Chat 与 Agent 状态

- 用户与 Agent 消息。
- 流式回复。
- Tool 正在运行、成功和失败。
- RAG 来源。
- 超时、断线和重试。
- 不展示冗长内部推理或敏感日志。

### 6. 必须存在的 UI 状态

```text
Loading
Empty
Error
Partial data
Long text
Offline / timeout
Tool running / success / failure
Mobile navigation
```

### 7. 响应式尺寸

至少验证：

- `375 × 812`
- `1366 × 768`
- `1440 × 900`

## Mock Contract

在本角色目录内建立：

```text
apps/web/src/mocks/today-brief.json
apps/web/src/mocks/notice-result.json
apps/web/src/mocks/courses.json
apps/web/src/mocks/tasks.json
apps/web/src/mocks/errors.json
```

Mock 必须覆盖：

- 正常数据。
- 空数据。
- 局部缺失。
- 超长通知。
- 模糊日期。
- Tool 失败。
- 网络超时。

切换真实后端时只修改 `apps/web/src/api/`，不重写页面。

## Work Sequence

1. 创建本角色分支 `agent/4-web`。
2. 建立 Vite/React/TypeScript 项目。
3. 建立类型、API Client 和完整 Mock。
4. 完成今日简报、通知、课表、待办和 Chat 页面。
5. 补齐加载、空、错误和超时状态。
6. 完成响应式和可访问性检查。
7. 运行验收命令与构建。
8. 创建 `HANDOFF-agent4.md` 后停止。

## Required Tests

至少验证：

- Mock 与公共类型一致。
- 今日简报正常/空/失败状态。
- 通知确认和创建任务流程。
- 重复点击不会重复提交。
- 待办完成和恢复。
- 流式回复中断和重试。
- 长标题、长通知和窄屏。
- 键盘可操作主要控件。
- 三个目标尺寸没有关键遮挡。

运行项目实际提供的等价命令，最低要求：

```powershell
npm test
npm run build
```

如果测试脚本使用其他名称，HANDOFF 中必须给出真实命令和结果。

## Acceptance

在没有真实后端时，完整 Mock 也必须让用户走完：

```text
查看今日简报
→ 粘贴通知
→ 确认字段
→ 创建任务
→ 查看课表和待办
→ 查看 Agent Tool 与 RAG 来源状态
```

## Finish

按 [HANDOFF 模板](../HANDOFF_TEMPLATE.md) 创建：

```text
HANDOFF-agent4.md
```

HANDOFF 必须记录：

- 页面、组件和 API Client。
- 启动、测试和构建命令。
- Mock 文件及切换真实 API 的方法。
- 三种尺寸的验证结果。
- 已知 UI 限制。
- Agent 0 的集成步骤。

完成 HANDOFF 后停止，不代写后端或修改公共契约。
