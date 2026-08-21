import { useEffect, useRef, useState } from 'react'
import { apiClient } from '../api/client'
import { Icon } from '../components/Icon'
import type { RagSource } from '../types'
import { errorCopy } from '../utils'

interface Message {
  id: string
  role: 'user' | 'agent'
  content: string
  sources?: RagSource[]
}

type ToolStatus = 'idle' | 'running' | 'success' | 'failure'

const welcome: Message = {
  id: 'welcome',
  role: 'agent',
  content: '你好，我可以结合今天的课表、待办和模拟校园资料回答问题。每条资料型回答都会展示来源。',
}

export function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([welcome])
  const [draft, setDraft] = useState('我今天最需要先做什么？')
  const [sending, setSending] = useState(false)
  const [tool, setTool] = useState<{ status: ToolStatus; name: string; detail?: string }>({ status: 'idle', name: '' })
  const [error, setError] = useState<string | null>(null)
  const [lastPrompt, setLastPrompt] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const conversationRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    conversationRef.current?.scrollTo({ top: conversationRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, tool])

  useEffect(() => () => abortRef.current?.abort(), [])

  const submit = async (prompt = draft) => {
    if (!prompt.trim() || sending) return
    const question = prompt.trim()
    setLastPrompt(question)
    setDraft('')
    setError(null)
    setSending(true)
    setTool({ status: 'idle', name: '' })
    setMessages((current) => [...current, { id: `user-${Date.now()}`, role: 'user', content: question }, { id: `agent-${Date.now()}`, role: 'agent', content: '' }])
    const controller = new AbortController()
    abortRef.current = controller

    try {
      for await (const event of apiClient.streamChat(question, undefined, controller.signal)) {
        if (event.type === 'tool_running') setTool({ status: 'running', name: event.tool ?? 'campus_tool' })
        if (event.type === 'tool_success') setTool({ status: 'success', name: event.tool ?? 'campus_tool' })
        if (event.type === 'tool_failure') setTool({ status: 'failure', name: event.tool ?? 'campus_tool', detail: event.content })
        if (event.type === 'delta' && event.content) {
          setMessages((current) => current.map((message, index) => index === current.length - 1 ? { ...message, content: message.content + event.content } : message))
        }
        if (event.type === 'sources' && event.sources) {
          setMessages((current) => current.map((message, index) => index === current.length - 1 ? { ...message, sources: event.sources } : message))
        }
      }
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === 'AbortError') {
        setError('回复已中断，你可以重新发送这条问题。')
      } else {
        setError(errorCopy(reason))
      }
      setMessages((current) => current.filter((message, index) => !(index === current.length - 1 && !message.content)))
    } finally {
      setSending(false)
      abortRef.current = null
    }
  }

  const interrupt = () => abortRef.current?.abort()

  return (
    <section className="page-section chat-page">
      <div className="chat-layout">
        <section className="chat-surface" aria-labelledby="chat-title">
          <div className="chat-heading"><div><span className="agent-avatar"><Icon name="spark" /></span><div><h2 id="chat-title">Campus Agent</h2><p><span className="status-dot" />在线 · 不展示内部推理</p></div></div><span className="mode-badge">校园知识模式</span></div>
          <div className="conversation" ref={conversationRef} aria-live="polite" aria-label="对话记录">
            {messages.map((message) => (
              <article className={`message ${message.role}`} key={message.id}>
                <span className="message-author">{message.role === 'user' ? '你' : <Icon name="spark" />}</span>
                <div className="message-body">
                  <p>{message.content || <span className="typing-dots" aria-label="正在生成回复"><i /><i /><i /></span>}</p>
                  {message.sources?.length ? (
                    <div className="rag-sources"><b><Icon name="book" />资料来源</b>{message.sources.map((source) => <a key={source.source_id} href={source.path} onClick={(event) => event.preventDefault()}><span>{source.title}</span><small>{source.valid_at} · {source.simulated ? '模拟资料' : '校园资料'}</small></a>)}</div>
                  ) : null}
                </div>
              </article>
            ))}
            {tool.status !== 'idle' && (
              <div className={`tool-status ${tool.status}`} role="status"><Icon name="tool" /><div><b>{tool.status === 'running' ? 'Tool 正在运行' : tool.status === 'success' ? 'Tool 调用成功' : 'Tool 调用失败'}</b><span>{tool.name}{tool.detail ? ` · ${tool.detail}` : ''}</span></div>{tool.status === 'running' && <span className="tool-spinner" />}</div>
            )}
            {error && <div className="chat-error" role="alert"><Icon name="wifi" /><div><b>这次回复没有完成</b><span>{error}</span></div><button className="text-action" onClick={() => submit(lastPrompt)} disabled={sending}><Icon name="refresh" />重试</button></div>}
          </div>
          <form className="composer" onSubmit={(event) => { event.preventDefault(); void submit() }}>
            <label className="sr-only" htmlFor="chat-input">向 Campus Agent 提问</label>
            <textarea id="chat-input" rows={2} value={draft} onChange={(event) => setDraft(event.target.value)} placeholder="问问今天的课程、待办或校园规定……" onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void submit() } }} />
            {sending ? <button className="button danger compact" type="button" onClick={interrupt}><Icon name="close" />中断</button> : <button className="button primary send-button" type="submit" disabled={!draft.trim()} aria-label="发送消息"><Icon name="send" /></button>}
          </form>
          <p className="composer-note">Enter 发送，Shift + Enter 换行 · 回答仅作事务辅助，请以正式来源为准</p>
        </section>

        <aside className="chat-context" aria-label="当前上下文">
          <div><span>当前上下文</span><h3>Agent 能看到什么</h3></div>
          <dl>
            <div><dt><Icon name="calendar" />今日课表</dt><dd>2 节</dd></div>
            <div><dt><Icon name="check" />未完成待办</dt><dd>2 项</dd></div>
            <div><dt><Icon name="book" />校园资料库</dt><dd>12 份模拟资料</dd></div>
          </dl>
          <div className="privacy-note"><Icon name="source" /><p><b>数据边界</b><span>前端不会接触模型密钥，也不会读取校园账号、Cookie 或密码。</span></p></div>
          <div className="suggested-prompts"><h4>可以这样问</h4>{['我今天最需要先做什么？', '奖学金材料什么时候截止？', '下一节课在哪里？'].map((prompt) => <button key={prompt} onClick={() => { setDraft(prompt); }}>{prompt}<Icon name="arrow" /></button>)}</div>
        </aside>
      </div>
    </section>
  )
}
