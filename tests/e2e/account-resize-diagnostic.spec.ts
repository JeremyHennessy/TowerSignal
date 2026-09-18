import { expect, test, type Page } from '@playwright/test'
import { signInForProject } from './auth.helpers'

test.use({ trace: 'off' })
test.setTimeout(180_000)
async function measure(page: Page, phase: string) {
  return page.evaluate(phase => {
    const sel = ['.reference-top-nav', '.account-profile-page', '.detail-panel', '.account-mode-tabs', '.account-mode-tabs button', '.account-unified-timeline']
    return { phase, url: location.href, innerWidth, innerHeight, outerWidth, outerHeight, scrollX, scrollY,
      screen: { width: screen.width, height: screen.height },
      viewport: visualViewport && { width: visualViewport.width, height: visualViewport.height, offsetTop: visualViewport.offsetTop, offsetLeft: visualViewport.offsetLeft, pageTop: visualViewport.pageTop, pageLeft: visualViewport.pageLeft, scale: visualViewport.scale },
      html: { width: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight },
      elements: sel.flatMap(selector => Array.from(document.querySelectorAll(selector)).map(el => {
        const b = el.getBoundingClientRect(), s = getComputedStyle(el)
        return { selector, text: el.tagName === 'BUTTON' ? el.textContent : '', top: b.top, left: b.left, right: b.right, bottom: b.bottom, width: b.width, height: b.height,
          position: s.position, display: s.display, overflow: s.overflow, zoom: s.zoom, transform: s.transform, scrollLeft: el.scrollLeft, scrollTop: el.scrollTop,
          clientWidth: el.clientWidth, scrollWidth: el.scrollWidth, scrollHeight: el.scrollHeight }
      })) }
  }, phase)
}

test('diagnose original Account resize path without forced clicks or production changes', async ({ page }, info) => {
  const states: unknown[] = []
  try {
    await signInForProject(page, info.project.name, '#/account/2000015564')
    const tabs = page.locator('.account-profile-page .account-mode-tabs')
    await expect(tabs).toBeVisible({ timeout: 60_000 })
    for (const width of [390, 768, 1280]) {
      states.push(await measure(page, `before-resize-${width}`))
      await page.setViewportSize({ width, height: 844 })
      states.push(await measure(page, `after-resize-${width}`))
      for (const mode of ['Summary', 'Sales', 'Field', 'Evidence', 'History']) {
        states.push(await measure(page, `before-click-${width}-${mode}`))
        await tabs.getByRole('button', { name: new RegExp(`^${mode}`) }).click({ timeout: 10_000 })
        await page.evaluate(() => window.scrollTo(0, Math.min(900, document.documentElement.scrollHeight - innerHeight)))
        states.push(await measure(page, `after-scroll-${width}-${mode}`))
      }
    }
  } finally {
    states.push(await measure(page, 'final-state'))
    await info.attach('resize-diagnostic.json', { body: JSON.stringify(states, null, 2), contentType: 'application/json' })
    await info.attach('resize-final', { body: await page.screenshot({ animations: 'disabled' }), contentType: 'image/png' })
  }
})
