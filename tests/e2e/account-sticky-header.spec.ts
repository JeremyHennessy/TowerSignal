import { devices, expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

test.use({ trace: 'off' })
test.setTimeout(240_000)

test('Account navigation clears the real header at phone tablet and desktop widths', async ({ page, browser }, info) => {
  const measurements: unknown[] = []
  const mobile = info.project.name.includes('iphone')
  if (!mobile) await signInForProject(page, info.project.name, '#/account/2000015564')
  for (const width of [390, 768, 1280]) {
    // Independent static HTML proof 35369659415 reproduces WebKit's corrupted
    // mobile scale after live 390->768 resizing (198px at scale 1.969). A fresh
    // context has the requested width and scale 1. Keep every width/mode and
    // rectangle assertion; retain actual live resizing in desktop Chromium.
    const current = mobile ? await browser.newPage({
      ...devices['iPhone 13'], baseURL: info.project.use.baseURL,
      storageState: info.project.use.storageState,
      viewport: { width, height: 844 }, screen: { width, height: 844 },
    }) : page
    try {
      if (mobile) await signInForProject(current, info.project.name, '#/account/2000015564')
      else await current.setViewportSize({ width, height: 844 })
      const tabs = current.locator('.account-profile-page .account-mode-tabs')
      await expect(tabs).toBeVisible({ timeout: 120_000 })
      for (const mode of ['Summary', 'Sales', 'Field', 'Evidence', 'History']) {
        await tabs.getByRole('button', { name: new RegExp(`^${mode}`) }).click()
        await current.evaluate(() => window.scrollTo(0, Math.min(900, document.documentElement.scrollHeight - innerHeight)))
        const geometry = await current.evaluate(() => {
          const header = document.querySelector('.reference-top-nav')!.getBoundingClientRect()
          const tabs = document.querySelector('.account-profile-page .account-mode-tabs')!.getBoundingClientRect()
          return { headerBottom: header.bottom, tabTop: tabs.top, tabBottom: tabs.bottom,
            actualViewportWidth: innerWidth, viewportScale: visualViewport?.scale ?? 1,
            buttons: Array.from(document.querySelectorAll('.account-profile-page .account-mode-tabs button')).map(button => {
              const box = button.getBoundingClientRect()
              return { text: button.textContent, top: box.top, bottom: box.bottom }
            }) }
        })
        measurements.push({ width, mode, ...geometry })
        expect(geometry.actualViewportWidth, 'Test must use its stated CSS viewport').toBe(width)
        expect(geometry.viewportScale).toBeCloseTo(1, 2)
        expect(geometry.tabTop, `${mode} tabs overlap the real header at ${width}px`).toBeGreaterThanOrEqual(geometry.headerBottom)
        for (const button of geometry.buttons) expect(button.top).toBeGreaterThanOrEqual(geometry.headerBottom)
        if (mode === 'Sales') await info.attach(`Sales-header-${width}px`, { body: await current.screenshot({ animations: 'disabled' }), contentType: 'image/png' })
      }
    } finally {
      await info.attach(`account-header-rectangles-${width}.json`, { body: JSON.stringify(measurements, null, 2), contentType: 'application/json' })
      if (mobile) await current.close()
    }
  }
})
