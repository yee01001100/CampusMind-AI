# AGENT 0 — Integrator / Debug / UI / Release

> 必读：[README](../../README.md) · [Shared Contract](../../contracts/SHARED_CONTRACT.md) · [HANDOFF 模板](../HANDOFF_TEMPLATE.md) · [最终验收](../FINAL_ACCEPTANCE.md)

Agent 0 由组长与主 AI 共同承担，是项目总装角色。组长负责确认合并范围、风险和最终发布；主 AI 负责读取四份 HANDOFF、持续集成、Debug 和验证。只有 Agent 1–4 完成各自分支与 HANDOFF 后才开始修改代码。Day 1–4 不与子 Agent 同时施工；Day 5–8 用一轮持续工作完成集成、Debug、UI 改进和发布验证。

## Goal

将四个独立模块合并为一个真实可启动、可测试、可演示的 CampusMind。解决接口、依赖和运行问题，但不重新设计产品或扩展功能范围。

## Required Input

按顺序读取：

1. `README.md`
2. `contracts/SHARED_CONTRACT.md`
3. `docs/agents/AGENT-0.md`
4. `HANDOFF-agent1.md`
5. `HANDOFF-agent2.md`
6. `HANDOFF-agent3.md`
7. `HANDOFF-agent4.md`
8. 四个子 Agent 分支的提交和源码
9. `docs/FINAL_ACCEPTANCE.md`

缺少任意 HANDOFF 时，先检查对应分支是否满足停止条件。不要在不了解模块契约的情况下直接重写。

## Branch

```text
agent/0-integration
```

如果使用双远程：

```text
origin = 用户自己的 Agent 施工仓库
target = yee01001100/CampusMind-AI
```

Agent 0 只将最终集成分支推到目标仓库的新预览分支，未经用户确认不得合并 `main`。

## Merge Order

推荐按依赖顺序合并：

1. Agent 2：Data / SQLite / RAG
2. Agent 3：Service / FastAPI
3. Agent 1：DeepTutor / Tool / Runtime
4. Agent 4：Web

每合并一个模块就运行其测试，不要四个分支一次合完再排错。

示例流程：

```powershell
git fetch origin --tags
git switch -c agent/0-integration day0-baseline
git merge --no-ff origin/agent/2-data-rag
git merge --no-ff origin/agent/3-service-api
git merge --no-ff origin/agent/1-runtime
git merge --no-ff origin/agent/4-web
```

实际分支名以远程为准。`day0-baseline` 必须存在，并且是四个子 Agent 最终提交的共同祖先。

## Allowed Work

- 合并四个分支。
- 解决类型、导入、依赖和配置冲突。
- 将 Stub/Mock 替换为真实模块。
- 编写最少必要的 glue code。
- 修复单元、集成和端到端 Bug。
- 补齐启动脚本和环境变量示例。
- 改进错误状态、响应式、视觉一致性和演示体验。
- 补充最终测试和启动文档。

## Forbidden Work

- 更换 Shared Contract 中的技术栈。
- 增加 README 之外的新产品功能。
- 因个人偏好重写已通过测试的子 Agent 模块。
- 删除失败测试来获得绿色结果。
- 将 Demo Mock 当成真实实现。
- 直接修改或强推目标仓库 `main`。
- 隐藏已知问题或伪造测试结果。

## Integration Sequence

### 1. 建立基线

- 确认四个分支有共同祖先或可追踪基线。
- 确认本地工作区干净。
- 保存四个分支的提交 SHA。
- 创建 `agent/0-integration`。

### 2. 合并 Data

- 运行 storage/RAG 测试。
- 初始化演示数据库。
- 验证 Pydantic 模型和来源数据。
- 记录公共模型的真实导入路径。

### 3. 合并 Service/API

- 替换内存 Repository Stub。
- 修复模型导入与错误映射。
- 运行 Service/API 测试。
- 启动 `/api/health` 和 OpenAPI。

### 4. 合并 Agent Runtime

- 将 Fake Service 替换为真实 Service/API。
- 验证五个 Tool 输入输出。
- 验证 RAG 和 Memory 边界。
- 检查 Tool Trace、超时和失败状态。

### 5. 合并 Web

- 将 Mock API 切换到真实 API Client。
- 保留 Mock 作为测试 fixture，不用于正式演示数据流。
- 验证流式 Chat、Tool 状态和来源展示。
- 修复 CORS、端口和环境变量。

### 6. 全项目启动

- 建立一个明确的启动入口或顺序。
- 验证全新 Windows 环境安装步骤。
- 验证 Ctrl+C 或停止流程不会遗留关键服务。
- 不要求安装与 MVP 无关的额外系统组件。

## Day 5 — 全链路 Debug

优先处理：

- 无法启动。
- 模型、数据库和 API 连接失败。
- 字段和错误码不一致。
- 重复通知、重复任务和重复提醒。
- Tool 误调用、重复调用和失败后编造。
- Loading 不结束、白屏和未捕获异常。

所有 P0/P1 Bug 必须有复现步骤和回归结果。

## Day 6 — 稳定性与响应式

- 测试服务重启、数据库重开和重新索引。
- 测试模型超时、RAG 无结果和流式中断。
- 检查多学生隔离和勿扰时间。
- 检查 `375 × 812`、`1366 × 768`、`1440 × 900`。
- 修复长文本、遮挡、滚动和重复点击。

## Day 7 — 回归与 UI 改进

- 第一屏突出下一节课和最高优先级任务。
- Tool 状态可见但不暴露冗长内部日志。
- 通知原文、解析结果、确认和创建任务形成清晰步骤。
- 高优先级、逾期和普通事项有稳定视觉区分。
- 统一颜色、间距、字体、卡片、按钮和状态反馈。
- 动画只用于解释状态变化，不拖慢操作。
- 三个核心场景连续运行三次。

## Day 8 — 发布验证

- 冻结代码，只修阻止演示或发布的问题。
- 在全新目录验证安装和启动。
- 运行全部自动测试。
- 按 Final Acceptance 完成人工验收。
- 生成 Demo 视频、备用录屏、截图和已知限制。
- 将集成分支推到目标仓库预览分支。

## Required Commands

根据子 Agent HANDOFF 使用真实命令，最低必须运行：

```powershell
python -m pytest -q
```

在前端目录运行：

```powershell
npm test
npm run build
```

如果脚本名称不同，以 Agent 4 HANDOFF 为准，并在集成报告中记录。

## Final Scenarios

### A. 今日简报

```text
“今天有什么事情？”
→ Agent
→ get_today_brief
→ Service
→ SQLite
→ H5 展示
```

### B. 通知转任务

```text
粘贴校园通知
→ Agent 提取
→ Service 校验
→ 用户确认
→ Task 入库
→ H5 可见
```

### C. 校园问答

```text
询问学校规定
→ RAG
→ 返回答案
→ 显示来源
```

### D. 主动提醒

```text
临期 Task
→ Reminder
→ 完成 Task
→ 后续提醒被跳过
```

## Acceptance

完整执行 [FINAL ACCEPTANCE](../FINAL_ACCEPTANCE.md)。必须做到：

- 全部 P0/P1 关闭。
- 自动测试通过。
- 四个场景连续通过三轮。
- UI 三种尺寸可操作。
- 无密钥和真实个人信息泄露。
- 目标仓库 `main` 未被直接覆盖。

## Finish

创建：

```text
docs/INTEGRATION_REPORT.md
```

至少包含：

- 合并的四个分支和 SHA。
- 实际启动命令。
- 自动测试结果。
- 四个场景结果。
- 修复的集成 Bug。
- UI 改进。
- 已知限制。
- 目标仓库预览分支和提交 SHA。

只有项目真实可运行、验收完成并推送预览分支后，Agent 0 才能停止。
