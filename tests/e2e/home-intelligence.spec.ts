import type { Locator, Page, TestInfo } from '@playwright/test'
import { expect, test } from './fixtures'
import { expectContained, expectAccountDetailHydrated } from './iphone.helpers'

async function captureHome(page: Page, panel: Locator, testInfo: TestInfo, name: string) {
  // Capture the actual full document from its top. Element screenshots scroll
  // tall panels and otherwise bake the fixed navigation into the panel's middle.
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: 'instant' }))
  await page.waitForFunction(() => window.scrollY === 0)
  const bounds = await panel.boundingBox()
  await testInfo.attach(name, { body: await page.screenshot({ fullPage: true, scale: 'css', animations: 'disabled' }), contentType: 'image/png' })
  await testInfo.attach(`${name}-panel-bounds`, { body: Buffer.from(JSON.stringify(bounds)), contentType: 'application/json' })
}

test('Home intelligence is searchable, paginated, responsive and linked to named-building accounts', async ({ page }, testInfo) => {
  testInfo.setTimeout(120_000)
  await page.evaluate(() => { window.location.hash = '#/home' })
  const contracts = await page.evaluate(async () => {
    const assets = [
      ['legionella-alerts.json', 'LEGIONELLA_PUBLIC_HEALTH_ALERTS'],
      ['legionella-property-matches.json', 'LEGIONELLA_PROPERTY_MATCHES'],
    ] as const
    return Promise.all(assets.map(async ([name, expectedDomain]) => {
      const response = await fetch(`data/${name}?home-contract=${Date.now()}`, { cache: 'no-store' })
      const payload = response.ok ? await response.json() as { domain?: string; items?: unknown[]; matched_observations?: unknown[] } : null
      return { name, expectedDomain, status: response.status, domain: payload?.domain ?? null,
        rowCount: Array.isArray(payload?.items) ? payload.items.length : Array.isArray(payload?.matched_observations) ? payload.matched_observations.length : 0 }
    }))
  })
  for (const contract of contracts) {
    expect(contract.status, `${contract.name} should be served by the deployed runtime`).toBe(200)
    expect(contract.domain, `${contract.name} should retain its production contract`).toBe(contract.expectedDomain)
    expect(contract.rowCount, `${contract.name} should contain retained official evidence`).toBeGreaterThan(0)
  }

  const panel = page.getByRole('region', { name: 'Legionnaires official intelligence' })
  await expect(panel).toBeVisible()
  await expect(panel.locator('.li-headline').first()).toBeVisible()
  await expect(panel.getByRole('button', { name: /[1-9].*buildings?/ }).first()).toBeVisible()
  await expect(panel.locator('.li-notice')).toHaveCount(0)
  await expectContained(page)
  await captureHome(page, panel, testInfo, 'home-intelligence-overview')

  const firstTitle = await panel.locator('.li-headline').first().innerText()
  await panel.getByRole('button', { name: 'Next intelligence page' }).click()
  await expect(panel.locator('.li-headline').first()).not.toHaveText(firstTitle)
  await panel.getByRole('button', { name: 'Previous intelligence page' }).click()
  await expect(panel.locator('.li-headline').first()).toHaveText(firstTitle)
  await panel.getByLabel('Search official intelligence').fill('no-such-publication-zzzz')
  await expect(panel.getByText('No publications match this view.')).toBeVisible()
  await panel.getByRole('button', { name: 'Show all updates' }).click()

  await panel.getByRole('button', { name: 'Linked buildings', exact: true }).click()
  await expect(panel.getByRole('button', { name: 'Linked buildings', exact: true })).toHaveAttribute('aria-pressed', 'true')
  const expand = panel.locator('.li-match-button').first()
  await expand.click()
  await expect(expand).toHaveAttribute('aria-expanded', 'true')
  await expect(panel.getByRole('heading', { name: 'Buildings connected to this update' })).toBeVisible()
  await expect(panel.getByText('Building-level match', { exact: true })).toBeVisible()
  await expect(panel.locator('.li-boundary')).toContainText('does not identify which system tested positive')
  const link = panel.getByRole('link', { name: /^Open tower account / }).first()
  const href = await link.getAttribute('href')
  expect(href).toMatch(/^#\/account\/\d+$/)
  await expectContained(page)
  await captureHome(page, panel, testInfo, 'home-linked-building-evidence')
  await link.click()
  await expectAccountDetailHydrated(page)
  await expect(page).toHaveURL(new RegExp(href!.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '$'))

  await page.evaluate(() => { window.location.hash = '#/home' })
  await expect(panel.locator('.li-headline').first()).toBeVisible()
  await panel.getByRole('button', { name: 'Reference library', exact: true }).click()
  await expect(panel.getByRole('button', { name: 'Reference library', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await expect(panel.locator('.li-headline').first()).toBeVisible()
  await expectContained(page)
  await captureHome(page, panel, testInfo, 'home-reference-library')
  await page.evaluate(() => { window.location.hash = '#/prospect' })
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible()
  await expect(panel).toHaveCount(0)
  await expect(page.locator('.account-table tbody tr').first()).toBeVisible()
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: 'instant' }))
  await testInfo.attach('prospect-without-news-panel', { body: await page.screenshot({ scale: 'css', animations: 'disabled' }), contentType: 'image/png' })
})
