import { expect, test } from './fixtures'

test.setTimeout(180_000)

test('diagnose 1 PENN PLZ history-token overflow', async ({ page }, testInfo) => {
  await page.evaluate(() => { window.location.hash = '#/account/2000000237' })
  const detail = page.getByLabel('Selected cooling tower detail')
  await expect(detail).toBeVisible({ timeout: 90_000 })
  await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
  await expect(detail).toContainText('1 PENN PLZ')

  const diagnostics = await page.evaluate(() => {
    const viewportWidth = window.innerWidth
    const history = document.querySelector<HTMLElement>('.history-timeline')
    const historyValues = [...document.querySelectorAll<HTMLElement>('.history-timeline small')]
      .map((element, index) => {
        const rect = element.getBoundingClientRect()
        const style = getComputedStyle(element)
        return {
          index,
          top: Math.round(rect.top),
          left: Math.round(rect.left * 10) / 10,
          right: Math.round(rect.right * 10) / 10,
          width: Math.round(rect.width * 10) / 10,
          scrollWidth: element.scrollWidth,
          clientWidth: element.clientWidth,
          overflowX: style.overflowX,
          whiteSpace: style.whiteSpace,
          overflowWrap: style.overflowWrap,
          wordBreak: style.wordBreak,
          text: (element.textContent || '').trim(),
        }
      })
      .filter(item => item.right > viewportWidth + 1 || item.scrollWidth > item.clientWidth + 2)
      .sort((a, b) => Math.max(b.right - viewportWidth, b.scrollWidth - b.clientWidth) - Math.max(a.right - viewportWidth, a.scrollWidth - a.clientWidth))

    const historyRect = history?.getBoundingClientRect()
    return {
      viewportWidth,
      bodyScrollWidth: document.body.scrollWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      history: historyRect ? {
        left: Math.round(historyRect.left * 10) / 10,
        right: Math.round(historyRect.right * 10) / 10,
        width: Math.round(historyRect.width * 10) / 10,
        scrollWidth: history!.scrollWidth,
        clientWidth: history!.clientWidth,
      } : null,
      historyOffenders: historyValues.slice(0, 12),
    }
  })

  await testInfo.attach('history-overflow-diagnostics.json', {
    body: Buffer.from(JSON.stringify(diagnostics, null, 2)),
    contentType: 'application/json',
  })
  const topOffender = diagnostics.historyOffenders[0]
  if (topOffender) {
    await page.evaluate(top => window.scrollTo(0, Math.max(0, top - 160)), topOffender.top)
    await testInfo.attach('history-overflow.png', {
      body: await page.screenshot({ fullPage: false }),
      contentType: 'image/png',
    })
  }

  expect(diagnostics.historyOffenders.length, `History overflow hypothesis not confirmed:\n${JSON.stringify(diagnostics, null, 2)}`).toBeGreaterThan(0)
  expect(diagnostics.bodyScrollWidth, `Confirmed history overflow diagnostics:\n${JSON.stringify(diagnostics, null, 2)}`).toBeGreaterThan(diagnostics.viewportWidth + 2)
})
