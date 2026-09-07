import { expect, test } from './fixtures'

test.setTimeout(180_000)

type MetricMeasurement = {
  viewport: number
  body: number
  document: number
  gridClient: number
  gridScroll: number
  valueClient: number
  valueScroll: number
  valueText: string
  valueOverflowWrap: string
}

async function measure(page: import('@playwright/test').Page): Promise<MetricMeasurement> {
  return page.evaluate(() => {
    const grid = document.querySelector<HTMLElement>('.reference-metric-grid')
    const value = [...document.querySelectorAll<HTMLElement>('.reference-metric-grid strong')]
      .find(element => element.textContent?.includes('$6,475,380,412'))
    if (!grid || !value) throw new Error('Expected Opportunities metric grid/value not found')
    return {
      viewport: window.innerWidth,
      body: document.body.scrollWidth,
      document: document.documentElement.scrollWidth,
      gridClient: grid.clientWidth,
      gridScroll: grid.scrollWidth,
      valueClient: value.clientWidth,
      valueScroll: value.scrollWidth,
      valueText: value.textContent || '',
      valueOverflowWrap: getComputedStyle(value).overflowWrap,
    }
  })
}

async function navigateWorkspace(page: import('@playwright/test').Page, name: string) {
  await page.getByRole('button', { name: 'Open workspace menu', exact: true }).click()
  const menu = page.getByRole('dialog', { name: 'TowerSignal workspace menu', exact: true })
  await expect(menu).toBeVisible()
  await menu.getByRole('button', { name, exact: true }).click()
}

async function reachOpportunities(page: import('@playwright/test').Page) {
  await page.evaluate(() => { window.location.hash = '#/prospect' })
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible({ timeout: 90_000 })

  const acrisQuick = page.getByRole('button', { name: 'Recent ACRIS activity', exact: true })
  if (await acrisQuick.count() > 0) {
    await acrisQuick.click()
    await expect(page.locator('.account-table tbody tr').first()).toBeVisible({ timeout: 90_000 })
    await page.locator('.account-table tbody tr').first().click()
    const detail = page.getByLabel('Selected cooling tower detail')
    await expect(detail).toBeVisible({ timeout: 90_000 })
    await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
    await page.evaluate(() => { window.location.hash = '#/prospect' })
    await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible()
  }

  await page.getByRole('button', { name: 'Manhattan', exact: true }).click()
  await expect(page.locator('.account-table tbody tr').first()).toBeVisible()
  await page.getByRole('button', { name: 'OATH cases', exact: true }).click()
  await expect(page.locator('.account-table tbody tr').first()).toBeVisible()
  await page.locator('.account-table tbody tr').first().click()
  const detail = page.getByLabel('Selected cooling tower detail')
  await expect(detail).toBeVisible({ timeout: 90_000 })
  await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await page.waitForTimeout(750)
  await page.evaluate(() => { window.location.hash = '#/prospect' })
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible()

  for (const name of ['Monitor', 'Map', 'NYS Market', 'NYS Changes', 'Opportunities']) {
    await navigateWorkspace(page, name)
    const headingName = name === 'Opportunities' ? 'Opportunities workspace' : name === 'NYS Changes' ? 'NYS Changes' : name === 'NYS Market' ? 'NYS Market' : `${name} workspace`
    await expect(page.getByRole('heading', { name: headingName, exact: true })).toBeVisible({ timeout: 90_000 })
  }

  await expect(page.getByText('Current account timing opportunities', { exact: true })).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('.opportunity-table tbody tr').first()).toBeVisible({ timeout: 90_000 })
  await expect(page.getByText('$6,475,380,412', { exact: true })).toBeVisible({ timeout: 90_000 })
}

test('prove wrapping the long Opportunities metric fixes the exact iPhone overflow', async ({ page }, testInfo) => {
  await reachOpportunities(page)

  const before = await measure(page)
  console.log('OPPORTUNITIES_METRIC_WRAP_BEFORE', JSON.stringify(before))
  expect(before.body).toBe(409)
  expect(before.gridScroll).toBeGreaterThan(before.gridClient + 2)
  expect(before.valueScroll).toBeGreaterThan(before.valueClient + 2)

  await page.addStyleTag({ content: '@media(max-width:520px){.reference-metric-grid strong{overflow-wrap:anywhere}}' })
  await page.waitForTimeout(150)

  const after = await measure(page)
  console.log('OPPORTUNITIES_METRIC_WRAP_AFTER', JSON.stringify(after))
  await testInfo.attach('opportunities-metric-wrap-proof.json', {
    body: Buffer.from(JSON.stringify({ before, after }, null, 2)),
    contentType: 'application/json',
  })
  await testInfo.attach('opportunities-metric-wrap-after.png', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  })

  expect(after.body).toBeLessThanOrEqual(392)
  expect(after.document).toBeLessThanOrEqual(392)
  expect(after.gridScroll).toBeLessThanOrEqual(after.gridClient + 2)
  expect(after.valueScroll).toBeLessThanOrEqual(after.valueClient + 2)
})
