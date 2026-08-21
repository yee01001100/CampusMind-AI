import { useMemo, useState } from 'react'
import { apiClient } from './api/client'
import { Icon, type IconName } from './components/Icon'
import { ChatPage } from './pages/ChatPage'
import { DashboardPage } from './pages/DashboardPage'
import { NoticePage } from './pages/NoticePage'
import { PlannerPage } from './pages/PlannerPage'
import type { DemoScenario } from './types'

export type ViewName = 'today' | 'notice' | 'planner' | 'chat'

const views: Array<{ id: ViewName; label: string; short: string; icon: IconName }> = [
  { id: 'today', label: '今日简报', short: '今日', icon: 'home' },
  { id: 'notice', label: '通知解析', short: '通知', icon: 'notice' },
  { id: 'planner', label: '课表与待办', short: '计划', icon: 'calendar' },
  { id: 'chat', label: '问问 Agent', short: '问问', icon: 'chat' },
]

const scenarioLabels: Record<DemoScenario, string> = {
  normal: '正常数据',
  empty: '空数据',
  partial: '局部缺失',
  long: '超长内容',
  error: '服务错误',
  offline: '离线',
  timeout: '请求超时',
}

export function App() {
  const [view, setView] = useState<ViewName>('today')
  const [scenario, setScenario] = useState<DemoScenario>('normal')
  const [refreshKey, setRefreshKey] = useState(0)
  const selectedView = useMemo(() => views.find((item) => item.id === view)!, [view])

  const changeView = (next: ViewName) => {
    setView(next)
    window.scrollTo?.({ top: 0, behavior: 'smooth' })
  }

  const changeScenario = (next: DemoScenario) => {
    setScenario(next)
    apiClient.setScenario?.(next)
    setRefreshKey((value) => value + 1)
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <aside className="sidebar" aria-label="主导航">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><Icon name="spark" /></span>
          <span><b>CampusMind</b><small>校园智能事务台</small></span>
        </div>
        <nav className="desktop-nav">
          {views.map((item) => (
            <button key={item.id} className={view === item.id ? 'active' : ''} aria-current={view === item.id ? 'page' : undefined} onClick={() => changeView(item.id)}>
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="status-dot" />
          <div><b>{apiClient.mode === 'mock' ? '演示数据已就绪' : '后端已连接'}</b><small>{apiClient.mode === 'mock' ? '全部内容均为模拟数据' : '仅通过校园 API 读取'}</small></div>
        </div>
      </aside>

      <div className="app-body">
        <header className="topbar">
          <div>
            <span className="mobile-brand">CampusMind</span>
            <h1>{selectedView.label}</h1>
          </div>
          <div className="topbar-actions">
            {apiClient.mode === 'mock' && (
              <label className="scenario-control">
                <span>演示场景</span>
                <select aria-label="切换演示场景" value={scenario} onChange={(event) => changeScenario(event.target.value as DemoScenario)}>
                  {Object.entries(scenarioLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                </select>
              </label>
            )}
            <button className="icon-button" aria-label="通知中心"><Icon name="bell" /><span className="notification-dot" /></button>
            <span className="avatar" aria-label="模拟学生账户">同学</span>
          </div>
        </header>

        <main id="main-content" tabIndex={-1}>
          {view === 'today' && <DashboardPage key={`today-${refreshKey}`} onNavigate={changeView} />}
          {view === 'notice' && <NoticePage key={`notice-${refreshKey}`} />}
          {view === 'planner' && <PlannerPage key={`planner-${refreshKey}`} />}
          {view === 'chat' && <ChatPage key={`chat-${refreshKey}`} />}
        </main>
      </div>

      <nav className="mobile-nav" aria-label="移动端主导航">
        {views.map((item) => (
          <button key={item.id} className={view === item.id ? 'active' : ''} aria-current={view === item.id ? 'page' : undefined} onClick={() => changeView(item.id)}>
            <Icon name={item.icon} />
            <span>{item.short}</span>
          </button>
        ))}
      </nav>
    </div>
  )
}
