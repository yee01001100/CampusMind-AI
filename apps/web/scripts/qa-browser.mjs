import { mkdir } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { resolve } from 'node:path'

const require = createRequire(import.meta.url)
const playwrightPath = process.argv[2] || 'playwright'
const { chromium } = require(playwrightPath)
const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const baseUrl = process.env.CAMPUSMIND_QA_URL || 'http://127.0.0.1:4173/'
const outputDir = resolve('.qa-artifacts')
const sizes = [
  { name: 'mobile-375', width: 375, height: 812 },
  { name: 'desktop-1366', width: 1366, height: 768 },
  { name: 'desktop-1440', width: 1440, height: 900 },
]

await mkdir(outputDir, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: edgePath })
const results = []

try {
  for (const size of sizes) {
    const page = await browser.newPage({ viewport: { width: size.width, height: size.height }, deviceScaleFactor: 1 })
    await page.goto(baseUrl, { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: '早上好，同学' }).waitFor()

    const layout = await page.evaluate(() => {
      const sidebar = document.querySelector('.sidebar')
      const mobileNav = document.querySelector('.mobile-nav')
      const isVisible = (element) => element instanceof HTMLElement && getComputedStyle(element).display !== 'none' && element.getBoundingClientRect().width > 0
      return {
        viewportWidth: window.innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        bodyWidth: document.body.scrollWidth,
        sidebarVisible: isVisible(sidebar),
        mobileNavVisible: isVisible(mobileNav),
        mainBottom: document.querySelector('main')?.getBoundingClientRect().bottom ?? 0,
      }
    })

    const overflow = Math.max(layout.documentWidth, layout.bodyWidth) > size.width + 1
    const expectedNav = size.width <= 820 ? layout.mobileNavVisible && !layout.sidebarVisible : layout.sidebarVisible && !layout.mobileNavVisible
    if (overflow) throw new Error(`${size.name}: horizontal overflow (${layout.documentWidth}/${layout.bodyWidth} > ${size.width})`)
    if (!expectedNav) throw new Error(`${size.name}: responsive navigation mismatch`)

    await page.getByLabel('切换演示场景').selectOption('long')
    await page.getByText(/跨学院综合实践项目材料提交与资格复核特别说明/).waitFor()
    const longOverflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > window.innerWidth + 1)
    if (longOverflow) throw new Error(`${size.name}: long content caused horizontal overflow`)
    await page.getByLabel('切换演示场景').selectOption('normal')
    await page.getByText('人工智能导论').waitFor()

    await page.screenshot({ path: resolve(outputDir, `${size.name}.png`), fullPage: true })
    const routeChecks = [
      { button: size.width <= 820 ? '通知' : '通知解析', heading: '把通知变成清楚的待办' },
      { button: size.width <= 820 ? '计划' : '课表与待办', heading: '课表与待办' },
      { button: size.width <= 820 ? '问问' : '问问 Agent', heading: 'Campus Agent' },
    ]
    for (const route of routeChecks) {
      await page.getByRole('button', { name: route.button, exact: true }).click()
      await page.locator('main').getByRole('heading', { name: route.heading, exact: true }).waitFor()
      const routeOverflow = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) > window.innerWidth + 1)
      if (routeOverflow) throw new Error(`${size.name}: ${route.heading} caused horizontal overflow`)
    }
    results.push({ ...size, overflow: false, responsiveNav: true, longText: true, routes: 4 })
    await page.close()
  }

  const flowPage = await browser.newPage({ viewport: { width: 375, height: 812 } })
  await flowPage.goto(baseUrl, { waitUntil: 'networkidle' })
  await flowPage.getByRole('navigation', { name: '移动端主导航' }).getByRole('button', { name: '通知' }).click()
  await flowPage.getByRole('heading', { name: '把通知变成清楚的待办' }).waitFor()
  await flowPage.getByRole('button', { name: /解析通知/ }).click()
  await flowPage.getByText('有字段需要人工确认').waitFor()
  await flowPage.getByRole('checkbox', { name: /我已核对/ }).check()
  await flowPage.getByRole('button', { name: /确认并创建任务/ }).click()
  await flowPage.getByText('任务创建成功').waitFor()
  await flowPage.getByRole('navigation', { name: '移动端主导航' }).getByRole('button', { name: '问问' }).click()
  await flowPage.getByRole('heading', { name: 'Campus Agent' }).waitFor()
  await flowPage.screenshot({ path: resolve(outputDir, 'mobile-chat.png'), fullPage: true })
  await flowPage.close()

  console.log(JSON.stringify({ ok: true, sizes: results, flow: 'notice parse -> confirm -> task -> chat' }, null, 2))
} finally {
  await browser.close()
}
