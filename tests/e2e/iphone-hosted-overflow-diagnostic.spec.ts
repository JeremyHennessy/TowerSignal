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
}

type Offender = {
  selector: string
  tag: string
  classes: string
  text: string
  left: number
  right: number
  width: number
  scrollWidth: number
  clientWidth: number
  overflowX: string
  position: string
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
    }
  }, label)
  console.log('OPPORTUNITIES_WIDTH_SAMPLE', JSON.stringify(sample))
  return sample
}

async function captureOffenders(page: import('@playwright/test').Page): Promise<Offender[]> {
  const offenders = await page.evaluate(() => {
    const viewport = window.innerWidth
    const selectorFor = (element: HTMLElement) => {
      if (element.id) return `#${element.id}`
      const classes = [...element.classList].slice(0, 5).map(value => `.${value}`).join('')
      return `${element.tagName.toLowerCase()}${classes}`
    }
    const candidates = [...document.querySelectorAll<HTMLElement>(
      '#root, main, .main-stage, .product-page, section, article, aside, header, footer, nav, form, fieldset, label, input, select, button, [class*="opportun"], [class*="procure"], [class*="filter"], [class*="toolbar"], [class*="header"], [class*="shell"], [class*="panel"], [class*="card"], [class*="grid"], [class*="row"], [class*="actions"]'
    )]
    const unique = [...new Set(candidates)]
    return unique.map(element => {
      const rect = element.getBoundingClientRect()
      const style = getComputedStyle(element)
      return {
        selector: selectorFor(element),
        tag: element.tagName.toLowerCase(),
        classes: element.className || '',
        text: (element.innerText || element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 160),
        left: Math.round(rect.left * 10) / 10,
        right: Math.round(rect.right * 10) / 10,
        width: Math.round(rect.width * 10) / 10,
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
        overflowX: style.overflowX,
        position: style.position,
      }
    }).filter(record => {
      const intentionalScroll = record.overflowX === 'auto' || record.overflowX === 'scroll' || record.overflowX === 'hidden' || record.overflowX === 'clip'
      return record.right > viewport + 1 || record.left < -1 || (!intentionalScroll && record.scrollWidth > record.clientWidth + 2)
    }).sort((a, b) => Math.max(b.right - viewport, b.scrollWidth - b.clientWidth) - Math.max(a.right - viewport, a.scrollWidth - a.clientWidth)).slice(0, 80)
  })
  console.log('OPPORTUNITIES_OFFENDERS', JSON.stringify(offenders))
  return offenders
}

async function navigateWorkspace(page: import('@playwright/test').Page, name: string) {
  await page.getByRole('button', { name: 'Open workspace menu', exact: true }).click()
  const menu = page.getByRole('dialog', { name: 'TowerSignal workspace menu', exact: true })
  await expect(menu).toBeVisible()
  await menu.getByRole('button', { name, exact: true }).click()
}

test('identify exact Opportunities overflow after the official hosted iPhone sequence', async ({ page }, testInfo) => {
  await page.evaluate(() => { window.location.hash = '#/prospect' })
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible({ timeout: 90_000 })

  const acrisQuick = page.getByRole('button', { name: 'Recent ACRIS activity', exact: true })
  const acrisAvailable = await acrisQuick.count() > 0
  if (acrisAvailable) {
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

  await navigateWorkspace(page, 'Monitor')
  await expect(page.getByRole('heading', { name: 'Monitor workspace', exact: true })).toBeVisible()
  await sampleWidths(page, 'monitor')

  await navigateWorkspace(page, 'Map')
  await expect(page.getByRole('heading', { name: 'Map workspace', exact: true })).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()
  await sampleWidths(page, 'map')

  await navigateWorkspace(page, 'NYS Market')
  await expect(page.getByRole('heading', { name: 'NYS Market', exact: true })).toBeVisible()
  await expect(page.locator('.nys-table tbody tr').first()).toBeVisible()
  await sampleWidths(page, 'nys-market')

  await navigateWorkspace(page, 'NYS Changes')
  await expect(page.getByRole('heading', { name: 'NYS Changes', exact: true })).toBeVisible()
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
  const offenders = await captureOffenders(page)

  await testInfo.attach('opportunities-width-samples.json', {
    body: Buffer.from(JSON.stringify(samples, null, 2)),
    contentType: 'application/json',
  })
  await testInfo.attach('opportunities-offenders.json', {
    body: Buffer.from(JSON.stringify(offenders, null, 2)),
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
