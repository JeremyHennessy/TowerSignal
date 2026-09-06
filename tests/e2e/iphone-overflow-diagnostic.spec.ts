import { expect, test } from './fixtures'

test.setTimeout(180_000)

test('diagnose 1 PENN PLZ iPhone horizontal overflow', async ({ page }, testInfo) => {
  await page.evaluate(() => { window.location.hash = '#/account/2000000237' })
  const detail = page.getByLabel('Selected cooling tower detail')
  await expect(detail).toBeVisible({ timeout: 90_000 })
  await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
  await expect(detail).toContainText('1 PENN PLZ')

  const diagnostics = await page.evaluate(() => {
    const viewportWidth = window.innerWidth
    const candidates = [...document.querySelectorAll<HTMLElement>('body *')]
      .map((element, index) => {
        const rect = element.getBoundingClientRect()
        return {
          element,
          index,
          top: Math.round(rect.top),
          bottom: Math.round(rect.bottom),
          left: Math.round(rect.left * 10) / 10,
          right: Math.round(rect.right * 10) / 10,
          width: Math.round(rect.width * 10) / 10,
          scrollWidth: element.scrollWidth,
          clientWidth: element.clientWidth,
        }
      })
      .filter(item => item.right > viewportWidth + 1 || item.left < -1 || item.scrollWidth > item.clientWidth + 2)
      .sort((a, b) => Math.max(b.right - viewportWidth, b.scrollWidth - b.clientWidth) - Math.max(a.right - viewportWidth, a.scrollWidth - a.clientWidth))
      .slice(0, 40)

    const describe = (item: typeof candidates[number]) => {
      const { element } = item
      const style = getComputedStyle(element)
      const className = typeof element.className === 'string' ? element.className : ''
      const parent = element.parentElement
      return {
        index: item.index,
        tag: element.tagName.toLowerCase(),
        id: element.id,
        className,
        parent: parent ? `${parent.tagName.toLowerCase()}${parent.id ? `#${parent.id}` : ''}${typeof parent.className === 'string' && parent.className ? `.${parent.className.trim().replace(/\s+/g, '.')}` : ''}` : null,
        top: item.top,
        bottom: item.bottom,
        left: item.left,
        right: item.right,
        width: item.width,
        scrollWidth: item.scrollWidth,
        clientWidth: item.clientWidth,
        minWidth: style.minWidth,
        widthStyle: style.width,
        overflowX: style.overflowX,
        whiteSpace: style.whiteSpace,
        display: style.display,
        text: (element.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 180),
      }
    }

    const detailElement = document.querySelector<HTMLElement>('.account-profile-page .detail-panel')!
    const detailRect = detailElement.getBoundingClientRect()
    return {
      viewportWidth,
      bodyScrollWidth: document.body.scrollWidth,
      documentScrollWidth: document.documentElement.scrollWidth,
      detail: {
        left: Math.round(detailRect.left * 10) / 10,
        right: Math.round(detailRect.right * 10) / 10,
        width: Math.round(detailRect.width * 10) / 10,
        scrollWidth: detailElement.scrollWidth,
        clientWidth: detailElement.clientWidth,
        display: getComputedStyle(detailElement).display,
      },
      offenders: candidates.map(describe),
    }
  })

  await testInfo.attach('overflow-diagnostics.json', {
    body: Buffer.from(JSON.stringify(diagnostics, null, 2)),
    contentType: 'application/json',
  })
  await testInfo.attach('1-penn-top.png', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  })

  for (const [index, offender] of diagnostics.offenders.slice(0, 5).entries()) {
    await page.evaluate(top => window.scrollTo(0, Math.max(0, top - 160)), offender.top)
    await testInfo.attach(`overflow-${index + 1}-${offender.tag}-${(offender.className || offender.id || 'element').replace(/[^a-zA-Z0-9_-]+/g, '-').slice(0, 50)}.png`, {
      body: await page.screenshot({ fullPage: false }),
      contentType: 'image/png',
    })
  }

  expect(diagnostics.bodyScrollWidth, `Horizontal overflow diagnostics:\n${JSON.stringify(diagnostics, null, 2)}`).toBeLessThanOrEqual(diagnostics.viewportWidth + 2)
})
