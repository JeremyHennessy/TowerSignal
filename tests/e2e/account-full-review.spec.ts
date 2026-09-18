import { expect, test, type Page, type TestInfo } from '@playwright/test'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { signInForProject } from './auth.helpers'
import type { SystemSummary } from '../../src/types/data'

// Read-only diagnostics. A captured screen is not release acceptance.
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
      const x = Math.max(0, Math.min(innerWidth - 1, r.left + r.width / 2)), y = r.top + r.height / 2
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
      signedOut: !!Array.from(document.querySelectorAll('h1,h2')).find(el => el.textContent === 'Sign in to TowerSignal'),
    }
  })
}
async function attach(page: Page, info: TestInfo, name: string, fullPage = false) {
  await info.attach(name, { body: await page.screenshot({ fullPage, animations: 'disabled' }), contentType: 'image/png' })
}

test('full Account modes, expanded sources, long scroll and reload diagnostics', async ({ page }, info) => {
  const errors: string[] = [], measurements: unknown[] = []
  page.on('pageerror', e => errors.push(e.message))
  try {
    await signInForProject(page, info.project.name, '#/account/2000015564')
    const panel = page.locator('.account-profile-page .detail-panel'), tabs = panel.locator('.account-mode-tabs')
    await expect(tabs).toBeVisible({ timeout: 120_000 })
    for (const [index, mode] of modes.entries()) {
      await tabs.getByRole('button', { name: new RegExp(`^${mode}`) }).click()
      if (mode !== 'Evidence' || process.env.CANDIDATE_ROOT) await expect(panel.locator(selectors[index])).toBeVisible({ timeout: 120_000 })
      if (mode === 'Evidence' && await panel.locator('.account-evidence-workspace').count()) {
        const groups = panel.locator('.account-evidence-workspace > details')
        await expect(groups).toHaveCount(7, { timeout: 120_000 })
        for (let i = 0; i < 7; i++) {
          await groups.nth(i).locator(':scope > summary').click()
          await attach(page, info, `Evidence-group-${i + 1}`)
        }
      }
      await page.evaluate(() => window.scrollTo(0, 0))
      await attach(page, info, `${mode}-top`)
      measurements.push({ mode, position: 'top', ...(await snapshot(page)) })
      await page.evaluate(() => window.scrollTo(0, Math.min(900, document.documentElement.scrollHeight - innerHeight)))
      await attach(page, info, `${mode}-scroll`)
      measurements.push({ mode, position: 'scroll', ...(await snapshot(page)) })
      await attach(page, info, `${mode}-full`, true)
    }
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
    measurements.push({ mode: 'History', position: 'bottom', ...(await snapshot(page)) })
    await tabs.getByRole('button', { name: /^Sales/ }).click()
    measurements.push({ mode: 'Sales', position: 'after-long-history', ...(await snapshot(page)) })
    await page.reload({ waitUntil: 'domcontentloaded' })
    await expect(tabs).toBeVisible({ timeout: 30_000 })
    measurements.push({ position: 'reload-share-url', ...(await snapshot(page)) })
    expect(errors).toEqual([])
  } finally {
    measurements.push({ position: 'final-state-including-failure', ...(await snapshot(page)) })
    await info.attach('account-full-review.json', { body: JSON.stringify({ target: process.env.CANDIDATE_ROOT ? 'candidate-on-accepted-data' : 'actual-hosted', errors, measurements }, null, 2), contentType: 'application/json' })
  }
})

test('distinct source-rich Accounts and retained baseline Account diagnostics', async ({ page }, info) => {
  const base = info.project.use.baseURL as string
  const payload = process.env.CANDIDATE_ROOT
    ? JSON.parse(await readFile(path.join(process.env.CANDIDATE_ROOT, 'data/systems.json'), 'utf8'))
    : await (await page.request.get(new URL('data/systems.json', base).href)).json()
  const rows = payload.systems as SystemSummary[], used = new Set<string>()
  const selected: Array<{ systemId: string; category: string }> = [], missing: string[] = []
  const pick = (category: string, condition: (row: SystemSummary) => boolean, score: (row: SystemSummary) => number = () => 0) => {
    const found = rows.filter(r => !used.has(r.system_id) && condition(r)).sort((a, b) => score(b) - score(a))[0]
    if (found) { selected.push({ systemId: found.system_id, category }); used.add(found.system_id) } else missing.push(category)
  }
  pick('high-priority', r => r.priority_score >= 70, r => r.priority_score)
  pick('no-contact', r => r.hpd_contact_count === 0)
  pick('institutional', r => (r.cms_institutional_facility_count ?? 0) > 0)
  pick('multi-tower', r => r.active_equipment > 1, r => r.active_equipment)
  pick('DWT-heavy', r => (r.nyc_building_water_signal_count ?? 0) > 0, r => r.nyc_building_water_signal_count ?? 0)
  pick('outer-borough', r => !!r.borough && r.borough.toUpperCase() !== 'MANHATTAN')
  pick('DOB-heavy', r => (r.dob_recent_activity_count ?? 0) > 0, r => r.dob_recent_activity_count ?? 0)
  for (const systemId of ['2000002585', '2000011123']) if (!used.has(systemId)) selected.push({ systemId, category: 'retained-baseline' })
  const results: unknown[] = []
  try {
    for (const { systemId, category } of selected) {
      await signInForProject(page, info.project.name, `#/account/${systemId}`)
      const panel = page.locator('.account-profile-page .detail-panel'), tabs = panel.locator('.account-mode-tabs')
      await expect(tabs).toBeVisible({ timeout: 120_000 })
      results.push({ systemId, category, mode: 'Summary', ...(await snapshot(page)) })
      await attach(page, info, `${category}-${systemId}-Summary`)
      await tabs.getByRole('button', { name: /^Evidence/ }).click()
      const workspace = panel.locator('.account-evidence-workspace')
      if (await workspace.count()) {
        const groups = workspace.locator(':scope > details')
        await expect(groups).toHaveCount(7, { timeout: 120_000 })
        for (const title of ['Project Activity', 'Property / Ownership']) await groups.filter({ has: page.locator('summary strong', { hasText: title }) }).locator(':scope > summary').click()
      }
      results.push({ systemId, category, mode: 'Evidence', ...(await snapshot(page)) })
      await attach(page, info, `${category}-${systemId}-Evidence`)
    }
    expect(selected.length).toBeGreaterThan(0)
  } finally {
    await info.attach('representative-account-review.json', { body: JSON.stringify({ selected, missing, results }, null, 2), contentType: 'application/json' })
  }
})
