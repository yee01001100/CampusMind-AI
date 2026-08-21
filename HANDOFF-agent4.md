# HANDOFF — Agent 4

## Identity

- Role: Agent 4 / React + Vite + TypeScript H5
- Team member: CampusMind 组员（Agent 4）
- AI partner: `/root/agent4_web`
- Branch: `agent/4-web`
- Base commit: `13ae67ab371834c4904bfd1d45ea2eadc8d83bbd` (`day0-baseline`)
- Final implementation commit: `00feb27b22d27b5b8d4a7123c22df3c0fcf5c563`
- Finished at: `2026-08-21T20:08:30+08:00`

## Goal Result

完整交付了 CampusMind 响应式 H5，而不是页面骨架。今日简报、通知解析与人工确认、任务防重复创建、课表、待办完成/恢复/取消、Reminder 状态、Chat 流式回复、Tool 状态、RAG 来源和重试流程均可在固定 Mock 下独立走通。页面只通过单一 API Client 访问后端；真实模式不需要改写页面，也不会读取、保存或打包模型密钥。Loading、Empty、Error、Partial data、Long text、Offline、Timeout 和 Tool running/success/failure 均有实现与测试/演示入口。

## Created Files

- `apps/web/package.json`、`apps/web/package-lock.json`
- `apps/web/tsconfig.json`、`apps/web/tsconfig.app.json`、`apps/web/tsconfig.node.json`、`apps/web/vite.config.ts`
- `apps/web/index.html`、`apps/web/.env.example`、`apps/web/.gitignore`
- `apps/web/README.md`、`apps/web/PRODUCT.md`、`apps/web/DESIGN.md`
- `apps/web/src/main.tsx`、`apps/web/src/App.tsx`、`apps/web/src/styles.css`
- `apps/web/src/types.ts`、`apps/web/src/utils.ts`、`apps/web/src/vite-env.d.ts`
- `apps/web/src/api/client.ts`、`apps/web/src/api/client.test.ts`
- `apps/web/src/components/Icon.tsx`、`apps/web/src/components/StateView.tsx`
- `apps/web/src/pages/DashboardPage.tsx`
- `apps/web/src/pages/NoticePage.tsx`
- `apps/web/src/pages/PlannerPage.tsx`
- `apps/web/src/pages/ChatPage.tsx`
- `apps/web/src/mocks/today-brief.json`
- `apps/web/src/mocks/notice-result.json`
- `apps/web/src/mocks/courses.json`
- `apps/web/src/mocks/tasks.json`
- `apps/web/src/mocks/reminders.json`
- `apps/web/src/mocks/errors.json`
- `apps/web/src/App.test.tsx`、`apps/web/src/test/setup.ts`
- `apps/web/scripts/qa-browser.mjs`
- `HANDOFF-agent4.md`

## Modified Files

无。除本 HANDOFF 外，所有交付都在原本为空的 `apps/web/` 内新增。

## Public Interfaces

### CampusMind API Client

- Name: `CampusMindApi` / `apiClient`
- Import / URL: `apps/web/src/api/client.ts`
- Input: Shared Contract 的 `student_id`、Notice 文本、Task 状态与 Chat 消息。
- Output: `TodayBrief`、`Notice`、`Course[]`、`Task[]`、`Reminder[]`、`CreateTaskResult`、`AsyncGenerator<ChatEvent>`。
- Error: 统一抛出 `ApiError`，页面只依赖稳定 `error.code` 和面向用户的 `message`，不解析业务消息判断状态。
- Example: `await apiClient.getTodayBrief()`；`for await (const event of apiClient.streamChat(message))`。

实现方法：

- `getTodayBrief` → `GET /api/v1/brief/today`
- `parseNotice` → `POST /api/v1/notices/parse`
- `createTaskFromNotice` → `POST /api/v1/tasks`
- `getTodayCourses` → `GET /api/v1/courses/today`
- `listTasks` → `GET /api/v1/tasks`
- `updateTask` → `PATCH /api/v1/tasks/{task_id}`
- `listDueReminders` → `GET /api/v1/reminders/due`
- `streamChat` → `POST /api/v1/chat`

### Mock / Real Switch

- Name: `createApiClient`
- Import / URL: `apps/web/src/api/client.ts`
- Input: `VITE_USE_MOCKS`、`VITE_API_BASE_URL`
- Output: `MockCampusMindApi` 或真实后端 Client。
- Error: Mock 覆盖固定错误；Real Client 将 API envelope 错误转为 `ApiError`。
- Example: `VITE_USE_MOCKS=false` 后重启 Vite，只替换 API 数据源，不修改页面。

## Contract Compliance

- [x] 使用 Shared Contract 公共字段
- [x] 未创建第二套同义字段
- [x] 未修改 Must NOT modify 目录
- [x] 分支从 `day0-baseline` 创建（该标签是当前分支祖先）
- [x] 时区与时间格式正确（API/Mock 为带 `+08:00` 的 ISO 8601，显示使用 `Asia/Shanghai`）
- [x] 未提交真实个人数据或密钥

Task 和 Reminder 保持为两个独立公共模型；前端通过 `task_id` 关联，不在 Task 上增加 `reminder_at` 私有字段。

## Commands

### Install

```powershell
Set-Location apps/web
npm install
Copy-Item .env.example .env
```

### Run

```powershell
Set-Location apps/web
npm run dev
```

### Test

```powershell
Set-Location apps/web
npm test
npm run build
npm run dev -- --port 4173
npm run qa:browser
```

### Switch to Real Backend

```text
VITE_USE_MOCKS=false
VITE_API_BASE_URL=http://127.0.0.1:8000
```

不得把模型供应商 Key 写入 `VITE_*`；Vite 会把这些值暴露给浏览器。

## Test Results

- Command: `D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe scripts\check_day0.py`
- Exit code: `0`
- Passed: `Day 0 baseline PASS on Python 3.12`
- Failed: `0`
- Skipped: `0`
- Important output: `PASS: Day 0 baseline is ready on Python 3.12`

- Command: `npm test`
- Exit code: `0`
- Passed: `20`
- Failed: `0`
- Skipped: `0`
- Important output: `2 test files passed`；覆盖正常/空/局部缺失/长文本/错误/离线/超时、通知确认与防重复、待办完成恢复、Reminder 停止恢复、流式中断重试、Tool 失败、RAG 来源和键盘焦点。

- Command: `npm run build`
- Exit code: `0`
- Passed: TypeScript project build + Vite production build；`43 modules transformed`
- Failed: `0`
- Skipped: `0`
- Important output: JS `234.35 kB`（gzip `73.12 kB`）；CSS `25.22 kB`（gzip `5.91 kB`）。

- Command: `npm run qa:browser`（本地 Playwright 复用系统 Microsoft Edge）
- Exit code: `0`
- Passed: `3` 个目标尺寸 × `4` 个主要页面；`1` 条端到端 Mock 流程
- Failed: `0`
- Skipped: `0`
- Important output: `375×812`、`1366×768`、`1440×900` 均无横向溢出；桌面/移动导航、长文本通过；走通 `通知解析 → 人工确认 → 创建任务 → Chat`。截图在本机 `apps/web/.qa-artifacts/` 生成并人工检查，该目录按设计不提交。

## Stub / Mock

| Path | Simulates | Must be replaced by | Replacement step |
| --- | --- | --- | --- |
| `apps/web/src/mocks/today-brief.json` | 今日简报 | Agent 3 + Agent 1/2 真实链路 | 设置 `VITE_USE_MOCKS=false` |
| `apps/web/src/mocks/notice-result.json` | 通知解析 | `POST /api/v1/notices/parse` | 设置真实 API 地址并核对响应 envelope |
| `apps/web/src/mocks/courses.json` | 今日课程 | `GET /api/v1/courses/today` | 同上 |
| `apps/web/src/mocks/tasks.json` | 待办与状态 | Task API | 同上 |
| `apps/web/src/mocks/reminders.json` | Reminder 与完成后停止提醒 | `GET /api/v1/reminders/due` + Task PATCH | 同上 |
| `apps/web/src/mocks/errors.json` | 业务错误、离线、超时、Tool 失败 | Agent 3/1 真实错误 | 保留作前端回归，不在生产模式加载 |

## Environment Variables

| Name | Required | Secret | Purpose | Example without secret |
| --- | --- | --- | --- | --- |
| `VITE_USE_MOCKS` | 否，默认 Mock | 否 | 在固定 Mock 与真实 API 间切换 | `true` |
| `VITE_API_BASE_URL` | 真实模式需要 | 否 | FastAPI 基础地址 | `http://127.0.0.1:8000` |

前端不定义模型 Key、Token、Cookie 或校园账号变量。

## Known Limitations

1. 尚未与 Agent 3 的最终 FastAPI 实例联调；字段与路径已按 Shared Contract 实现。
2. 真实 `POST /api/v1/chat` 当前按 chunked text 读取。若 Agent 3 最终采用 SSE `data:` 或结构化 JSON event，Agent 0 只需在 `RealCampusMindApi.streamChat` 内做协议适配，页面不需修改。
3. Mock 日期固定为 `2026-08-21` 便于稳定演示；真实模式日期完全由后端返回。
4. Codex in-app Browser 在本机初始化时报 `Cannot redefine property: process`；已用独立 Playwright + 系统 Edge 完成真实页面尺寸、截图和流程 QA，不影响项目运行。

## Integration Steps for Agent 0

1. 将 `agent/4-web` 合并到 `agent/0-integration`。
2. 在 `apps/web/` 运行 `npm install`。
3. 保持 `VITE_USE_MOCKS=true`，先运行 `npm test`、`npm run build` 和完整 Mock 演示。
4. 启动 Agent 3 FastAPI，配置 `VITE_USE_MOCKS=false` 与 `VITE_API_BASE_URL`。
5. 核对所有 API 成功/失败 envelope；重点对齐 `/api/v1/chat` 的流式传输格式。
6. 重跑 `npm test`；启动 4173 端口后运行 `npm run qa:browser`。
7. 手动走通“今日简报 → 通知解析 → 人工确认 → 创建任务 → 待办 → Chat/RAG 来源”。

## Behaviors That Must Not Break

- 不确定通知必须确认后才能创建任务。
- 连续点击不能重复创建相同 `dedupe_key` 的任务。
- 任务完成/取消后 Reminder 变为 `skipped`；恢复后可回到 `pending`。
- 错误判断依赖 `error.code`，不解析中文 `message`。
- Chat 只展示 Tool/RAG 状态和回答，不展示内部推理或敏感日志。
- 375px 使用固定底部导航，桌面使用左侧导航；长文本不得产生横向溢出。
- 前端不得接触或打包模型密钥。

## Remaining Blockers

无 Agent 4 内部阻塞。真实联调依赖 Agent 3 最终 API 和 Agent 1 最终 Chat 流式事件格式，由 Agent 0 集成阶段完成。

## Final Statement

COMPLETE — 全部 Agent 4 验收通过，可以交给 Agent 0。
