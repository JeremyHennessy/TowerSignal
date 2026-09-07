import { expect, test } from './fixtures'

test.setTimeout(240_000)

type OverflowRecord = {
  selector: string
  tag: string
  classes: string
  text: string
  left: number
  right: number
  width: number
  scrollWidth: number
  clientWidth: number
  rightExcess: number
  intrinsicExcess: number
  display: string
  position: string
  widthCss: string
  minWidth: string
  maxWidth: string
  overflowX: string
  overflowWrap: string
  wordBreak: string
  whiteSpace: string
}

type OverflowSnapshot = {
  url: string
  viewportWidth: number
  bodyScrollWidth: number
  documentScrollWidth: number
  offenders: OverflowRecord[]
}

async function snapshot(page: import('@playwright/test').Page): Promise<OverflowSnapshot> {
  return page.evaluate(() => {
    const round = (value: number) => Math.round(value * 10) / 10
    const selectorFor = (element: Element): string => {
      const html = element as HTMLElement
      if (html.id) return `#${CSS.escape(html.id)}`
      const classes = [...html.classList].slice(0, 4).map(value => `.${CSS.escape(value)}`).join('')
      return `${html.tagName.toLowerCase()}${classes}`
    }
    const records = [...document.body.querySelectorAll<HTMLElement>('*')]
      .map(element => {
        const rect = element.getBoundingClientRect()
        const style = getComputedStyle(element)
        const rightExcess = rect.right - window.innerWidth
        const intrinsicExcess = element.scrollWidth - element.clientWidth
        return {
          selector: selectorFor(element),
          tag: element.tagName.toLowerCase(),
          classes: typeof element.className === 'string' ? element.className : '',
          text: (element.innerText || element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 180),
          left: round(rect.left),
          right: round(rect.right),
          width: round(rect.width),
          scrollWidth: element.scrollWidth,
          clientWidth: element.clientWidth,
          rightExcess: round(rightExcess),
          intrinsicExcess,
          display: style.display,
          position: style.position,
          widthCss: style.width,
          minWidth: style.minWidth,
          maxWidth: style.maxWidth,
          overflowX: style.overflowX,
          overflowWrap: style.overflowWrap,
          wordBreak: style.wordBreak,
          whiteSpace: style.whiteSpace,
        }
      })
      .filter(record => record.width > 0 && (record.rightExcess > 1 || record.intrinsicExcess > 2 || record.left < -1))
      .sort((a, b) => Math.max(b.rightExcess, b.intrinsicExcess) - Math.max(a.rightExcess, a.intrinsicExcess))
      .slice(0, 80)
    return {
      url: location.href,
      viewportWidth: window.innerWidth,
      bodyScrollWidth: document.body.scrollWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      offenders: records,
    }
  })
}

async function attachSnapshot(page: import('@playwright/test').Page, testInfo: import('@playwright/test').TestInfo, name: string) {
  const result = await snapshot(page)
  console.log(`HOSTED_OVERFLOW_DIAGNOSTIC ${name}`, JSON.stringify(result))
  await testInfo.attach(`${name}.json`, {
    body: Buffer.from(JSON.stringify(result, null, 2)),
    contentType: 'application/json',
  })
  await testInfo.attach(`${name}.png`, {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  })
  return result
}

async function navigateWorkspace(page: import('@playwright/test').Page, name: string) {
  await page.getByRole('button', { name: 'Open workspace menu', exact: true }).click()
  const menu = page.getByRole('dialog', { name: 'TowerSignal workspace menu', exact: true })
  await expect(menu).toBeVisible()
  await menu.getByRole('button', { name, exact: true }).click()
}

test('diagnose Opportunities overflow after the hosted navigation sequence', async ({ page }, testInfo) => {
  await page.evaluate(() => { window.location.hash = '#/prospect' })
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible({ timeout: 90_000 })
  await page.getByRole('button', { name: 'OATH cases', exact: true }).click()
  await expect(page.locator('.account-table tbody tr').first()).toBeVisible({ timeout: 90_000 })
  await page.locator('.account-table tbody tr').first().click()
  const detail = page.getByLabel('Selected cooling tower detail')
  await expect(detail).toBeVisible({ timeout: 90_000 })
  await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
  await page.evaluate(() => { window.location.hash = '#/prospect' })
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible()

  await navigateWorkspace(page, 'Monitor')
  await expect(page.getByRole('heading', { name: 'Monitor workspace', exact: true })).toBeVisible()
  await navigateWorkspace(page, 'Map')
  await expect(page.getByRole('heading', { name: 'Map workspace', exact: true })).toBeVisible()
  await navigateWorkspace(page, 'NYS Market')
  await expect(page.getByRole('heading', { name: 'NYS Market', exact: true })).toBeVisible()
  await navigateWorkspace(page, 'NYS Changes')
  await expect(page.getByRole('heading', { name: 'NYS Changes', exact: true })).toBeVisible()
  await navigateWorkspace(page, 'Opportunities')
  await expect(page.getByRole('heading', { name: 'Opportunities workspace', exact: true })).toBeVisible()
  await expect(page.getByText('Current account timing opportunities', { exact: true })).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('.opportunity-table tbody tr').first()).toBeVisible({ timeout: 90_000 })

  const immediate = await attachSnapshot(page, testInfo, 'opportunities-sequence-immediate')
  await page.waitForTimeout(2500)
  const settled = await attachSnapshot(page, testInfo, 'opportunities-sequence-settled')
  console.log('OPPORTUNITIES_SEQUENCE_WIDTHS', JSON.stringify({ immediate: immediate.bodyScrollWidth, settled: settled.bodyScrollWidth }))
})

test('prove history wrapping fixes the hosted roof-account document overflow', async ({ page }, testInfo) => {
  await page.evaluate(() => { window.location.hash = '#/account/2000015564' })
  const detail = page.getByLabel('Selected cooling tower detail')
  await expect(detail).toBeVisible({ timeout: 90_000 })
  await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
  await expect(page.locator('section.planimetric-section')).toHaveCount(1)
  await expect(page.locator('section.domestic-water-section')).toHaveCount(1)

  const before = await attachSnapshot(page, testInfo, 'roof-account-before-history-wrap')
  expect(before.bodyScrollWidth).toBeGreaterThan(before.viewportWidth + 2)

  await page.addStyleTag({ content: '.account-profile-page .history-timeline small{overflow-wrap:anywhere}' })
  await page.waitForTimeout(150)
  const after = await attachSnapshot(page, testInfo, 'roof-account-after-history-wrap')
  console.log('ROOF_HISTORY_WRAP_WIDTHS', JSON.stringify({ before: before.bodyScrollWidth, after: after.bodyScrollWidth }))

  expect(after.bodyScrollWidth).toBeLessThanOrEqual(after.viewportWidth + 2)
  expect(after.documentScrollWidth).toBeLessThanOrEqual(after.viewportWidth + 2)
})
