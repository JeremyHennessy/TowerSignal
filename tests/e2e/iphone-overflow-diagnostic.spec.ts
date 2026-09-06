import { expect, test } from './fixtures'

test.setTimeout(180_000)

type Offender = {
  tag: string
  className: string
  text: string
  left: number
  right: number
  width: number
  scrollWidth: number
  clientWidth: number
  display: string
  overflowX: string
  whiteSpace: string
  overflowWrap: string
  wordBreak: string
  minWidth: string
  maxWidth: string
}

type Snapshot = {
  viewportWidth: number
  bodyScrollWidth: number
  documentScrollWidth: number
  history: { width: number; scrollWidth: number; clientWidth: number } | null
  offenders: Offender[]
}

async function inspect(page: import('@playwright/test').Page): Promise<Snapshot> {
  return page.evaluate(() => {
    const history = document.querySelector<HTMLElement>('.history-timeline')
    const historyRect = history?.getBoundingClientRect()
    const viewportWidth = window.innerWidth
    const round = (value: number) => Math.round(value * 10) / 10
    const offenders = history
      ? [...history.querySelectorAll<HTMLElement>('*')]
        .map(element => {
          const rect = element.getBoundingClientRect()
          const style = getComputedStyle(element)
          return {
            tag: element.tagName.toLowerCase(),
            className: element.className,
            text: (element.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 240),
            left: round(rect.left),
            right: round(rect.right),
            width: round(rect.width),
            scrollWidth: element.scrollWidth,
            clientWidth: element.clientWidth,
            display: style.display,
            overflowX: style.overflowX,
            whiteSpace: style.whiteSpace,
            overflowWrap: style.overflowWrap,
            wordBreak: style.wordBreak,
            minWidth: style.minWidth,
            maxWidth: style.maxWidth,
          }
        })
        .filter(item => item.right > viewportWidth + 1 || item.scrollWidth > item.clientWidth + 2)
        .sort((a, b) => Math.max(b.right - viewportWidth, b.scrollWidth - b.clientWidth) - Math.max(a.right - viewportWidth, a.scrollWidth - a.clientWidth))
      : []

    return {
      viewportWidth,
      bodyScrollWidth: document.body.scrollWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      history: historyRect ? {
        width: round(historyRect.width),
        scrollWidth: history!.scrollWidth,
        clientWidth: history!.clientWidth,
      } : null,
      offenders,
    }
  })
}

test('identify remaining 1 PENN PLZ history overflow after grid-track constraint', async ({ page }, testInfo) => {
  await page.evaluate(() => { window.location.hash = '#/account/2000000237' })
  const detail = page.getByLabel('Selected cooling tower detail')
  await expect(detail).toBeVisible({ timeout: 90_000 })
  await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
  await expect(detail).toContainText('1 PENN PLZ')

  const before = await inspect(page)
  expect(before.bodyScrollWidth, `Expected the known overflow before diagnostic constraint:\n${JSON.stringify(before, null, 2)}`).toBeGreaterThan(before.viewportWidth + 2)

  await page.addStyleTag({ content: '.account-profile-page .history-timeline{grid-template-columns:minmax(0,1fr)}' })
  await page.waitForTimeout(100)
  const afterGridTrack = await inspect(page)

  await testInfo.attach('history-overflow-descendants.json', {
    body: Buffer.from(JSON.stringify({ before, afterGridTrack }, null, 2)),
    contentType: 'application/json',
  })
  await testInfo.attach('history-overflow-after-grid-track.png', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  })

  // Observation-only diagnostic. The previous run proved the grid track alone
  // is insufficient; this run records the exact descendant(s) still overflowing.
  expect(afterGridTrack.offenders.length).toBeGreaterThan(0)
})
