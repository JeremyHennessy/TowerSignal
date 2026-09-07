import { expect, test } from './fixtures'

test.setTimeout(180_000)

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
          classes: element.className || '',
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

test('diagnose hosted Opportunities iPhone overflow', async ({ page }, testInfo) => {
  await page.evaluate(() => { window.location.hash = '#/opportunities' })
  await expect(page.getByRole('heading', { name: 'Opportunities workspace', exact: true })).toBeVisible({ timeout: 90_000 })
  await expect(page.getByText('Current account timing opportunities', { exact: true })).toBeVisible({ timeout: 90_000 })
  await expect(page.locator('.opportunity-table tbody tr').first()).toBeVisible({ timeout: 90_000 })
  const result = await attachSnapshot(page, testInfo, 'opportunities-overflow')
  expect(result.bodyScrollWidth).toBeGreaterThan(result.viewportWidth + 2)
})

test('diagnose hosted roof-account iPhone overflow', async ({ page }, testInfo) => {
  await page.evaluate(() => { window.location.hash = '#/account/2000015564' })
  const detail = page.getByLabel('Selected cooling tower detail')
  await expect(detail).toBeVisible({ timeout: 90_000 })
  await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
  await expect(page.locator('section.planimetric-section')).toHaveCount(1)
  await expect(page.locator('section.domestic-water-section')).toHaveCount(1)
  const result = await attachSnapshot(page, testInfo, 'roof-account-overflow')
  expect(result.bodyScrollWidth).toBeGreaterThan(result.viewportWidth + 2)
})
