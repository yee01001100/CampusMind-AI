import { useEffect, useMemo, useState } from 'react'
import { apiClient } from '../api/client'
import { Icon } from '../components/Icon'
import { EmptyView, ErrorView, LoadingView, PriorityBadge } from '../components/StateView'
import type { Course, Reminder, Task, TaskStatus } from '../types'
import { errorCopy, formatDateTime } from '../utils'

type TaskGroup = { title: string; description: string; tasks: Task[] }

function taskGroups(tasks: Task[]): TaskGroup[] {
  const pending = tasks.filter((task) => task.status === 'pending')
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(new Date())
  const value = (type: Intl.DateTimeFormatPartTypes) => parts.find((part) => part.type === type)?.value ?? ''
  const today = `${value('year')}-${value('month')}-${value('day')}`
  return [
    { title: '今天截止', description: '优先处理', tasks: pending.filter((task) => task.due_at?.startsWith(today)) },
    { title: '接下来', description: '按截止时间', tasks: pending.filter((task) => !task.due_at?.startsWith(today)) },
    { title: '已完成与取消', description: '可以恢复', tasks: tasks.filter((task) => task.status !== 'pending') },
  ].filter((group) => group.tasks.length)
}

export function PlannerPage() {
  const [courses, setCourses] = useState<Course[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [reminders, setReminders] = useState<Reminder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updating, setUpdating] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)
  const groups = useMemo(() => taskGroups(tasks), [tasks])
  const courseConflicts = useMemo(() => {
    const ordered = [...courses].sort((left, right) => left.start_time.localeCompare(right.start_time))
    return ordered.slice(0, -1).flatMap((left, index) => {
      const right = ordered[index + 1]
      return left.end_time > right.start_time
        ? [`${left.name}与${right.name}在 ${right.start_time}–${left.end_time} 重叠`]
        : []
    })
  }, [courses])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    Promise.allSettled([apiClient.getTodayCourses(), apiClient.listTasks(), apiClient.listDueReminders()]).then(([courseResult, taskResult, reminderResult]) => {
      if (!active) return
      if (courseResult.status === 'fulfilled') setCourses(courseResult.value)
      if (taskResult.status === 'fulfilled') setTasks(taskResult.value)
      if (reminderResult.status === 'fulfilled') setReminders(reminderResult.value)
      if (courseResult.status === 'rejected' || taskResult.status === 'rejected' || reminderResult.status === 'rejected') {
        const reason = courseResult.status === 'rejected' ? courseResult.reason : taskResult.status === 'rejected' ? taskResult.reason : reminderResult.status === 'rejected' ? reminderResult.reason : null
        setError(errorCopy(reason))
      }
      setLoading(false)
    })
    return () => { active = false }
  }, [attempt])

  const updateTask = async (task: Task, status: TaskStatus) => {
    setUpdating(task.id)
    setError(null)
    try {
      const updated = await apiClient.updateTask(task.id, status)
      setTasks((current) => current.map((item) => item.id === updated.id ? updated : item))
      setReminders((current) => current.map((reminder) => reminder.task_id === task.id ? { ...reminder, status: status === 'pending' ? 'pending' : 'skipped' } : reminder))
    } catch (reason) {
      setError(errorCopy(reason))
    } finally {
      setUpdating(null)
    }
  }

  if (loading) return <section className="page-section"><div className="page-intro compact-intro"><div><span className="date-line">今天</span><h2>课表与待办</h2></div></div><LoadingView rows={7} /></section>
  if (error && !courses.length && !tasks.length) return <section className="page-section"><ErrorView detail={error} retry={() => setAttempt((value) => value + 1)} /></section>

  return (
    <section className="page-section planner-page">
      <div className="page-intro compact-intro"><div><span className="date-line">今天 · Asia/Shanghai</span><h2>课表与待办</h2><p>课程按时间展开，待办按截止日期与优先级分组。</p></div></div>
      {error && <div className="inline-alert warning" role="alert"><Icon name="alert" /><div><b>部分数据暂不可用</b><span>{error}</span></div><button className="text-action" onClick={() => setAttempt((value) => value + 1)}>重试</button></div>}

      <div className="planner-layout">
        <section className="schedule-panel" aria-labelledby="schedule-title">
          <div className="section-heading"><div><span>今日课程</span><h3 id="schedule-title">时间安排</h3></div><span className="count-badge">{courses.length} 节</span></div>
          {courses.length ? (
            <div className="timeline">
              {courses.map((course, index) => (
                <div className="timeline-item" key={course.id}>
                  <div className="timeline-time"><strong>{course.start_time}</strong><span>{course.end_time}</span></div>
                  <div className="timeline-line"><span />{index < courses.length - 1 && <i />}</div>
                  <article className="course-row">
                    <h4>{course.name}</h4>
                    <p><Icon name="map" />{course.location ?? '地点待确认'}</p>
                    <p><Icon name="source" />{course.teacher ?? '教师待确认'} · 第 {course.start_week}–{course.end_week} 周</p>
                  </article>
                  {index < courses.length - 1 && <div className="free-time">空闲 {Number(courses[index + 1].start_time.slice(0, 2)) * 60 + Number(courses[index + 1].start_time.slice(3)) - Number(course.end_time.slice(0, 2)) * 60 - Number(course.end_time.slice(3))} 分钟</div>}
                </div>
              ))}
              {courseConflicts.length ? (
                <div className="conflict-note"><Icon name="alert" /><span><b>检测到课程冲突</b> · {courseConflicts.join('；')}</span></div>
              ) : (
                <div className="conflict-note clear"><Icon name="check" /><span><b>今天没有课程冲突</b> · 当前课表可以按顺序执行。</span></div>
              )}
            </div>
          ) : <EmptyView title="今天没有课程" detail="可以把空闲时间留给临期待办或休息。" />}
        </section>

        <section className="task-panel" aria-labelledby="tasks-title">
          <div className="section-heading"><div><span>个人待办</span><h3 id="tasks-title">需要完成</h3></div><span className="count-badge">{tasks.filter((task) => task.status === 'pending').length} 项未完成</span></div>
          {!tasks.length ? <EmptyView title="没有待办" detail="从校园通知创建的任务会显示在这里。" /> : (
            <div className="task-groups">
              {groups.map((group) => (
                <section key={group.title} className="task-group" aria-label={group.title}>
                  <div className="task-group-title"><h4>{group.title}</h4><span>{group.description}</span></div>
                  {group.tasks.map((task) => (
                    <article className={`task-row status-${task.status}`} key={task.id}>
                      <button className="task-toggle" aria-label={task.status === 'completed' ? `恢复任务：${task.title}` : `完成任务：${task.title}`} disabled={updating === task.id || task.status === 'cancelled'} onClick={() => updateTask(task, task.status === 'completed' ? 'pending' : 'completed')}><Icon name={task.status === 'completed' ? 'refresh' : 'check'} /></button>
                      <div className="task-copy">
                        <div><PriorityBadge priority={task.priority} />{task.source_notice_id && <span className="source-tag"><Icon name="source" />来自通知</span>}{task.status === 'cancelled' && <span className="cancelled-tag">已取消</span>}</div>
                        <h5>{task.title}</h5>
                        <p>{task.description ?? '暂无补充说明'}</p>
                        <div className="task-meta"><span><Icon name="clock" />截止 {formatDateTime(task.due_at)}</span>{reminders.find((reminder) => reminder.task_id === task.id && reminder.status === 'pending') && <span><Icon name="bell" />提醒 {formatDateTime(reminders.find((reminder) => reminder.task_id === task.id)?.trigger_at ?? null)}</span>}</div>
                      </div>
                      {task.status === 'pending' && <button className="icon-button subtle" aria-label={`取消任务：${task.title}`} disabled={updating === task.id} onClick={() => updateTask(task, 'cancelled')}><Icon name="close" /></button>}
                      {task.status === 'cancelled' && <button className="text-action" disabled={updating === task.id} onClick={() => updateTask(task, 'pending')}>恢复</button>}
                    </article>
                  ))}
                </section>
              ))}
            </div>
          )}
        </section>
      </div>
    </section>
  )
}
