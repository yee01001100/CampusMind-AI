# CampusMind AI 集成报告

日期：2026-08-21

分支：`agent/0-integration`

执行角色：Agent 0（组长 + 主 AI）

发布范围：只允许 `guiyuanzhuomin-oss/CampusMind-AI-Agents`

## 1. 结论

四个子 Agent 已按 Data → Service/API → Runtime → Web 的顺序合并。SQLite、业务 Service、五个 Agent Tool、本地 RAG、FastAPI 和 React H5 已形成一个可启动、可测试的本地 MVP。

代码级 P0/P1 问题已清零，Python、Web、构建、Mock 浏览器 QA 和真实 API 浏览器 QA 均通过。所有真实浏览器 QA 使用模拟校园数据；最终真实联调进程显式清空 `DEEPSEEK_API_KEY`，运行模式为 `local-rules`。

## 2. 合并记录

| 模块 | 子分支最终提交 | 集成合并提交 | 子模块交接结果 |
| --- | --- | --- | --- |
| Agent 2 Data/RAG | `b5c063f` | `6def5ed` | 38 tests，Day 0 / Contract / pip check 通过 |
| Agent 3 Service/API | `0ebbbe7` | `f24e0a1` | 79 tests，Day 0 通过 |
| Agent 1 Runtime | `027ab705` | `60d4196` | 32 tests 通过 |
| Agent 4 Web | `e0b54cf` | `93b50d2` | 20 tests，build，三尺寸浏览器 QA 通过 |

四份输入交接：

- `HANDOFF-agent1.md`
- `HANDOFF-agent2.md`
- `HANDOFF-agent3.md`
- `HANDOFF-agent4.md`

## 3. 集成实现

### 3.1 Composition Root

`apps/api/integration.py` 是正式入口，负责：

1. 解析 `CAMPUSMIND_DB_PATH`。
2. 初始化 SQLite schema。
3. 幂等导入 `data/demo` 与 `data/knowledge`。
4. 将 SQLite Repository 适配给 Service。
5. 将 Service 适配为 Runtime 的五个 Tool。
6. 将本地 RAG 接入 `rag_search`。
7. 将 Agent Chat Facade 接入统一 FastAPI envelope。

正式启动命令：

```powershell
.\.venv\Scripts\python.exe -m uvicorn apps.api.integration:app --env-file .env --host 127.0.0.1 --port 8000
```

### 3.2 Web

真实 API Client 已适配后端的嵌套 payload 和统一 envelope：

- 通知解析解包 `data.notice`。
- 今日课程解包 `data.courses`。
- Chat 将同步 Agent envelope 转换为 UI 的 Tool、文本、来源和完成事件。
- 测试环境强制 Mock，避免本机 `.env.local` 污染单元测试。
- 正式演示使用 `VITE_USE_MOCKS=false`。

## 4. Agent 0 修复的问题

| 级别 | 问题 | 修复与回归 |
| --- | --- | --- |
| P1 | SQLite Repository 缺少 Service 所需的 save/list 接口 | 增加 Task upsert、按 Notice 查询、Reminder 全量查询；集成测试覆盖持久化和重启 |
| P1 | Chat Facade 为 async，但 API 按同步返回处理 | API 检测 awaitable 并等待；真实 Chat/RAG 测试通过 |
| P1 | 浏览器只支持 5173 CORS，QA 的 4173 被阻止 | 增加 localhost/127.0.0.1 的 4173；OPTIONS 回归测试通过 |
| P1 | 前端发送 UTC `Z`，北京时间零点附近“本周五”会算到上周 | Notice Service 先转 `Asia/Shanghai`；增加 UTC→上海回归测试 |
| P1 | 完成任务后恢复，未来 Reminder 仍停留在 skipped | `schedule()` 幂等恢复未来 skipped 提醒；Service 和全栈测试覆盖 |
| P1 | 真实前端按 Mock 形状读取 Notice/Course/Chat | Real API Client 统一解包并映射 RAG 来源；Web 单测和真实流程通过 |
| P2 | 404/405 未遵循统一 envelope | 增加 Starlette HTTPException 映射和回归测试 |
| P2 | Planner “今天截止”、页面日期和冲突为硬编码 | 使用 `Asia/Shanghai` 动态日期并按真实课程计算冲突 |
| P2 | 浏览器自动请求图标产生 404 控制台错误 | 增加内嵌 SVG favicon；真实 QA 控制台错误为 0 |
| P2 | `.env.local` 的真实模式污染 Vitest | `MODE=test` 固定使用 Mock；22 个 Web 测试恢复稳定 |
| P1 | 系统环境残留 Key 会让集成入口自动进入在线模型 | 增加 `CAMPUSMIND_MODEL_MODE` 显式开关，默认移除 Runtime 可见 Key；回归测试确认仍为 local-rules |

## 5. 自动验收

以下结果来自 2026-08-21 的最终工作树：

| 命令 | Exit | 结果 |
| --- | ---: | --- |
| `.venv\Scripts\python.exe -m pip install -e ".[dev]"` | 0 | 根 `pyproject.toml` 可编辑安装成功 |
| `.venv\Scripts\python.exe -m pytest -q` | 0 | `161 passed`，`0 failed`，1 条第三方弃用警告 |
| `.venv\Scripts\python.exe scripts\check_day0.py` | 0 | PASS，Python 3.12 |
| `.venv\Scripts\python.exe scripts\check_contracts.py` | 0 | 5 个模型样例和 2 个 API envelope 通过 |
| `.venv\Scripts\python.exe -m pip check` | 0 | No broken requirements |
| `npm test -- --reporter=dot` | 0 | `22 passed`，`0 failed` |
| `npm run build` | 0 | TypeScript + Vite 构建，43 modules |
| `npm run qa:browser` | 0 | Mock 模式三尺寸、四页面、长文本和完整流程通过 |
| `npm run qa:real` | 0 | 真实 API 三尺寸、四页面、0 横向溢出、0 控制台错误；通知→任务→RAG 来源通过 |

第三方警告来自 FastAPI `TestClient` 对当前 `httpx` 路径的弃用提示，不影响测试结果；后续依赖升级时应跟踪 FastAPI/Starlette 的推荐替代方案。

## 6. 四个核心场景

### A. 今日简报

`/api/v1/chat` 识别“今天有什么事情？”，调用 `get_today_brief`，从 SQLite 返回课程、任务、通知、冲突和建议。测试断言 Tool Trace 为 success，Runtime 为 `local-rules`。

### B. 通知转任务

通知原文入库后返回不确定字段，用户确认再调用任务创建 API。`dedupe_key` 防止重复任务；SQLite 重开后任务仍存在。

### C. 校园 RAG

“学校规定考试管理是什么？”返回非过期的“模拟考试管理规定”及来源。无来源问题返回 `RAG_NO_SOURCE`，不会用模型常识补学校规定。

### D. 主动提醒

创建任务时按类型生成未来 Reminder；完成/取消后 future pending 变为 skipped；恢复任务时重新激活未来 Reminder；重启后 pending 状态可恢复。

`tests/integration/test_full_stack.py` 按 A → B → C → D 连续执行三轮，全部通过。

## 7. 浏览器验收

尺寸：

- `375 × 812`
- `1366 × 768`
- `1440 × 900`

检查结果：

- 移动端底部导航和桌面侧栏切换正确。
- 四个页面均可进入，无横向滚动。
- 通知人工确认、创建任务和 Planner 持久化可见。
- Chat Tool 状态和 RAG 来源可见，不展示内部推理。
- Loading、Empty、Error、Partial、Long text 和中断/超时已有 Web 测试覆盖。
- 最终真实 QA 控制台错误为 0。

截图生成在 `apps/web/.qa-artifacts/`，该目录被 Git 忽略，不作为源码提交。

## 8. 安全检查

- `.env`、`.env.local`、SQLite 运行库和 QA 截图均被忽略。
- 可提交的 `.env.example` 不包含任何凭据变量名，符合 Day 0 安全检查。
- 前端 `VITE_*` 不包含模型密钥。
- 集成入口默认 `CAMPUSMIND_MODEL_MODE=local-rules`，会移除 Runtime 可见 Key；最终真实 QA 也显式清空 Key。
- 演示资料全部使用模拟描述，不含真实学生隐私、校园账号、Cookie 或密码。
- 发布前凭据签名扫描命中文件为 0；提交时只显式暂存本报告列出的项目文件。

## 9. 已知限制

1. 未安装或修改 DeepTutor 上游核心；公开 Host 桥用 Fake Host 验证。
2. DeepSeek Transport 由 Fake Transport 测试；在线模型响应不是本次交付证据。
3. RAG 是本地字符二元组词法检索，不是向量检索；默认排除过期资料。
4. 所有校园数据是模拟数据，不连接真实教务、认证或消息推送平台。
5. Reminder 没有生产级常驻后台调度器；MVP 提供持久化、到期查询、停止和恢复。
6. 演示学期起始日和部分资料日期固定在 2026 年 8 月；真实部署前需配置化并更新数据。
7. CORS 只允许本地 `5173` 和 QA `4173`。
8. Demo 视频、PPT 和答辩录屏属于比赛展示物料，不在本代码分支内生成。

## 10. 发布边界

本轮只发布：

```text
origin = https://github.com/guiyuanzhuomin-oss/CampusMind-AI-Agents.git
branch = agent/0-integration
```

`target = https://github.com/yee01001100/CampusMind-AI.git` 只保留为协作目标引用。本轮不推送 `target`，不修改任何仓库的 `main`。
