import { readFileSync, writeFileSync } from 'node:fs'
import { test, type Page } from '@playwright/test'

// Set AXE_PATH to a local axe-core/axe.min.js. Results go to AUDIT_OUT as JSON.
const axeSource = readFileSync(process.env.AXE_PATH as string, 'utf-8')
const results: unknown[] = []

const documents = {
  count: 2,
  next: null,
  previous: null,
  results: [1, 2].map((id) => ({
    id,
    title: `Fixture Document ${id}`,
    content: null,
    correspondent: null,
    document_type: null,
    document_date: '2026-01-01',
    created: '2026-01-01T00:00:00Z',
    modified: '2026-01-01T00:00:00Z',
    tags: [],
    correspondent_name: null,
    review_status: null,
    local_cached: false,
    local_overrides: false,
    has_embeddings: false,
    has_suggestions: false,
    has_vision_pages: false,
  })),
}

const stubApi = (page: Page) =>
  page.route('**/api/**', (route) => {
    const isList = /\/api\/documents\/(\?.*)?$/.test(route.request().url())
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(isList ? documents : { results: [], items: [], count: 0 }),
    })
  })

const viewports = { desktop: { width: 1366, height: 800 }, mobile: { width: 375, height: 812 } }
const routes = ['/', '/queue', '/writeback', '/documents/1']

for (const [viewportName, viewport] of Object.entries(viewports)) {
  for (const route of routes) {
    test(`${viewportName} ${route}`, async ({ page }) => {
      await page.setViewportSize(viewport)
      await stubApi(page)
      await page.goto(route)
      await page.waitForTimeout(1500)
      await page.evaluate(axeSource)
      const axe = await page.evaluate(async () => {
        const run = await (window as unknown as { axe: { run: () => Promise<{ violations: { id: string; impact: string; nodes: unknown[] }[] }> } }).axe.run()
        return run.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }))
      })
      const layout = await page.evaluate(() => ({
        overflowPx: document.documentElement.scrollWidth - window.innerWidth,
        smallTargets: [...document.querySelectorAll('a,button,input,select')].filter((el) => {
          const box = el.getBoundingClientRect()
          return box.width > 0 && (box.width < 24 || box.height < 24)
        }).length,
        text: document.body.innerText.slice(0, 80),
      }))
      const stops: string[] = []
      let invisibleFocus = 0
      for (let i = 0; i < 40; i++) {
        await page.keyboard.press('Tab')
        const info = await page.evaluate(() => {
          const el = document.activeElement as HTMLElement | null
          if (!el || el === document.body) return null
          const style = getComputedStyle(el)
          return {
            label: (el.innerText || el.getAttribute('aria-label') || el.tagName).trim().slice(0, 30),
            href: el.getAttribute('href') || '',
            visible: style.outlineStyle !== 'none' || style.boxShadow !== 'none',
          }
        })
        if (!info) break
        stops.push(info.href || info.label)
        if (!info.visible) invisibleFocus += 1
      }
      const firstRow = stops.findIndex((stop) => /\/documents\/\d+/.test(stop))
      results.push({ viewportName, route, axe, layout, tabStops: stops.length, tabsToFirstRow: firstRow, invisibleFocus })
      writeFileSync(process.env.AUDIT_OUT as string, JSON.stringify(results, null, 1))
    })
  }
}
