import { useMemo, useState } from 'react'
import { apiClient } from '../api/client'
import { Icon } from '../components/Icon'
import { ErrorView, LoadingView, PriorityBadge } from '../components/StateView'
import type { CreateTaskResult, Notice, Priority } from '../types'
import { errorCopy, formatDateTime } from '../utils'

const defaultNotice = '【模拟数据】2026 级本科生请在 8 月 22 日 18:00 前完成四六级报名。报名对象以教务系统资格名单为准，如时间有调整请以学院后续通知为准。'

export function NoticePage() {
  const [text, setText] = useState(defaultNotice)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const [taskResult, setTaskResult] = useState<CreateTaskResult | null>(null)

  const needsConfirmation = useMemo(() => notice?.needs_confirmation || !notice?.deadline, [notice])

  const parseNotice = async () => {
    setLoading(true)
    setError(null)
    setTaskResult(null)
    setConfirmed(false)
    try {
      setNotice(await apiClient.parseNotice(text))
    } catch (reason) {
      setNotice(null)
      setError(errorCopy(reason))
    } finally {
      setLoading(false)
    }
  }

  const createTask = async () => {
    if (!notice || submitting || (needsConfirmation && !confirmed)) return
    setSubmitting(true)
    setError(null)
    try {
      setTaskResult(await apiClient.createTaskFromNotice(notice))
    } catch (reason) {
      setError(errorCopy(reason))
    } finally {
      setSubmitting(false)
    }
  }

  const update = <K extends keyof Notice>(key: K, value: Notice[K]) => {
    setNotice((current) => current ? { ...current, [key]: value } : current)
    setTaskResult(null)
  }

  return (
    <section className="page-section notice-page">
      <div className="page-intro compact-intro">
        <div><span className="date-line">通知 → 行动</span><h2>把通知变成清楚的待办</h2><p>粘贴原文后先核对提取结果；有歧义的时间必须由你确认。</p></div>
      </div>

      <div className="notice-workspace">
        <section className="input-panel" aria-labelledby="notice-input-title">
          <div className="section-heading"><div><span>第一步</span><h3 id="notice-input-title">粘贴原通知</h3></div><span className="char-count">{text.length} 字</span></div>
          <label className="sr-only" htmlFor="notice-text">校园通知正文</label>
          <textarea id="notice-text" value={text} onChange={(event) => setText(event.target.value)} placeholder="粘贴通知正文，原文会完整保留……" maxLength={8000} />
          <div className="panel-footer"><p><Icon name="source" />仅处理你主动粘贴的模拟通知，不读取校园账号。</p><button className="button primary" disabled={loading || !text.trim()} onClick={parseNotice}>{loading ? '正在解析…' : <><Icon name="spark" />解析通知</>}</button></div>
        </section>

        <section className="result-panel" aria-labelledby="notice-result-title" aria-live="polite">
          <div className="section-heading"><div><span>第二步</span><h3 id="notice-result-title">核对提取结果</h3></div>{notice && <PriorityBadge priority={notice.priority} />}</div>
          {loading && <LoadingView rows={7} label="正在解析通知" />}
          {!loading && error && !notice && <ErrorView title="解析没有完成" detail={error} retry={parseNotice} icon="alert" />}
          {!loading && !notice && !error && <div className="result-placeholder"><Icon name="notice" /><p>解析结果会出现在这里</p><span>标题、对象、截止时间、行动事项与来源都可以核对。</span></div>}
          {!loading && notice && (
            <div className="notice-form">
              {needsConfirmation && <div className="inline-alert warning" role="status"><Icon name="alert" /><div><b>有字段需要人工确认</b><span>置信度 {Math.round(notice.confidence * 100)}%，请重点核对截止时间与适用对象。</span></div></div>}
              <label>标题<input value={notice.title} onChange={(event) => update('title', event.target.value)} /></label>
              <div className="form-row">
                <label>适用对象<input value={notice.audience.join('、')} onChange={(event) => update('audience', event.target.value.split(/[、,，]/).map((item) => item.trim()).filter(Boolean))} /></label>
                <label>优先级<select value={notice.priority} onChange={(event) => update('priority', event.target.value as Priority)}><option value="critical">紧急</option><option value="high">高</option><option value="medium">中</option><option value="normal">普通</option></select></label>
              </div>
              <label>截止时间<input type="datetime-local" value={notice.deadline?.slice(0, 16) ?? ''} onChange={(event) => update('deadline', event.target.value ? `${event.target.value}:00+08:00` : null)} /></label>
              <label>行动事项<textarea className="compact-textarea" value={notice.actions.join('\n')} onChange={(event) => update('actions', event.target.value.split('\n').filter(Boolean))} /></label>
              <details><summary>查看保留的原通知</summary><p className="raw-notice">{notice.raw_text}</p></details>
              <dl className="notice-meta"><div><dt>置信度</dt><dd>{Math.round(notice.confidence * 100)}%</dd></div><div><dt>来源</dt><dd>{notice.source_type === 'user_input' ? '用户粘贴' : notice.source_type}</dd></div><div><dt>解析时间</dt><dd>{formatDateTime(notice.created_at)}</dd></div></dl>
              {needsConfirmation && <label className="confirm-check"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} /><span>我已核对适用对象和截止时间</span></label>}
              <button className="button primary full" disabled={submitting || !notice.actions.length || (needsConfirmation && !confirmed)} onClick={createTask}>{submitting ? '正在创建…' : <><Icon name="check" />确认并创建任务</>}</button>
              {error && <div className="inline-alert error" role="alert"><Icon name="alert" /><div><b>创建失败</b><span>{error}</span></div></div>}
              {taskResult && (
                <div className={`creation-result ${taskResult.created ? 'success' : 'duplicate'}`} role="status">
                  <Icon name={taskResult.created ? 'check' : 'alert'} />
                  <div><b>{taskResult.created ? '任务创建成功' : '任务已存在，未重复创建'}</b><span>{taskResult.task.title} · {formatDateTime(taskResult.task.due_at)}</span></div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </section>
  )
}
