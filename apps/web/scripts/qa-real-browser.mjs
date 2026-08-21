import { mkdir } from 'node:fs/promises'
import { resolve } from 'node:path'
import { chromium } from 'playwright'

const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const baseUrl = process.env.CAMPUSMIND_QA_URL || 'http://127.0.0.1:4173/'
const outputDir = resolve('.qa-artifacts')
const sizes = [
  { name: 'real-mobile-375', width: 375, height: 812 },
  { name: 'real-desktop-1366', width: 1366, height: 768 },
  { name: 'real-desktop-1440', width: 1440, height: 900 },
]

await mkdir(outputDir, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: edgePath })
const results = []

function collectErrors(page) {
  const errors = []
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`))
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`)
  })
  return errors
}

try {
  for (const size of sizes) {
    const page = await browser.newPage({ viewport: { width: size.width, height: size.height } })
    const errors = collectErrors(page)
    await page.goto(baseUrl, { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: '早上好，同学' }).waitFor()
    if (await page.getByLabel('切换演示场景').count()) {
      throw new Error(`${size.name}: still running in mock mode`)
    }
    const layout = await page.evaluate(() => {
      const visible = (selector) => {
        const element = document.querySelector(selector)
        return element instanceof HTMLElement && getComputedStyle(element).display !== 'none' && element.getBoundingClientRect().width > 0
      }
      return {
        width: Math.max(document.documentElement.scrollWidth, document.body.scrollWidth),
        sidebar: visible('.sidebar'),
        mobileNav: visible('.mobile-nav'),
      }
    })
    if (layout.width > size.width + 1) throw new Error(`${size.name}: horizontal overflow`)
    const responsive = size.width <= 820 ? layout.mobileNav && !layout.sidebar : layout.sidebar && !layout.mobileNav
    if (!responsive) throw new Error(`${size.name}: responsive navigation mismatch`)

    const routes = [
      { button: size.width <= 820 ? '通知' : '通知解析', heading: '把通知变成清楚的待办' },
      { button: size.width <= 820 ? '计划' : '课表与待办', heading: '课表与待办' },
      { button: size.width <= 820 ? '问问' : '问问 Agent', heading: 'Campus Agent' },
    ]
    for (const route of routes) {
      await page.getByRole('button', { name: route.button, exact: true }).click()
      await page.locator('main').getByRole('heading', { name: route.heading, exact: true }).waitFor()
    }
    await page.screenshot({ path: resolve(outputDir, `${size.name}.png`), fullPage: true })
    if (errors.length) throw new Error(`${size.name}: ${errors.join(' | ')}`)
    results.push({ ...size, routes: 4, overflow: false, consoleErrors: 0 })
    await page.close()
  }

  const flow = await browser.newPage({ viewport: { width: 375, height: 812 } })
  const flowErrors = collectErrors(flow)
  await flow.goto(baseUrl, { waitUntil: 'networkidle' })
  await flow.getByRole('navigation', { name: '移动端主导航' }).getByRole('button', { name: '通知' }).click()
  const unique = Date.now()
  await flow.getByLabel('校园通知正文').fill(`【模拟数据】2026年8月28日 18:00前，要求：提交真实联调材料 ${unique}`)
  await flow.getByRole('button', { name: /解析通知/ }).click()
  await flow.getByText('有字段需要人工确认').waitFor()
  await flow.getByRole('checkbox', { name: /我已核对/ }).check()
  await flow.getByRole('button', { name: /确认并创建任务/ }).click()
  await flow.getByText('任务创建成功').waitFor()

  await flow.getByRole('navigation', { name: '移动端主导航' }).getByRole('button', { name: '计划' }).click()
  await flow.getByText(/提交真实联调材料/).first().waitFor()
  await flow.getByRole('navigation', { name: '移动端主导航' }).getByRole('button', { name: '问问' }).click()
  await flow.getByLabel('向 Campus Agent 提问').fill('学校规定考试管理是什么？')
  await flow.getByRole('button', { name: '发送消息' }).click()
  await flow.getByText('资料来源').waitFor()
  await flow.getByText('模拟考试管理规定').waitFor()
  await flow.screenshot({ path: resolve(outputDir, 'real-mobile-flow.png'), fullPage: true })
  if (flowErrors.length) throw new Error(`real flow: ${flowErrors.join(' | ')}`)
  await flow.close()

  console.log(JSON.stringify({
    ok: true,
    sizes: results,
    flow: 'SQLite brief -> notice confirm -> task persistence -> Runtime/RAG source',
  }, null, 2))
} finally {
  await browser.close()
}
