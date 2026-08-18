# CampusMind HANDOFF Template

> 返回 [README](../README.md) · 查看 [Shared Contract](../contracts/SHARED_CONTRACT.md) · 查看 [最终验收](FINAL_ACCEPTANCE.md)

每个子 Agent 完成后，在仓库根目录创建自己的文件：

```text
HANDOFF-agent1.md
HANDOFF-agent2.md
HANDOFF-agent3.md
HANDOFF-agent4.md
```

复制下面模板并填写真实内容。不得删除必填章节，不得把计划写成已经完成的结果。

---

```markdown
# HANDOFF — Agent N

## Identity

- Role: Agent N / 角色名称
- Team member: <组员姓名或代号>
- AI partner: <AI 任务/会话标识>
- Branch: agent/N-...
- Base commit: <SHA>
- Final commit: <SHA>
- Finished at: <带时区时间>

## Goal Result

用 3–6 句话说明目标是否完整完成。未完成时明确列出原因，不使用“基本完成”掩盖缺口。

## Created Files

- `path/to/file`

## Modified Files

- `path/to/file`

## Public Interfaces

列出其他模块需要调用的类、函数、API、Tool、命令或数据文件。

### Interface 1

- Name:
- Import / URL:
- Input:
- Output:
- Error:
- Example:

## Contract Compliance

- [ ] 使用 Shared Contract 公共字段
- [ ] 未创建第二套同义字段
- [ ] 未修改 Must NOT modify 目录
- [ ] 分支从 `day0-baseline` 创建
- [ ] 时区与时间格式正确
- [ ] 未提交真实个人数据或密钥

如有偏差，逐项说明。

## Commands

### Install

```powershell
<真实命令>
```

### Run

```powershell
<真实命令>
```

### Test

```powershell
<真实命令>
```

## Test Results

- Command:
- Exit code:
- Passed:
- Failed:
- Skipped:
- Important output:

不要只写“测试通过”，必须写真实命令和结果数字。

## Stub / Mock

| Path | Simulates | Must be replaced by | Replacement step |
| --- | --- | --- | --- |
| | | | |

没有 Stub/Mock 时写“无”。

## Environment Variables

| Name | Required | Secret | Purpose | Example without secret |
| --- | --- | --- | --- | --- |
| | | | | |

不得在 HANDOFF 写真实密钥。

## Known Limitations

1.

没有已知限制时写“当前验收范围内无”。

## Integration Steps for Agent 0

1. 合并哪个分支。
2. 安装哪些依赖。
3. 替换哪些 Stub/Mock。
4. 配置哪些环境变量。
5. 运行哪些测试。
6. 验证哪个场景。

## Behaviors That Must Not Break

-

## Remaining Blockers

- Blocker:
- Owner:
- Required action:

没有阻塞时写“无”。

## Final Statement

明确选择一个：

- COMPLETE — 全部验收通过，可以交给 Agent 0。
- INCOMPLETE — 未达到停止条件，不能进入最终集成。
```

---

## HANDOFF 审核规则

Agent 0 开始合并前检查：

- 分支和 SHA 真实存在。
- 修改文件没有越界。
- 测试命令可以运行。
- Stub/Mock 有明确替换方式。
- `COMPLETE` 与测试结果一致。
- 没有真实密钥、Cookie、Token 或个人数据。

HANDOFF 是施工摘要，不替代代码和测试；代码保存现实，HANDOFF 保存集成所需上下文。
