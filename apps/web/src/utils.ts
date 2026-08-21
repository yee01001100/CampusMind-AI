import type { Priority } from './types'

export const priorityLabel: Record<Priority, string> = {
  critical: '紧急',
  high: '高优先级',
  medium: '中优先级',
  normal: '普通',
}

export function formatDateTime(value: string | null, options?: Intl.DateTimeFormatOptions) {
  if (!value) return '待确认'
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    ...options,
  }).format(new Date(value))
}

export function formatDay(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }).format(new Date(`${value}T12:00:00+08:00`))
}

export function errorCopy(error: unknown) {
  if (error instanceof Error) return error.message
  return '发生未知错误，请稍后重试'
}
