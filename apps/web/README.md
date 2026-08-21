# CampusMind Web

React + Vite + TypeScript 的响应式校园事务 H5。前端默认使用本目录内的固定模拟数据；切换真实后端时只需调整环境变量，不需要改写页面。

## 启动

```powershell
npm install
Copy-Item .env.example .env
npm run dev
```

默认配置：

```text
VITE_USE_MOCKS=true
VITE_API_BASE_URL=http://127.0.0.1:8000
```

需要连接 Agent 3 的 FastAPI 时，将 `VITE_USE_MOCKS` 改为 `false`。浏览器只调用 Shared Contract 中的 `/api/v1/*` 接口；模型供应商密钥必须留在后端，禁止写入任何 `VITE_*` 变量。

## 验收

```powershell
npm test
npm run build
npm run dev -- --port 4173
npm run qa:browser
```

`qa:browser` 复用本机 Edge，验证 375×812、1366×768、1440×900 的四个主要页面、长文本与移动导航，并走通“解析通知 → 人工确认 → 创建任务 → Chat”流程。截图写入已忽略的 `.qa-artifacts/`。

## 结构

- `src/api/client.ts`：唯一 API 入口，包含 Mock/Real 两种实现。
- `src/mocks/`：遵循 Shared Contract 的 Notice、Course、Task、Reminder 固定演示数据与错误场景。
- `src/pages/`：今日简报、通知解析、课表与待办、Chat。
- 顶栏“演示场景”可切换正常、空、局部缺失、长文本、错误、离线和超时。
