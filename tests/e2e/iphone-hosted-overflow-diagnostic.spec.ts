import { expect, test } from './fixtures'

test.setTimeout(180_000)

type ElementMeasurement = {
  name: string
  text: string
  left: number
  right: number
  width: number
  clientWidth: number
  scrollWidth: number
  minWidth: string
  widthCss: string
  display: string
  overflowX: string
  overflowWrap: string
  wordBreak: string
  whiteSpace: string
  flex: string
}

type MetricMeasurement = {
  viewport: number
  body: number
  document: number
  gridClient: number
  gridScroll: number
  elements: ElementMeasurement[]
}

async function measure(page: import('@playwright/test').Page): Promise<MetricMeasurement> {
  return page.evaluate(() => {
    const grid = document.querySelector<HTMLElement>('.reference-metric-grid')
    const value = [...document.querySelectorAll<HTMLElement>('.reference-metric-grid strong')]
      .find(element => element.textContent?.includes('$6,475,380,412'))
    const content = value?.parentElement as HTMLElement | null
    const article = content?.parentElement as HTMLElement | null
    const label = content?.querySelector<HTMLElement>('small') ?? null
    const subtitle = content?.querySelector<HTMLElement>('span') ?? null
    if (!grid || !value || !content || !article || !label || !subtitle) throw new Error('Expected Opportunities metric card not found')

    const record = (name: string, element: HTMLElement): ElementMeasurement => {
      const rect = element.getBoundingClientRect()
      const style = getComputedStyle(element)
      return {
        name,
        text: (element.textContent || '').replace(/\s+/g, ' ').trim(),
        left: Math.round(rect.left * 10) / 10,
        right: Math.round(rect.right * 10) / 10,
        width: Math.round(rect.width * 10) / 10,
        clientWidth: element.clientWidth,
        scrollWidth: element.scrollWidth,
        minWidth: style.minWidth,
        widthCss: style.width,
        display: style.display,
        overflowX: style.overflowX,
        overflowWrap: style.overflowWrap,
        wordBreak: style.wordBreak,
        whiteSpace: style.whiteSpace,
        flex: style.flex,
      }
    }

    return {
      viewport: window.innerWidth,
      body: document.body.scrollWidth,
      document: document.documentElement.scrollWidth,
      gridClient: grid.clientWidth,
      gridScroll: grid.scrollWidth,
      elements: [
        record('article', article),
        record('content', content),
        record('label', label),
        record('value', value),
        record('subtitle', subtitle),
      ],
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

test('measure the exact overflowing Opportunities metric card on iPhone', async ({ page }, testInfo) => {
  await reachOpportunities(page)
  const measurement = await measure(page)
  console.log('OPPORTUNITIES_METRIC_CARD_MEASUREMENT', JSON.stringify(measurement))
  await testInfo.attach('opportunities-metric-card-measurement.json', {
    body: Buffer.from(JSON.stringify(measurement, null, 2)),
    contentType: 'application/json',
  })
  await testInfo.attach('opportunities-metric-card.png', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  })

  expect(measurement.body).toBe(409)
  expect(measurement.gridScroll).toBeGreaterThan(measurement.gridClient + 2)
})
