import { expect, test } from './fixtures'

test.setTimeout(180_000)

type WidthSnapshot = {
  viewportWidth: number
  bodyScrollWidth: number
  documentScrollWidth: number
  history: { width: number; scrollWidth: number; clientWidth: number } | null
  maxHistoryValueRight: number | null
  maxHistoryValueWidth: number | null
}

async function measure(page: import('@playwright/test').Page): Promise<WidthSnapshot> {
  return page.evaluate(() => {
    const history = document.querySelector<HTMLElement>('.history-timeline')
    const rects = [...document.querySelectorAll<HTMLElement>('.history-timeline small')]
      .map(element => element.getBoundingClientRect())
    const historyRect = history?.getBoundingClientRect()
    return {
      viewportWidth: window.innerWidth,
      bodyScrollWidth: document.body.scrollWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      history: historyRect ? {
        width: Math.round(historyRect.width * 10) / 10,
        scrollWidth: history!.scrollWidth,
        clientWidth: history!.clientWidth,
      } : null,
      maxHistoryValueRight: rects.length ? Math.round(Math.max(...rects.map(rect => rect.right)) * 10) / 10 : null,
      maxHistoryValueWidth: rects.length ? Math.round(Math.max(...rects.map(rect => rect.width)) * 10) / 10 : null,
    }
  })
}

test('prove minmax(0,1fr) fixes 1 PENN PLZ history-token overflow', async ({ page }, testInfo) => {
  await page.evaluate(() => { window.location.hash = '#/account/2000000237' })
  const detail = page.getByLabel('Selected cooling tower detail')
  await expect(detail).toBeVisible({ timeout: 90_000 })
  await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
  await expect(detail).toContainText('1 PENN PLZ')

  const before = await measure(page)
  expect(before.bodyScrollWidth, `Expected the known history overflow before injection:\n${JSON.stringify(before, null, 2)}`).toBeGreaterThan(before.viewportWidth + 2)

  await page.addStyleTag({ content: '.account-profile-page .history-timeline{grid-template-columns:minmax(0,1fr)}' })
  await page.waitForTimeout(100)

  const after = await measure(page)
  await testInfo.attach('history-grid-track-before-after.json', {
    body: Buffer.from(JSON.stringify({ before, after }, null, 2)),
    contentType: 'application/json',
  })
  await testInfo.attach('history-grid-track-after.png', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  })

  expect(after.bodyScrollWidth, `Minimal grid-track rule did not eliminate document overflow:\n${JSON.stringify({ before, after }, null, 2)}`).toBeLessThanOrEqual(after.viewportWidth + 2)
  expect(after.documentScrollWidth).toBeLessThanOrEqual(after.viewportWidth + 2)
  expect(after.history?.scrollWidth ?? 0).toBeLessThanOrEqual((after.history?.clientWidth ?? 0) + 2)
  expect(after.maxHistoryValueRight ?? 0).toBeLessThanOrEqual(after.viewportWidth + 1)
})
