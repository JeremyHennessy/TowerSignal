import { expect, test, type Page, type TestInfo } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { signInForProject } from './auth.helpers'

// Diagnostic review only: never edit Workflow state or modify production data.
// Findings are retained as measurements, not silently converted into acceptance.
test.use({ trace: 'off' })
test.setTimeout(600_000)
const modes = ['Summary', 'Sales', 'Field', 'Evidence', 'History'] as const
const selectors = ['.account-decision-summary', '.sales-precall-pack', '.technician-field-pack', '.account-evidence-workspace', '.account-unified-timeline']

async function snapshot(page: Page) {
  return page.evaluate(() => {
    const panel = document.querySelector<HTMLElement>('.account-profile-page .detail-panel')
    const tabs = panel?.querySelector<HTMLElement>('.account-mode-tabs')
    const box = (element: Element | null | undefined) => {
      if (!element) return null
      const r = element.getBoundingClientRect()
      return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, width: r.width, height: r.height }
    }
    const visible = (element: Element) => element.getClientRects().length > 0 && getComputedStyle(element).visibility !== 'hidden'
    const hit = (element: Element) => {
      const r = element.getBoundingClientRect()
      const x = Math.max(0, Math.min(innerWidth - 1, r.left + r.width / 2))
      const y = r.top + r.height / 2
      const target = y >= 0 && y < innerHeight ? document.elementFromPoint(x, y) : null
      return { text: element.textContent?.trim(), box: box(element), hit: !!target && (target === element || element.contains(target)), hitElement: target?.tagName, hitClass: target?.getAttribute('class') }
    }
    return {
      url: location.href, viewport: { width: innerWidth, height: innerHeight }, scroll: { x: scrollX, y: scrollY, height: document.documentElement.scrollHeight },
      bodyWidth: document.body.scrollWidth, panelBox: box(panel), tabsBox: box(tabs),
      tabs: Array.from(tabs?.querySelectorAll('button') ?? []).map(hit),
      visibleSections: Array.from(panel?.children ?? []).filter(visible).map(element => ({ tag: element.tagName, class: element.getAttribute('class'), group: element.getAttribute('data-account-mode-group'), heading: element.querySelector('h2,h3,h4')?.textContent, box: box(element) })),
      visibleHeadings: Array.from(panel?.querySelectorAll('h2,h3,h4') ?? []).filter(visible).map(el => el.textContent),
      visibleText: panel?.innerText ?? '',
      hiddenLegacy: Array.from(panel?.querySelectorAll<HTMLElement>(':scope > [data-account-mode-group="legacy-evidence"]') ?? []).map(el => ({ heading: el.querySelector('h3')?.textContent, text: el.textContent, labels: Array.from(el.querySelectorAll('dt')).map(dt => dt.textContent), recordCount: el.querySelectorAll('details').length })),
      evidenceGroups: Array.from(panel?.querySelectorAll<HTMLDetailsElement>('.account-evidence-workspace > details') ?? []).map(el => ({ title: el.querySelector('summary strong')?.textContent, open: el.open, text: el.textContent, links: Array.from(el.querySelectorAll<HTMLAnchorElement>('a[href]')).map(a => ({ text: a.textContent, href: a.href })) })),
      maps: Array.from(panel?.querySelectorAll<HTMLElement>('.leaflet-container') ?? []).filter(visible).map(el => ({ box: box(el), tiles: el.querySelectorAll('img.leaflet-tile').length, loadedTiles: el.querySelectorAll('img.leaflet-tile-loaded').length, clientWidth: el.clientWidth, clientHeight: el.clientHeight })),
      errors: Array.from(panel?.querySelectorAll('.error-state,.loading-state') ?? []).filter(visible).map(el => el.textContent),
    }
  })
}
async function attach(page: Page, info: TestInfo, name: string, fullPage = false) {
  await info.attach(name, { body: await page.screenshot({ fullPage, animations: 'disabled' }), contentType: 'image/png' })
}

test('full Account mode, expanded-source, share, and scrolled-navigation review', async ({ page }, info) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  const measurements: unknown[] = []
  await signInForProject(page, info.project.name, '#/account/2000015564')
  const panel = page.locator('.account-profile-page .detail-panel')
  const tabs = panel.locator('.account-mode-tabs')
  await expect(tabs).toBeVisible({ timeout: 120_000 })
  for (const [index, mode] of modes.entries()) {
    await tabs.getByRole('button', { name: new RegExp(`^${mode}`) }).click()
    if (mode !== 'Evidence' || process.env.CANDIDATE_ROOT) await expect(panel.locator(selectors[index])).toBeVisible({ timeout: 120_000 })
    if (mode === 'Evidence' && await panel.locator('.account-evidence-workspace').count()) {
      await expect(panel.locator('.account-evidence-workspace > details')).toHaveCount(7, { timeout: 120_000 })
      const groups = panel.locator('.account-evidence-workspace > details')
      for (let i = 0; i < 7; i++) {
        await groups.nth(i).locator(':scope > summary').click()
        await attach(page, info, `Evidence-group-${i + 1}`)
      }
      await panel.locator('.account-evidence-workspace .loading-state').first().waitFor({ state: 'hidden', timeout: 120_000 }).catch(() => {})
    }
    await page.evaluate(() => window.scrollTo(0, 0))
    await attach(page, info, `${mode}-top`)
    measurements.push({ mode, position: 'top', ...(await snapshot(page)) })
    await page.evaluate(() => window.scrollTo(0, Math.min(900, document.documentElement.scrollHeight - innerHeight)))
    await attach(page, info, `${mode}-scroll`)
    measurements.push({ mode, position: 'scroll', ...(await snapshot(page)) })
    // Native full-page screenshots retain lower content that the earlier viewport-only proof missed.
    await attach(page, info, `${mode}-full`, true)
  }
  // Switching from the bottom of a long mode must be observed, not assumed safe.
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
  measurements.push({ mode: 'History', position: 'bottom', ...(await snapshot(page)) })
  await tabs.getByRole('button', { name: /^Sales/ }).click()
  measurements.push({ mode: 'Sales', position: 'after-long-history', ...(await snapshot(page)) })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(tabs).toBeVisible({ timeout: 120_000 })
  measurements.push({ position: 'reload-share-url', ...(await snapshot(page)) })
  await info.attach('account-full-review.json', { body: JSON.stringify({ target: process.env.CANDIDATE_ROOT ? 'candidate-on-accepted-data' : 'live', errors, measurements }, null, 2), contentType: 'application/json' })
  expect(errors, 'Runtime errors during full Account navigation').toEqual([])
})

test('representative Accounts expose source payload without silently losing DOB records', async ({ page }, info) => {
  const base = info.project.use.baseURL as string
  const payload = process.env.CANDIDATE_ROOT
    ? JSON.parse(await readFile(path.join(process.env.CANDIDATE_ROOT, 'data/systems.json'), 'utf8'))
    : await (await page.request.get(new URL('data/systems.json', base).href)).json()
  const rows = payload.systems as Array<Record<string, any>>
  const selected = new Map<string, string>()
  const pick = (label: string, condition: (row: Record<string, any>) => boolean, score: (row: Record<string, any>) => number = () => 0) => {
    const found = rows.filter(condition).sort((a, b) => score(b) - score(a))[0]
    if (found) selected.set(String(found.system_id), label)
  }
  pick('high-priority', r => r.priority_score >= 70, r => r.priority_score)
  pick('no-contact', r => r.hpd_contact_count === 0)
  pick('institutional', r => r.cms_institutional_facility_count > 0)
  pick('multi-tower', r => r.active_equipment > 1, r => r.active_equipment)
  pick('DWT-heavy', r => r.nyc_building_water_signal_count > 0, r => r.nyc_building_water_signal_count)
  pick('outer-borough', r => r.borough && r.borough !== 'MANHATTAN')
  pick('DOB-heavy', r => r.dob_recent_activity_count > 0, r => r.dob_recent_activity_count)
  const results: unknown[] = []
  for (const [systemId, category] of selected) {
    await signInForProject(page, info.project.name, `#/account/${systemId}`)
    const panel = page.locator('.account-profile-page .detail-panel')
    const tabs = panel.locator('.account-mode-tabs')
    await expect(tabs).toBeVisible({ timeout: 120_000 })
    await tabs.getByRole('button', { name: /^Evidence/ }).click()
    const workspace = panel.locator('.account-evidence-workspace')
    if (await workspace.count()) {
      await expect(workspace.locator(':scope > details')).toHaveCount(7, { timeout: 120_000 })
      const project = workspace.locator(':scope > details').filter({ has: page.locator('summary strong', { hasText: 'Project Activity' }) })
      await project.locator(':scope > summary').click()
      const ownership = workspace.locator(':scope > details').filter({ has: page.locator('summary strong', { hasText: 'Property / Ownership' }) })
      await ownership.locator(':scope > summary').click()
    }
    results.push({ systemId, category, ...(await snapshot(page)) })
    await attach(page, info, `${category}-${systemId}`)
  }
  await info.attach('representative-account-review.json', { body: JSON.stringify(results, null, 2), contentType: 'application/json' })
  expect(selected.size).toBeGreaterThan(0)
})
