import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { apiClient } from './api/client'
import { App } from './App'

describe('CampusMind app flows', () => {
  it('renders the complete today brief', async () => {
    render(<App />)
    expect(await screen.findByText('人工智能导论')).toBeInTheDocument()
    expect(screen.getByText('确认奖学金材料并提交')).toBeInTheDocument()
    expect(screen.getByText('模拟奖学金材料提交提醒')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '时间冲突' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Agent 建议' })).toBeInTheDocument()
  })

  it('renders an instructive empty state', async () => {
    apiClient.setScenario?.('empty')
    render(<App />)
    expect(await screen.findByRole('heading', { name: '今天暂时没有安排' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /解析通知/ })).toBeEnabled()
  })

  it('renders service errors and a keyboard-operable retry', async () => {
    apiClient.setScenario?.('error')
    render(<App />)
    const retry = await screen.findByRole('button', { name: /重新尝试/ })
    retry.focus()
    expect(retry).toHaveFocus()
    expect(screen.getByRole('alert')).toHaveTextContent('演示服务暂时不可用')
  })

  it('renders long titles without dropping the content', async () => {
    apiClient.setScenario?.('long')
    render(<App />)
    expect(await screen.findByText(/跨学院综合实践项目材料提交与资格复核特别说明/)).toBeInTheDocument()
  })

  it('keeps usable content visible when the brief is partial', async () => {
    apiClient.setScenario?.('partial')
    render(<App />)
    expect(await screen.findByText('部分数据尚未返回')).toBeInTheDocument()
    expect(screen.getByText('人工智能导论')).toBeInTheDocument()
  })

  it('parses a notice, requires confirmation, and prevents a duplicate task', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: '通知解析' }))
    await user.click(screen.getByRole('button', { name: /解析通知/ }))
    expect(await screen.findByText('有字段需要人工确认')).toBeInTheDocument()
    const create = screen.getByRole('button', { name: /确认并创建任务/ })
    expect(create).toBeDisabled()
    await user.click(screen.getByRole('checkbox', { name: /我已核对/ }))
    await user.click(create)
    expect(await screen.findByText('任务创建成功')).toBeInTheDocument()
    await user.click(create)
    expect(await screen.findByText('任务已存在，未重复创建')).toBeInTheDocument()
  })

  it('completes and restores a task from the planner', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: '课表与待办' }))
    const complete = await screen.findByRole('button', { name: '完成任务：确认奖学金材料并提交' })
    await user.click(complete)
    expect(await screen.findByRole('button', { name: '恢复任务：确认奖学金材料并提交' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '恢复任务：确认奖学金材料并提交' }))
    expect(await screen.findByRole('button', { name: '完成任务：确认奖学金材料并提交' })).toBeInTheDocument()
  })

  it('streams an Agent reply with Tool success and a RAG source', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: '问问 Agent' }))
    const input = screen.getByLabelText('向 Campus Agent 提问')
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' })
    expect(await screen.findByText('Tool 调用成功')).toBeInTheDocument()
    expect(await screen.findByText(/你下一节是 10:00/)).toBeInTheDocument()
    expect(await screen.findByText('模拟教务处 · 今日事务数据')).toBeInTheDocument()
  })

  it('shows an interrupted stream and offers retry', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(screen.getByRole('button', { name: '问问 Agent' }))
    await user.click(screen.getByRole('button', { name: '发送消息' }))
    await user.click(await screen.findByRole('button', { name: /中断/ }))
    expect(await screen.findByRole('alert')).toHaveTextContent('回复已中断')
    expect(screen.getByRole('button', { name: /重试/ })).toBeEnabled()
  })

  it('shows a timeout with a retry action', async () => {
    const user = userEvent.setup()
    apiClient.setScenario?.('timeout')
    render(<App />)
    await user.click(screen.getByRole('button', { name: '问问 Agent' }))
    await user.click(screen.getByRole('button', { name: '发送消息' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('请求超时')
    expect(screen.getByRole('button', { name: /重试/ })).toBeEnabled()
  })

  it('reports Tool failure without exposing internal logs', async () => {
    const user = userEvent.setup()
    apiClient.setScenario?.('error')
    render(<App />)
    await user.click(screen.getByRole('button', { name: '问问 Agent' }))
    await user.click(screen.getByRole('button', { name: '发送消息' }))
    expect(await screen.findByText('Tool 调用失败')).toBeInTheDocument()
    expect(await screen.findByRole('alert')).toHaveTextContent('课程工具调用失败')
    expect(screen.queryByText(/chain.of.thought|system prompt|token/i)).not.toBeInTheDocument()
  })

  it('exposes a mobile navigation landmark and all primary routes', async () => {
    render(<App />)
    const mobileNav = screen.getByRole('navigation', { name: '移动端主导航' })
    expect(mobileNav).toBeInTheDocument()
    expect(mobileNav.querySelectorAll('button')).toHaveLength(4)
    await waitFor(() => expect(screen.getByRole('main')).toBeInTheDocument())
  })
})
