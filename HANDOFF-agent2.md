# HANDOFF — Agent 2

## Identity

- Role: Agent 2 / Data、SQLite、RAG
- Team member: CampusMind 组员（用户委托全自动施工）
- AI partner: `/root/agent2_data_rag`
- Branch: `agent/2-data-rag`
- Base commit: `089bb8314cf34ed385dc158df288ca321d5bbfea`
- Final implementation commit: `e6396249bed82c46b65e1d03191f2413bf97d970`
- Handoff commit: 本文档所在的分支 HEAD；集成时应合并整个 `agent/2-data-rag`
- Finished at: `2026-08-21T19:59:07+08:00`

## Goal Result

Agent 2 的独立验收范围已完整实现。五个 Shared Contract 模型由 Pydantic 严格校验并保持原字段；SQLite schema 开启外键，提供五类 Repository、任务去重、状态切换、日期查询和提醒时间查询。模拟数据可幂等初始化，满足 1 名学生、8 门课程、8 条任务、5 条通知、5 条提醒和 2 组冲突。10 份模拟知识资料可重复导入，检索结果总是携带来源与有效期；无可靠来源时抛出 `RAG_NO_SOURCE`，不会补写学校规定。

## Created Files

- `campusmind/domain/__init__.py`
- `campusmind/domain/models.py`
- `campusmind/storage/__init__.py`
- `campusmind/storage/__main__.py`
- `campusmind/storage/database.py`
- `campusmind/storage/demo.py`
- `campusmind/repositories/__init__.py`
- `campusmind/repositories/sqlite.py`
- `campusmind/repositories/rag.py`
- `data/demo/manifest.json`
- `data/demo/student_profiles.json`
- `data/demo/courses.json`
- `data/demo/notices.json`
- `data/demo/tasks.json`
- `data/demo/reminders.json`
- `data/demo/conflicts.json`
- `data/knowledge/*.json`（10 份独立模拟资料）
- `tests/storage/test_models.py`
- `tests/storage/test_database_and_repositories.py`
- `tests/rag/test_rag.py`
- `HANDOFF-agent2.md`

## Modified Files

- `requirements/agent-2.txt`

## Public Interfaces

### Shared Contract Models

- Name: `Notice`、`Course`、`Task`、`StudentProfile`、`Reminder` 及对应枚举
- Import: `from campusmind.domain import Notice, Course, Task, StudentProfile, Reminder`
- Input: Shared Contract 中冻结的同名字段；禁止 extra 字段
- Output: `model_dump(mode="json")` 返回与契约一致的 JSON 字段
- Error: 无效枚举、无时区 datetime、非法周次/时间、状态与完成时间不一致时抛出 Pydantic `ValidationError`
- Example: `Task.model_validate(payload)`

### SQLite Database

- Name: `SQLiteDatabase`
- Import: `from campusmind.storage import SQLiteDatabase`
- Input: SQLite 路径；调用 `initialize()` 可重复建表
- Output: `connect()` 提供 `sqlite3.Row` 连接，并在每次连接开启 `PRAGMA foreign_keys=ON`
- Error: 外键、唯一键和 CHECK 约束违反时抛出 `sqlite3.IntegrityError`
- Example: `database = SQLiteDatabase("data/local/campusmind.sqlite3"); database.initialize()`

### Repositories

- Name: `StudentProfileRepository`
- Import: `from campusmind.repositories import StudentProfileRepository`
- Methods: `save(profile)`、`get(student_id)`、`list_all()`
- Output: `StudentProfile` 或 `None`

- Name: `NoticeRepository`
- Import: `from campusmind.repositories import NoticeRepository`
- Methods: `create(notice)` / `save(notice)`、`get(id)`、`list_for_date(day, tzinfo=...)`、`list_all()`
- Output: `create` 返回 `(stored_notice, created: bool)`；相同通知 ID 不覆盖原文与来源

- Name: `CourseRepository`
- Import: `from campusmind.repositories import CourseRepository`
- Methods: `save(course)`、`get(id)`、`list_for_student(student_id)`、`list_for_student_on_date(student_id, day, term_start=...)`
- Output: `Course` 或 `Course[]`；日期查询处理 all/odd/even/custom 周规则
- Error: `term_start` 不是第 1 周周一时抛出 `ValueError`

- Name: `TaskRepository`
- Import: `from campusmind.repositories import TaskRepository`
- Methods: `create(task)`、`get(id, student_id=...)`、`get_by_dedupe_key(key)`、`list_for_student(...)`、`list_for_student_on_date(...)`、`complete(...)`、`restore(...)`、`set_status(...)`
- Output: `create` 返回 `(stored_task, created: bool)`；重复 `dedupe_key` 返回原任务且 `created=False`
- Error: `complete` 的时间必须带时区；完成状态必须通过 `complete()` 写入完成时间

- Name: `ReminderRepository`
- Import: `from campusmind.repositories import ReminderRepository`
- Methods: `save(reminder)`、`get(id)`、`list_for_task(task_id)`、`list_in_range(start, end, ...)`、`list_due(at, student_id=...)`
- Output: `Reminder` 或 `Reminder[]`；`list_due` 自动排除已完成/已取消任务

### Demo Initializer

- Name: `load_demo_data` / storage CLI
- Import: `from campusmind.storage import load_demo_data`
- Input: 已初始化或未初始化的 `SQLiteDatabase`、`data/demo` 路径
- Output: `DemoLoadResult`，包含读取数量和实际新建数量
- Error: manifest 未明确设置 `is_demo=true` 时拒绝加载
- Example: `python -m campusmind.storage --database data/local/campusmind-demo.sqlite3`

### Knowledge Import and Retrieval

- Name: `KnowledgeImporter`、`RAGRetriever`、`KnowledgeDocument`、`RAGMatch`
- Import: `from campusmind.repositories import KnowledgeImporter, RAGRetriever`
- Input: `import_directory("data/knowledge")`；`search(query, as_of=date, limit=3, include_expired=False)`
- Output: `RAGMatch[]`，每项包含 `snippet`、`score` 和完整 `source` 元数据（`source_id`、标题、类型、发布时间、生效日、失效日、引用路径、模拟标记、是否过期）
- Error: 空库、空查询、未知问题、无当前可靠来源时抛出 `RAGNoSourceError`，其稳定 `code` 为 `RAG_NO_SOURCE`
- Example: `RAGRetriever(database).search("四六级报名截止时间", as_of=date(2026, 8, 21))`

## Contract Compliance

- [x] 使用 Shared Contract 公共字段
- [x] 未创建第二套同义字段
- [x] 未修改 Must NOT modify 目录
- [x] 分支从统一 Day 0 实现提交 `089bb831...` 创建
- [x] 时区与时间格式正确
- [x] 未提交真实个人数据或密钥

补充：本地 `day0-baseline` 为 annotated tag，其 commit peel 后是 `089bb831...`；Agent 2 分支起点与该实现提交一致。

## Commands

### Install

```powershell
& 'D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe' -m pip install -r requirements\agent-2.txt
```

### Run

```powershell
& 'D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe' -m campusmind.storage --database data\local\campusmind-demo.sqlite3
```

该命令幂等加载模拟业务数据和知识资料。`data/local/` 与 `*.sqlite3` 已被根 `.gitignore` 忽略。

### Test

```powershell
$env:PYTHONUTF8='1'
& 'D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe' -m pytest tests\storage tests\rag -q
& 'D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe' -m pytest tests\contract -q
& 'D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe' scripts\check_contracts.py
& 'D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe' scripts\check_day0.py
& 'D:\codexproject\unbengable\CampusMind-AI\.venv\Scripts\python.exe' -m pip check
```

## Test Results

- Command: `python -m pytest tests/storage tests/rag -q`
- Exit code: `0`
- Passed: `38`
- Failed: `0`
- Skipped: `0`
- Important output: `38 passed in 7.64s`

- Command: `python -m pytest tests/contract -q`
- Exit code: `0`
- Passed: `4`
- Failed: `0`
- Skipped: `0`
- Important output: `4 passed in 0.08s`

- Command: `python scripts/check_contracts.py`
- Exit code: `0`
- Important output: `PASS: 5 model examples and 2 API envelopes match the frozen contract`

- Command: `python scripts/check_day0.py`
- Exit code: `0`
- Important output: `PASS: Day 0 baseline is ready on Python 3.12`

- Command: `python -m pip check`
- Exit code: `0`
- Important output: `No broken requirements found.`

## Stub / Mock

无代码 Stub/Mock。`data/demo/` 和 `data/knowledge/` 是明确标记 `is_demo=true` 的产品演示数据，不冒充生产校园数据；切换生产数据时应调用相同模型、Repository 和知识导入接口。

## Environment Variables

无。Agent 2 不读取 API Key、校园账号、Cookie、Token 或其他密钥。

## Known Limitations

1. RAG 是零外部依赖的本地字符二元组词法检索，不生成答案、不调用 embedding/LLM；Agent 1/3 应基于 `RAGMatch` 的片段和来源组织回答，不能把模型记忆当学校规定。
2. `Course` 公共模型没有学期起始日，因此按日期算单双周时，调用方必须向 `list_for_student_on_date` 显式传入第 1 周周一 `term_start`。
3. `Notice` 公共模型没有 `student_id`，所以 Repository 按日期返回全局通知；Agent 3 应依据 `audience` 和学生档案判断适用性。
4. 默认检索排除过期资料；审计历史规则时必须显式传 `include_expired=True`，返回值会标记 `is_expired=true` 并保留有效期。
5. SQLite 运行库不提交 Git；它由 CLI 或 `load_demo_data` 在本地生成，测试库始终位于 Pytest 临时目录，与演示运行库分离。

## Integration Steps for Agent 0

1. 合并完整分支 `agent/2-data-rag`（不要只拣选 HANDOFF 提交）。
2. 使用 Python 3.12 安装 `requirements/agent-2.txt`；当前唯一第三方运行依赖为 Pydantic 2。
3. 执行 `python -m campusmind.storage --database data/local/campusmind-demo.sqlite3` 初始化演示库和 10 份知识资料。
4. Agent 3 通过 `campusmind.domain` 导入公共模型，通过 `campusmind.repositories` 构建五类 Repository。
5. Service 查询课程时从配置提供学期第 1 周周一；查询通知后根据学生档案和 `audience` 过滤。
6. Chat/RAG 路径捕获 `RAGNoSourceError.code == "RAG_NO_SOURCE"`，仅根据 `RAGMatch.source` 引用来源。
7. 运行本 HANDOFF 中全部测试命令，然后验证：课程单双周、任务重复创建、完成任务停止 due reminder、四六级查询返回来源、未知问题返回 `RAG_NO_SOURCE`。

## Behaviors That Must Not Break

- 所有 datetime 必须带时区，外部序列化字段与 Shared Contract 完全一致。
- SQLite 每次连接必须保持 `foreign_keys=ON`。
- `Task.dedupe_key` 必须唯一，重复创建返回原任务且不新增行。
- 完成任务必须写 `completed_at`；恢复任务必须清空该字段。
- 相同通知 ID 不得覆盖已保存的原文和来源。
- 学生课程、任务和提醒查询不得跨学生泄漏。
- all/odd/even/custom 周课程查询语义不得改变。
- RAG 未命中、过期或尚未生效的来源不得伪装成当前可靠规定。
- 所有演示资料必须继续明确标记 `is_demo=true`。

## Remaining Blockers

无。

## Final Statement

COMPLETE — 全部 Agent 2 验收通过，可以交给 Agent 0。
