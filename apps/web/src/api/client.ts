import todayBriefJson from '../mocks/today-brief.json'
import noticeResultJson from '../mocks/notice-result.json'
import coursesJson from '../mocks/courses.json'
import tasksJson from '../mocks/tasks.json'
import remindersJson from '../mocks/reminders.json'
import errorsJson from '../mocks/errors.json'
import type {
  ApiErrorBody,
  ApiResponse,
  ChatEvent,
  Course,
  CreateTaskResult,
  DemoScenario,
  Notice,
  Reminder,
  Task,
  TaskStatus,
  TodayBrief,
} from '../types'

const STUDENT_ID = 'student-demo-001'

export class ApiError extends Error {
  code: string
  details: Record<string, unknown>

  constructor(error: ApiErrorBody) {
    super(error.message)
    this.name = 'ApiError'
    this.code = error.code
    this.details = error.details
  }
}

export interface CampusMindApi {
  readonly mode: 'mock' | 'real'
  setScenario?(scenario: DemoScenario): void
  reset?(): void
  getTodayBrief(studentId?: string): Promise<TodayBrief>
  parseNotice(text: string, studentId?: string): Promise<Notice>
  createTaskFromNotice(notice: Notice, studentId?: string): Promise<CreateTaskResult>
  getTodayCourses(studentId?: string): Promise<Course[]>
  listTasks(studentId?: string): Promise<Task[]>
  listDueReminders(studentId?: string): Promise<Reminder[]>
  updateTask(taskId: string, status: TaskStatus): Promise<Task>
  streamChat(message: string, studentId?: string, signal?: AbortSignal): AsyncGenerator<ChatEvent>
}

function clone<T>(value: T): T {
  return structuredClone(value)
}

function wait(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = window.setTimeout(resolve, ms)
    signal?.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timer)
        reject(new DOMException('请求已取消', 'AbortError'))
      },
      { once: true },
    )
  })
}

function scenarioError(scenario: DemoScenario): ApiError | null {
  if (scenario === 'error') return new ApiError(errorsJson.error)
  if (scenario === 'offline') return new ApiError(errorsJson.offline)
  if (scenario === 'timeout') return new ApiError(errorsJson.timeout)
  return null
}

export class MockCampusMindApi implements CampusMindApi {
  readonly mode = 'mock' as const
  private scenario: DemoScenario = 'normal'
  private tasks: Task[] = clone(tasksJson) as Task[]
  private reminders: Reminder[] = clone(remindersJson) as Reminder[]

  setScenario(scenario: DemoScenario) {
    this.scenario = scenario
  }

  reset() {
    this.scenario = 'normal'
    this.tasks = clone(tasksJson) as Task[]
    this.reminders = clone(remindersJson) as Reminder[]
  }

  private async beforeResponse(signal?: AbortSignal) {
    await wait(this.scenario === 'timeout' ? 260 : 32, signal)
    const error = scenarioError(this.scenario)
    if (error) throw error
  }

  async getTodayBrief(): Promise<TodayBrief> {
    await this.beforeResponse()
    const brief = clone(todayBriefJson) as TodayBrief
    brief.tasks = clone(this.tasks)

    if (this.scenario === 'empty') {
      return { ...brief, courses: [], tasks: [], notices: [], conflicts: [], suggestions: [] }
    }
    if (this.scenario === 'partial') {
      return { ...brief, notices: [], suggestions: [], conflicts: ['通知服务暂未返回，课程与待办仍可使用'] }
    }
    if (this.scenario === 'long') {
      const repeated = '请逐项核对个人信息、资格条件、附件命名和提交状态，并保留提交回执。'.repeat(12)
      brief.notices[0] = { ...brief.notices[0], title: `跨学院综合实践项目材料提交与资格复核特别说明（模拟长标题）${repeated.slice(0, 38)}`, raw_text: repeated }
      brief.tasks[0] = { ...brief.tasks[0], title: `核对并提交跨学院综合实践项目全部材料（模拟长标题）${repeated.slice(0, 30)}` }
    }
    return brief
  }

  async parseNotice(text: string): Promise<Notice> {
    await this.beforeResponse()
    if (!text.trim()) {
      throw new ApiError({ code: 'NOTICE_EMPTY', message: '请先粘贴通知正文', details: {} })
    }
    const parsed = clone(noticeResultJson) as Notice
    parsed.raw_text = text.trim()
    if (text.includes('明天') || text.includes('下周')) {
      parsed.deadline = null
      parsed.confidence = 0.61
      parsed.needs_confirmation = true
    }
    return parsed
  }

  async createTaskFromNotice(notice: Notice, studentId = STUDENT_ID): Promise<CreateTaskResult> {
    await this.beforeResponse()
    const dedupeKey = `${studentId}:${notice.id}:registration`
    const duplicate = this.tasks.find((task) => task.dedupe_key === dedupeKey)
    if (duplicate) return { task: clone(duplicate), created: false, duplicate_of: duplicate.id }

    const task: Task = {
      id: `task-${notice.id}`,
      student_id: studentId,
      title: notice.actions[0] ?? notice.title,
      description: `来自通知 ${notice.id}`,
      task_type: 'registration',
      priority: notice.priority,
      status: 'pending',
      due_at: notice.deadline,
      source_notice_id: notice.id,
      dedupe_key: dedupeKey,
      created_at: '2026-08-21T09:30:00+08:00',
      completed_at: null,
    }
    this.tasks = [task, ...this.tasks]
    if (notice.deadline) {
      this.reminders = [{
        id: `reminder-${task.id}`,
        task_id: task.id,
        trigger_at: '2026-08-22T15:00:00+08:00',
        channel: 'in_app',
        status: 'pending',
        sent_at: null,
        failure_reason: null,
      }, ...this.reminders]
    }
    return { task: clone(task), created: true, duplicate_of: null }
  }

  async getTodayCourses(): Promise<Course[]> {
    await this.beforeResponse()
    if (this.scenario === 'empty') return []
    if (this.scenario === 'partial') return [clone(coursesJson[0]) as Course]
    return clone(coursesJson) as Course[]
  }

  async listTasks(): Promise<Task[]> {
    await this.beforeResponse()
    if (this.scenario === 'empty') return []
    return clone(this.tasks)
  }

  async listDueReminders(): Promise<Reminder[]> {
    await this.beforeResponse()
    if (this.scenario === 'empty') return []
    return clone(this.reminders)
  }

  async updateTask(taskId: string, status: TaskStatus): Promise<Task> {
    await this.beforeResponse()
    const index = this.tasks.findIndex((task) => task.id === taskId)
    if (index === -1) {
      throw new ApiError({ code: 'TASK_NOT_FOUND', message: '任务不存在或已被删除', details: { task_id: taskId } })
    }
    const updated: Task = {
      ...this.tasks[index],
      status,
      completed_at: status === 'completed' ? '2026-08-21T10:02:00+08:00' : null,
    }
    this.tasks[index] = updated
    if (status === 'completed' || status === 'cancelled') {
      this.reminders = this.reminders.map((reminder) => reminder.task_id === taskId && reminder.status === 'pending' ? { ...reminder, status: 'skipped' } : reminder)
    }
    if (status === 'pending') {
      this.reminders = this.reminders.map((reminder) => reminder.task_id === taskId && reminder.status === 'skipped' ? { ...reminder, status: 'pending' } : reminder)
    }
    return clone(updated)
  }

  async *streamChat(message: string, _studentId = STUDENT_ID, signal?: AbortSignal): AsyncGenerator<ChatEvent> {
    await wait(24, signal)
    if (this.scenario === 'offline') throw new ApiError(errorsJson.offline)
    if (this.scenario === 'timeout') throw new ApiError(errorsJson.timeout)

    yield { type: 'tool_running', tool: 'get_today_brief' }
    await wait(38, signal)
    if (this.scenario === 'error') {
      yield { type: 'tool_failure', tool: 'get_today_brief', content: errorsJson.tool.message }
      throw new ApiError(errorsJson.tool)
    }
    yield { type: 'tool_success', tool: 'get_today_brief' }

    const answer = message.includes('奖学金')
      ? '奖学金材料需要在今天 18:00 前提交。建议先核对资格与附件命名，再保留提交回执。'
      : '你下一节是 10:00 的人工智能导论，地点在模拟教学楼 A101。今天最高优先级是 18:00 前提交奖学金材料。'
    for (const fragment of answer.match(/.{1,9}/gu) ?? []) {
      await wait(18, signal)
      yield { type: 'delta', content: fragment }
    }
    yield {
      type: 'sources',
      sources: [
        {
          source_id: 'source-demo-brief-001',
          title: '模拟教务处 · 今日事务数据',
          valid_at: '2026-08-21',
          path: 'demo://knowledge/today-brief',
          simulated: true,
        },
      ],
    }
    yield { type: 'done' }
  }
}

class RealCampusMindApi implements CampusMindApi {
  readonly mode = 'real' as const

  constructor(private readonly baseUrl: string) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    })
    const envelope = (await response.json()) as ApiResponse<T>
    if (!response.ok || !envelope.ok || !envelope.data) {
      throw new ApiError(envelope.error ?? { code: 'INTERNAL_ERROR', message: '服务返回了无效响应', details: {} })
    }
    return envelope.data
  }

  getTodayBrief(studentId = STUDENT_ID) {
    return this.request<TodayBrief>(`/api/v1/brief/today?student_id=${encodeURIComponent(studentId)}`)
  }

  parseNotice(text: string, studentId = STUDENT_ID) {
    return this.request<Notice>('/api/v1/notices/parse', {
      method: 'POST',
      body: JSON.stringify({ text, student_id: studentId, reference_time: new Date().toISOString() }),
    })
  }

  createTaskFromNotice(notice: Notice, studentId = STUDENT_ID) {
    return this.request<CreateTaskResult>('/api/v1/tasks', {
      method: 'POST',
      body: JSON.stringify({
        student_id: studentId,
        title: notice.actions[0] ?? notice.title,
        description: `来自通知 ${notice.id}`,
        task_type: 'registration',
        priority: notice.priority,
        due_at: notice.deadline,
        source_notice_id: notice.id,
        dedupe_key: `${studentId}:${notice.id}:registration`,
      }),
    })
  }

  getTodayCourses(studentId = STUDENT_ID) {
    return this.request<Course[]>(`/api/v1/courses/today?student_id=${encodeURIComponent(studentId)}`)
  }

  listTasks(studentId = STUDENT_ID) {
    return this.request<Task[]>(`/api/v1/tasks?student_id=${encodeURIComponent(studentId)}`)
  }

  listDueReminders(studentId = STUDENT_ID) {
    return this.request<Reminder[]>(`/api/v1/reminders/due?student_id=${encodeURIComponent(studentId)}`)
  }

  updateTask(taskId: string, status: TaskStatus) {
    return this.request<Task>(`/api/v1/tasks/${encodeURIComponent(taskId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
  }

  async *streamChat(message: string, studentId = STUDENT_ID, signal?: AbortSignal): AsyncGenerator<ChatEvent> {
    yield { type: 'tool_running', tool: 'campus_agent' }
    const response = await fetch(`${this.baseUrl}/api/v1/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, student_id: studentId }),
      signal,
    })
    if (!response.ok || !response.body) {
      throw new ApiError({ code: 'MODEL_UNAVAILABLE', message: 'Agent 暂时不可用', details: { status: response.status } })
    }
    yield { type: 'tool_success', tool: 'campus_agent' }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const content = decoder.decode(value, { stream: true })
      if (content) yield { type: 'delta', content }
    }
    yield { type: 'done' }
  }
}

export function createApiClient(): CampusMindApi {
  if (import.meta.env.VITE_USE_MOCKS === 'false') {
    return new RealCampusMindApi(import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000')
  }
  return new MockCampusMindApi()
}

export const apiClient = createApiClient()
