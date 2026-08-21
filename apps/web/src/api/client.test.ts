import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, MockCampusMindApi, RealCampusMindApi } from './client'
import coursesJson from '../mocks/courses.json'
import noticeResultJson from '../mocks/notice-result.json'

afterEach(() => vi.unstubAllGlobals())

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

describe('RealCampusMindApi integration envelopes', () => {
  const envelope = (data: unknown) => new Response(JSON.stringify({
    ok: true,
    data,
    error: null,
    request_id: 'req-web-test',
  }), { status: 200, headers: { 'Content-Type': 'application/json' } })

  it('unwraps the integrated notice and course payloads', async () => {
    const notice = { ...noticeResultJson, raw_text: '测试通知' }
    const course = coursesJson[0]
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(envelope({ notice, tasks: [], reminders: [], duplicate: false }))
      .mockResolvedValueOnce(envelope({ date: '2026-08-21', week: 1, courses: [course], next_course: course, free_slots: [] }))
    vi.stubGlobal('fetch', fetchMock)

    const api = new RealCampusMindApi('http://127.0.0.1:8000')
    expect((await api.parseNotice('测试通知')).raw_text).toBe('测试通知')
    expect(await api.getTodayCourses()).toEqual([course])
  })

  it('turns the integrated chat envelope into UI events and sources', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(envelope({
      message: '已找到有来源的校园资料。',
      result: {
        sources: [{
          source_id: 'knowledge-demo-001',
          title: '模拟校园资料',
          effective_date: '2026-08-21',
          source_ref: 'demo://knowledge/001',
          is_demo: true,
        }],
      },
      traces: [{ name: 'rag_search', status: 'success' }],
      runtime_mode: 'local-rules',
    })))

    const events = []
    for await (const event of new RealCampusMindApi('http://127.0.0.1:8000').streamChat('奖学金规定')) {
      events.push(event)
    }
    expect(events.map((event) => event.type)).toEqual([
      'tool_running', 'tool_success', 'delta', 'sources', 'done',
    ])
    expect(events.find((event) => event.type === 'sources')?.sources?.[0]).toMatchObject({
      source_id: 'knowledge-demo-001',
      simulated: true,
    })
  })
})
