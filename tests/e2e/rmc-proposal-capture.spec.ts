import { expect, test, type Page, type Locator } from '@playwright/test'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'

const OUT = 'proposal-captures'
mkdirSync(OUT, { recursive: true })
test.use({ viewport: { width: 1280, height: 1600 }, deviceScaleFactor: 2 })

async function go(page: Page, hash: string) {
  await page.goto(`./${hash}`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
  await expect(page.locator('.app-shell')).toBeVisible({ timeout: 120_000 })
  await expect(page.locator('.loading-page')).toHaveCount(0, { timeout: 120_000 })
  await page.waitForTimeout(2000)
}
async function record(page: Page, name: string, target: Locator, state: string) {
  await expect(target).toHaveCount(1)
  await target.evaluate(element => window.scrollTo(0, Math.max(0, element.getBoundingClientRect().top + window.scrollY - 110)))
  await page.waitForTimeout(1000)
  const path = `${OUT}/${name}.png`
  await target.screenshot({ path, animations: 'disabled' })
  writeFileSync(`${OUT}/${name}.json`, JSON.stringify({
    captured_at: new Date().toISOString(), url: page.url(), state,
    viewport: page.viewportSize(), device_scale_factor: 2,
    screenshot_sha256: createHash('sha256').update(readFileSync(path)).digest('hex'),
    visible_text: await target.innerText(),
    application_scripts: await page.locator('script[src]').evaluateAll(elements => elements.map(e => (e as HTMLScriptElement).src)),
    controls: await page.locator('select').evaluateAll(elements => elements.map(e => ({ label: e.getAttribute('aria-label'), value: (e as HTMLSelectElement).value, text: (e as HTMLSelectElement).selectedOptions[0]?.textContent }))),
  }, null, 2))
}

test('territory priority concentration and a focused ranking', async ({ page }) => {
  test.setTimeout(180_000)
  await go(page, '#/prospect?borough=Manhattan&minScore=70')
  await record(page, '01-priority-prospect', page.locator('.prospect-reference-page'), 'Manhattan; minimum priority score 70; native default priority order; no data or styles modified')
  await record(page, '01a-priority-table', page.locator('.prospect-reference-page table').first(), 'Same filtered prospect view; native table for editorial crop')
  await go(page, '#/map?borough=Manhattan&minScore=70')
  const map = page.locator('.map-shell').first()
  await page.waitForTimeout(3500)
  for (let n = 1; n <= 3; n += 1) {
    await map.locator('.leaflet-control-zoom-in').click()
    await page.waitForTimeout(1700)
    if (n >= 2) await record(page, `01b-priority-map-zoom-${n}`, map, `Manhattan; minimum score 70; ${n} native zoom-in clicks from initial view; no marker selection`)
  }
})

test('CUNY overlapping account signals and observed firms', async ({ page }) => {
  test.setTimeout(180_000)
  await page.setViewportSize({ width: 1000, height: 1900 })
  await go(page, '#/account/2000012577')
  await expect(page.locator('.sales-precall-pack')).toBeVisible({ timeout: 120_000 })
  await record(page, '02-cuny-sales-summary', page.locator('.sales-precall-pack'), 'Account 2000012577; native Sales Pre-Call Pack; initial accordion state')
  await record(page, '02a-cuny-metrics', page.locator('.sales-pack-metrics'), 'Account 2000012577; native commercial timing, scale, owner-context and evidence cards')
  await record(page, '02b-cuny-before-call', page.locator('.sales-pack-panel').first(), 'Account 2000012577; before-call source-backed talking points')
  const firms = page.locator('.sales-precall-pack summary').filter({ hasText: 'Known firms / observed roles' }).first()
  await expect(firms).toBeVisible()
  await firms.click()
  await record(page, '02c-cuny-observed-firms', firms.locator('..'), 'Account 2000012577; Known firms / observed roles expanded using native control')
  writeFileSync(`${OUT}/02-cuny-page-context.json`, JSON.stringify({ url: page.url(), captured_at: new Date().toISOString(), text: await page.locator('.detail-panel').innerText() }, null, 2))
})

test('Metro Group selected property relationship and commercial footprint', async ({ page }) => {
  test.setTimeout(180_000)
  await page.setViewportSize({ width: 1440, height: 1700 })
  await go(page, '#/companies')
  const metro = page.locator('tr').filter({ hasText: /THE METRO GROUP INC/i }).first()
  await expect(metro).toBeVisible({ timeout: 120_000 })
  await metro.click()
  await expect(page.locator('.firm-profile-heading')).toBeVisible({ timeout: 120_000 })
  await record(page, '03-metro-heading', page.locator('.firm-profile-heading'), 'The Metro Group Inc; exact native company profile reached from the matching row')
  await record(page, '03a-metro-metrics', page.locator('.known-firm-profile-metrics'), 'Native company summary; source-reported public values are not revenue')
  const site = page.locator('.firm-prospect-sites-table tbody tr').filter({ hasText: /515 east 72nd street/i })
  await expect(site).toHaveCount(1)
  await site.click()
  await expect(page.locator('.firm-selected-prospect-site')).toBeVisible()
  await page.waitForTimeout(2500)
  const map = page.locator('.firm-site-map-shell')
  await record(page, '03b-metro-selected-site', page.locator('.firm-selected-prospect-site'), '515 east 72nd street selected; all relationship and borough filters; actual linked-account detail')
  await record(page, '03c-metro-selected-map-close', map, '515 east 72nd street selected; native selected-site zoom')
  for (let n = 0; n < 2; n += 1) {
    await map.locator('.leaflet-control-zoom-out').click()
    await page.waitForTimeout(1500)
  }
  await record(page, '03d-metro-selected-map-context', map, '515 east 72nd street remains selected; two native zoom-out clicks to show the wider company footprint')
  await record(page, '03e-metro-map-and-selected-site', page.locator('.firm-site-map-grid'), '515 east 72nd street selected alongside the wider observed company footprint; no empty selection panel')
  await record(page, '04-metro-commercial-footprint', page.locator('.company-evidence-card').filter({ hasText: 'Commercial footprint' }), 'Native commercial-footprint card, including buyer names and source-value qualifiers')
  const procurement = page.locator('.known-firm-profile-page .reference-table-card').filter({ has: page.getByText('Public procurement observations', { exact: true }) })
  await record(page, '04a-metro-procurement-evidence', procurement, 'The Metro Group Inc public procurement observations; native default order, no contract expiry inferred')
  writeFileSync(`${OUT}/03-metro-page-context.json`, JSON.stringify({ url: page.url(), captured_at: new Date().toISOString(), text: await page.locator('.known-firm-profile-page').innerText() }, null, 2))
})

test('Central Park South roof geometry and field-preparation evidence', async ({ page }) => {
  test.setTimeout(180_000)
  await page.setViewportSize({ width: 1000, height: 1900 })
  await go(page, '#/account/2000000855')
  await expect(page.locator('.technician-field-pack')).toBeVisible({ timeout: 120_000 })
  await record(page, '05-central-park-field-pack', page.locator('.technician-field-pack'), 'Account 2000000855; native Technician Field Pack; source limits preserved')
  await record(page, '05a-central-park-roof-summary', page.locator('.planimetric-summary'), 'Native mapped-footprint count and imagery-year qualifiers')
  await record(page, '05b-central-park-roof-map', page.locator('.planimetric-map-shell'), 'Native aerial, orange cooling-tower observations and building outline; default fit-to-bounds')
  await record(page, '05c-central-park-roof-legend', page.locator('.roof-map-legend'), 'Native legend and imagery-source label')
  writeFileSync(`${OUT}/05-central-park-page-context.json`, JSON.stringify({ url: page.url(), captured_at: new Date().toISOString(), text: await page.locator('.detail-panel').innerText() }, null, 2))
})
