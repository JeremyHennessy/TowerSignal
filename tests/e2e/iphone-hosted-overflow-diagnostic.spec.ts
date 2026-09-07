import { expect, test } from './fixtures'

test.setTimeout(180_000)

type WidthSample = {
  label: string
  viewport: number
  body: number
  document: number
  root: number | null
  shell: number | null
  stage: number | null
  page: number | null
  opportunityScroll: number | null
  opportunityTable: number | null
  procurementScroll: number | null
  procurementTable: number | null
}

async function sampleWidths(page: import('@playwright/test').Page, label: string): Promise<WidthSample> {
  const sample = await page.evaluate(labelValue => {
    const width = (selector: string) => document.querySelector<HTMLElement>(selector)?.scrollWidth ?? null
    return {
      label: labelValue,
      viewport: window.innerWidth,
      body: document.body.scrollWidth,
      document: document.documentElement.scrollWidth,
      root: width('#root'),
      shell: width('main.app-shell'),
      stage: width('.main-stage'),
      page: width('.product-page'),
      opportunityScroll: width('.opportunity-table') === null ? null : document.querySelector<HTMLElement>('.opportunity-table')?.parentElement?.scrollWidth ?? null,
      opportunityTable: width('.opportunity-table'),
      procurementScroll: width('.procurement-table') === null ? null : document.querySelector<HTMLElement>('.procurement-table')?.parentElement?.scrollWidth ?? null,
      procurementTable: width('.procurement-table'),
    }
  }, label)
  console.log('OPPORTUNITIES_WIDTH_SAMPLE', JSON.stringify(sample))
  return sample
}

async function navigateWorkspace(page: import('@playwright/test').Page, name: string) {
  await page.getByRole('button', { name: 'Open workspace menu', exact: true }).click()
  const menu = page.getByRole('dialog', { name: 'TowerSignal workspace menu', exact: true })
  await expect(menu).toBeVisible()
  await menu.getByRole('button', { name, exact: true }).click()
}

test('sample Opportunities containment after the hosted iPhone navigation sequence', async ({ page }, testInfo) => {
  await page.evaluate(() => { window.location.hash = '#/prospect' })
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible({ timeout: 90_000 })

  await page.getByRole('button', { name: 'OATH cases', exact: true }).click()
  await expect(page.locator('.account-table tbody tr').first()).toBeVisible({ timeout: 90_000 })
  await page.locator('.account-table tbody tr').first().click()
  const detail = page.getByLabel('Selected cooling tower detail')
  await expect(detail).toBeVisible({ timeout: 90_000 })
  await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await page.waitForTimeout(750)
  await page.evaluate(() => { window.location.hash = '#/prospect' })
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible()

  await navigateWorkspace(page, 'Monitor')
  await expect(page.getByRole('heading', { name: 'Monitor workspace', exact: true })).toBeVisible()
  await expect(page.getByText(/new events/)).toBeVisible()
  await sampleWidths(page, 'monitor')

  await navigateWorkspace(page, 'Map')
  await expect(page.getByRole('heading', { name: 'Map workspace', exact: true })).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()
  await expect(page.getByText('Matching accounts', { exact: true })).toBeVisible()
  await sampleWidths(page, 'map')

  await navigateWorkspace(page, 'NYS Market')
  await expect(page.getByRole('heading', { name: 'NYS Market', exact: true })).toBeVisible()
  await expect(page.getByLabel('NYS registry filters')).toBeVisible()
  await expect(page.locator('.nys-table tbody tr').first()).toBeVisible()
  await expect(page.getByLabel('Filtered New York State cooling tower registry map')).toBeVisible()
  await expect(page.getByText(/matching NYS equipment records/)).toBeVisible()
  await sampleWidths(page, 'nys-market')

  await navigateWorkspace(page, 'NYS Changes')
  await expect(page.getByRole('heading', { name: 'NYS Changes', exact: true })).toBeVisible()
  await expect(page.getByText('NYS history collection began')).toBeVisible()
  await sampleWidths(page, 'nys-changes')

  await navigateWorkspace(page, 'Opportunities')
  await expect(page.getByRole('heading', { name: 'Opportunities workspace', exact: true })).toBeVisible()
  await expect(page.getByText('LIVE SOURCE DATA', { exact: true })).toBeVisible()
  const procurementSource = page.getByLabel('Procurement source')
  if (await procurementSource.isVisible().catch(() => false)) {
    await expect(procurementSource).toBeVisible()
  } else {
    await expect(page.getByText('Loading verified procurement intelligence…', { exact: true })).toBeVisible()
  }
  await expect(page.getByText('Current account timing opportunities', { exact: true })).toBeVisible()
  await expect(page.locator('.opportunity-table tbody tr').first()).toBeVisible()

  const samples: WidthSample[] = []
  for (const [label, delay] of [['immediate', 0], ['250ms', 250], ['1s', 750], ['2.5s', 1500], ['5s', 2500]] as const) {
    if (delay) await page.waitForTimeout(delay)
    samples.push(await sampleWidths(page, label))
  }

  await testInfo.attach('opportunities-width-samples.json', {
    body: Buffer.from(JSON.stringify(samples, null, 2)),
    contentType: 'application/json',
  })
  await testInfo.attach('opportunities-final.png', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  })

  const maxBody = Math.max(...samples.map(sample => sample.body))
  console.log('OPPORTUNITIES_MAX_BODY_WIDTH', maxBody)
  expect(maxBody).toBeLessThanOrEqual(392)
})
