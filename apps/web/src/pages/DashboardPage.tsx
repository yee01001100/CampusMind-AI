import { useEffect, useMemo, useState } from 'react'
import { apiClient } from '../api/client'
import { Icon } from '../components/Icon'
import { EmptyView, ErrorView, LoadingView, PriorityBadge } from '../components/StateView'
import type { TodayBrief } from '../types'
import type { ViewName } from '../App'
import { errorCopy, formatDateTime, formatDay } from '../utils'

export function DashboardPage({ onNavigate }: { onNavigate: (view: ViewName) => void }) {
  const [brief, setBrief] = useState<TodayBrief | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    apiClient.getTodayBrief()
      .then((data) => active && setBrief(data))
      .catch((reason) => active && setError(errorCopy(reason)))
      .finally(() => active && setLoading(false))
    return () => { active = false }
  }, [attempt])

  const pendingTasks = useMemo(() => brief?.tasks.filter((task) => task.status === 'pending') ?? [], [brief])
  const completeCount = brief?.tasks.filter((task) => task.status === 'completed').length ?? 0
  const nextCourse = brief?.courses[0]
  const urgentTask = pendingTasks.find((task) => task.priority === 'critical' || task.priority === 'high') ?? pendingTasks[0]
  const latestNotice = brief?.notices[0]
  const isEmpty = brief && !brief.courses.length && !brief.tasks.length && !brief.notices.length

  if (loading) {
    return <section className="page-section"><div className="page-intro"><div><span className="date-line">正在同步今日安排</span><h2>早上好，同学</h2></div></div><LoadingView rows={6} /></section>
  }
  if (error) return <section className="page-section"><ErrorView detail={error} retry={() => setAttempt((value) => value + 1)} /></section>
  if (!brief || isEmpty) {
    return (
      <section className="page-section">
        <div className="page-intro"><div><span className="date-line">今天</span><h2>今天暂时没有安排</h2></div></div>
        <EmptyView title="清爽的一天" detail="没有课程、待办或新通知。你可以先解析一条校园通知，CampusMind 会帮你提取行动事项。" action={<button className="button primary" onClick={() => onNavigate('notice')}><Icon name="notice" />解析通知</button>} />
      </section>
    )
  }

  return (
    <section className="page-section dashboard-page">
      <div className="page-intro">
        <div>
          <span className="date-line">{formatDay(brief.date)}</span>
          <h2>早上好，同学</h2>
          <p>今天有 <strong>{brief.courses.length} 节课</strong>、<strong>{pendingTasks.length} 项待办</strong>，先处理离截止最近的事情。</p>
        </div>
        <button className="button secondary compact" onClick={() => onNavigate('chat')}><Icon name="spark" />问问 Agent</button>
      </div>

      {!latestNotice && (
        <div className="inline-alert info" role="status"><Icon name="alert" /><div><b>部分数据尚未返回</b><span>通知与建议暂时缺失，课程和待办仍可正常查看。</span></div></div>
      )}

      <div className="brief-grid">
        <article className="next-course-panel">
          <div className="panel-heading">
            <span className="panel-icon teal"><Icon name="book" /></span>
            <div><span>下一节课</span><h3>{nextCourse?.name ?? '今天没有后续课程'}</h3></div>
          </div>
          {nextCourse ? (
            <>
              <div className="course-time"><strong>{nextCourse.start_time}</strong><span>{nextCourse.end_time} 结束</span></div>
              <dl className="detail-list">
                <div><dt><Icon name="map" />地点</dt><dd>{nextCourse.location ?? '地点待确认'}</dd></div>
                <div><dt><Icon name="source" />教师</dt><dd>{nextCourse.teacher ?? '教师待确认'}</dd></div>
              </dl>
              <button className="text-action" onClick={() => onNavigate('planner')}>查看今日课表 <Icon name="arrow" /></button>
            </>
          ) : <p className="muted">今天的课程已经结束，可以安排自己的时间。</p>}
        </article>

        <article className="progress-panel">
          <div className="panel-heading">
            <span className="panel-icon blue"><Icon name="check" /></span>
            <div><span>今日完成</span><h3>{completeCount} / {brief.tasks.length} 项</h3></div>
          </div>
          <div className="progress-track" aria-label={`已完成 ${completeCount} 项，共 ${brief.tasks.length} 项`}><span style={{ width: `${brief.tasks.length ? Math.round(completeCount / brief.tasks.length * 100) : 0}%` }} /></div>
          <p className="muted">{pendingTasks.length ? `还有 ${pendingTasks.length} 项待办，完成后提醒会自动停止。` : '今天的待办已经全部完成。'}</p>
          <button className="text-action" onClick={() => onNavigate('planner')}>管理全部待办 <Icon name="arrow" /></button>
        </article>

        <article className="urgent-panel">
          <div className="panel-kicker"><span>最高优先级</span>{urgentTask && <PriorityBadge priority={urgentTask.priority} />}</div>
          {urgentTask ? (
            <><h3>{urgentTask.title}</h3><p>{urgentTask.description ?? '暂无补充说明'}</p><div className="deadline"><Icon name="clock" /><span>截止 {formatDateTime(urgentTask.due_at)}</span></div></>
          ) : <><h3>没有未完成任务</h3><p>今天的事项已经处理完毕。</p></>}
        </article>
      </div>

      <div className="dashboard-columns">
        <section className="content-section" aria-labelledby="latest-notice-title">
          <div className="section-heading"><div><span>校园信息</span><h3 id="latest-notice-title">最新通知</h3></div><button className="text-action" onClick={() => onNavigate('notice')}>解析新通知 <Icon name="arrow" /></button></div>
          {latestNotice ? (
            <article className="notice-row">
              <div className="notice-date"><strong>{formatDateTime(latestNotice.published_at, { month: '2-digit', day: '2-digit' })}</strong><span>发布</span></div>
              <div className="notice-copy"><div><PriorityBadge priority={latestNotice.priority} /><span className="confidence">置信度 {Math.round(latestNotice.confidence * 100)}%</span></div><h4>{latestNotice.title}</h4><p>{latestNotice.raw_text}</p></div>
            </article>
          ) : <EmptyView title="通知暂未同步" detail="课程和待办仍可使用，稍后可重试通知服务。" />}
        </section>

        <aside className="insight-section" aria-label="冲突与 Agent 建议">
          <div className="insight-block warning">
            <div className="insight-title"><Icon name="alert" /><h3>时间冲突</h3></div>
            {brief.conflicts.length ? <ul>{brief.conflicts.map((item) => <li key={item}>{item}</li>)}</ul> : <p>今天没有检测到时间冲突。</p>}
          </div>
          <div className="insight-block suggestion">
            <div className="insight-title"><Icon name="spark" /><h3>Agent 建议</h3></div>
            {brief.suggestions.length ? <ol>{brief.suggestions.map((item) => <li key={item}>{item}</li>)}</ol> : <p>建议暂未返回，你仍可按待办截止时间处理。</p>}
          </div>
        </aside>
      </div>
    </section>
  )
}
