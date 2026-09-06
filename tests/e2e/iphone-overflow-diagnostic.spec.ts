import { expect, test } from './fixtures'

test.setTimeout(180_000)

type Snapshot = {
  viewportWidth: number
  bodyScrollWidth: number
  documentScrollWidth: number
  history: { width: number; scrollWidth: number; clientWidth: number } | null
  maxSmallScrollWidth: number
  maxSmallClientWidth: number
  maxSmallRight: number
}

async function measure(page: import('@playwright/test').Page): Promise<Snapshot> {
  return page.evaluate(() => {
    const history = document.querySelector<HTMLElement>('.history-timeline')
    const historyRect = history?.getBoundingClientRect()
    const smalls = [...document.querySelectorAll<HTMLElement>('.history-timeline small')]
    const round = (value: number) => Math.round(value * 10) / 10
    return {
      viewportWidth: window.innerWidth,
      bodyScrollWidth: document.body.scrollWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      history: historyRect ? {
        width: round(historyRect.width),
        scrollWidth: history!.scrollWidth,
        clientWidth: history!.clientWidth,
      } : null,
      maxSmallScrollWidth: smalls.length ? Math.max(...smalls.map(element => element.scrollWidth)) : 0,
      maxSmallClientWidth: smalls.length ? Math.max(...smalls.map(element => element.clientWidth)) : 0,
      maxSmallRight: smalls.length ? round(Math.max(...smalls.map(element => element.getBoundingClientRect().right))) : 0,
    }
  })
}

test('prove overflow-wrap:anywhere alone fixes 1 PENN PLZ history evidence overflow', async ({ page }, testInfo) => {
  await page.evaluate(() => { window.location.hash = '#/account/2000000237' })
  const detail = page.getByLabel('Selected cooling tower detail')
  await expect(detail).toBeVisible({ timeout: 90_000 })
  await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
  await expect(detail).toContainText('1 PENN PLZ')

  const before = await measure(page)
  expect(before.bodyScrollWidth, `Expected the known overflow before wrapping:\n${JSON.stringify(before, null, 2)}`).toBeGreaterThan(before.viewportWidth + 2)

  await page.addStyleTag({ content: '.account-profile-page .history-timeline small{overflow-wrap:anywhere}' })
  await page.waitForTimeout(100)
  const after = await measure(page)

  console.log('HISTORY_WRAP_DIAGNOSTIC', JSON.stringify({ before, after }))
  await testInfo.attach('history-wrap-before-after.json', {
    body: Buffer.from(JSON.stringify({ before, after }, null, 2)),
    contentType: 'application/json',
  })
  await testInfo.attach('history-wrap-after.png', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  })

  expect(after.bodyScrollWidth, `Wrapping did not eliminate document overflow:\n${JSON.stringify({ before, after }, null, 2)}`).toBeLessThanOrEqual(after.viewportWidth + 2)
  expect(after.documentScrollWidth).toBeLessThanOrEqual(after.viewportWidth + 2)
  expect(after.history?.scrollWidth ?? 0).toBeLessThanOrEqual((after.history?.clientWidth ?? 0) + 2)
  expect(after.maxSmallScrollWidth).toBeLessThanOrEqual(after.maxSmallClientWidth + 2)
  expect(after.maxSmallRight).toBeLessThanOrEqual(after.viewportWidth + 1)
})
