export type Priority = 'critical' | 'high' | 'medium' | 'normal'
export type TaskStatus = 'pending' | 'completed' | 'cancelled'
export type DemoScenario = 'normal' | 'empty' | 'partial' | 'long' | 'error' | 'offline' | 'timeout'

export interface Notice {
  id: string
  title: string
  raw_text: string
  audience: string[]
  published_at: string | null
  deadline: string | null
  actions: string[]
  priority: Priority
  source_type: 'demo' | 'document' | 'url' | 'user_input'
  source_ref: string | null
  confidence: number
  needs_confirmation: boolean
  created_at: string
}

export interface Course {
  id: string
  student_id: string
  name: string
  teacher: string | null
  weekday: number
  start_time: string
  end_time: string
  location: string | null
  start_week: number
  end_week: number
  week_pattern: 'all' | 'odd' | 'even' | 'custom'
  custom_weeks: number[]
}

export interface Task {
  id: string
  student_id: string
  title: string
  description: string | null
  task_type: 'registration' | 'exam' | 'assignment' | 'course' | 'activity' | 'general'
  priority: Priority
  status: TaskStatus
  due_at: string | null
  source_notice_id: string | null
  dedupe_key: string
  created_at: string
  completed_at: string | null
}

export interface Reminder {
  id: string
  task_id: string
  trigger_at: string
  channel: 'in_app'
  status: 'pending' | 'sent' | 'skipped' | 'failed'
  sent_at: string | null
  failure_reason: string | null
}

export interface TodayBrief {
  date: string
  courses: Course[]
  tasks: Task[]
  notices: Notice[]
  conflicts: string[]
  suggestions: string[]
}

export interface ApiErrorBody {
  code: string
  message: string
  details: Record<string, unknown>
}

export interface ApiResponse<T> {
  ok: boolean
  data: T | null
  error: ApiErrorBody | null
  request_id: string
}

export interface CreateTaskResult {
  task: Task
  created: boolean
  duplicate_of: string | null
}

export interface RagSource {
  source_id: string
  title: string
  valid_at: string
  path: string
  simulated: boolean
}

export interface ChatEvent {
  type: 'tool_running' | 'tool_success' | 'tool_failure' | 'delta' | 'sources' | 'done'
  tool?: string
  content?: string
  sources?: RagSource[]
}
