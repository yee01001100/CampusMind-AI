import { describe, expect, it } from 'vitest'
import { ApiError, MockCampusMindApi } from './client'

describe('MockCampusMindApi contract', () => {
  it('returns Shared Contract shaped brief data with timezone-aware dates', async () => {
    const api = new MockCampusMindApi()
    const brief = await api.getTodayBrief()
    expect(brief.date).toBe('2026-08-21')
    expect(brief.courses[0]).toMatchObject({ student_id: 'student-demo-001', weekday: 5, week_pattern: 'all' })
    expect(brief.tasks[0].due_at).toMatch(/[+-]\d{2}:\d{2}$/)
    expect(brief.notices[0]).toMatchObject({ source_type: 'demo', confidence: 0.94, needs_confirmation: false })
  })

  it('covers empty and partial brief scenarios', async () => {
    const api = new MockCampusMindApi()
    api.setScenario('empty')
    expect(await api.getTodayBrief()).toMatchObject({ courses: [], tasks: [], notices: [] })
    api.setScenario('partial')
    const partial = await api.getTodayBrief()
    expect(partial.courses).toHaveLength(2)
    expect(partial.notices).toHaveLength(0)
    expect(partial.conflicts[0]).toContain('暂未返回')
  })

  it('marks relative notification dates for confirmation', async () => {
    const api = new MockCampusMindApi()
    const notice = await api.parseNotice('【模拟数据】请在明天完成报名。')
    expect(notice.deadline).toBeNull()
    expect(notice.needs_confirmation).toBe(true)
    expect(notice.confidence).toBeLessThan(0.75)
  })

  it('rejects an empty notice with a stable error code', async () => {
    const api = new MockCampusMindApi()
    await expect(api.parseNotice(' ')).rejects.toMatchObject({ code: 'NOTICE_EMPTY' })
  })

  it('deduplicates task creation and supports complete/restore', async () => {
    const api = new MockCampusMindApi()
    const notice = await api.parseNotice('【模拟数据】2026 级本科生请在 8 月 22 日 18:00 前报名。')
    const first = await api.createTaskFromNotice(notice)
    const second = await api.createTaskFromNotice(notice)
    expect(first.created).toBe(true)
    expect(second).toMatchObject({ created: false, duplicate_of: first.task.id })
    expect((await api.listDueReminders()).find((reminder) => reminder.task_id === first.task.id)).toMatchObject({ channel: 'in_app', status: 'pending' })

    const complete = await api.updateTask(first.task.id, 'completed')
    expect(complete.completed_at).toMatch(/[+-]\d{2}:\d{2}$/)
    expect((await api.listDueReminders()).find((reminder) => reminder.task_id === first.task.id)?.status).toBe('skipped')
    const restored = await api.updateTask(first.task.id, 'pending')
    expect(restored).toMatchObject({ status: 'pending', completed_at: null })
    expect((await api.listDueReminders()).find((reminder) => reminder.task_id === first.task.id)?.status).toBe('pending')
  })

  it.each(['error', 'offline', 'timeout'] as const)('surfaces the %s scenario as an error', async (scenario) => {
    const api = new MockCampusMindApi()
    api.setScenario(scenario)
    await expect(api.getTodayBrief()).rejects.toBeInstanceOf(ApiError)
  })
})
