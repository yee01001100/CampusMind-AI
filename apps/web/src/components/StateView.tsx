import { Icon, type IconName } from './Icon'

export function LoadingView({ rows = 3, label = '正在读取数据' }: { rows?: number; label?: string }) {
  return (
    <div className="state-view" role="status" aria-label={label}>
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }, (_, index) => (
        <div className="skeleton-row" key={index} style={{ width: `${92 - index * 11}%` }} />
      ))}
    </div>
  )
}

export function EmptyView({ title, detail, action }: { title: string; detail: string; action?: React.ReactNode }) {
  return (
    <div className="state-view empty-view">
      <span className="empty-mark" aria-hidden="true">✓</span>
      <h3>{title}</h3>
      <p>{detail}</p>
      {action}
    </div>
  )
}

export function ErrorView({ title = '暂时没有拿到数据', detail, retry, icon = 'wifi' }: { title?: string; detail: string; retry?: () => void; icon?: IconName }) {
  return (
    <div className="state-view error-view" role="alert">
      <Icon name={icon} />
      <h3>{title}</h3>
      <p>{detail}</p>
      {retry && <button className="button secondary" onClick={retry}><Icon name="refresh" />重新尝试</button>}
    </div>
  )
}

export function PriorityBadge({ priority }: { priority: 'critical' | 'high' | 'medium' | 'normal' }) {
  const labels = { critical: '紧急', high: '高', medium: '中', normal: '普通' }
  return <span className={`priority priority-${priority}`}><span aria-hidden="true" className="priority-dot" />{labels[priority]}</span>
}
