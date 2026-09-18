import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

test.use({ trace: 'off' })
test.setTimeout(240_000)

test('Account navigation remains fully below the shared header after scrolling and resizing', async ({ page }, info) => {
  const measurements: unknown[] = []
  await signInForProject(page, info.project.name, '#/account/2000015564')
  const tabs = page.locator('.account-profile-page .account-mode-tabs')
  await expect(tabs).toBeVisible({ timeout: 120_000 })
  for (const width of [390, 768, 1280]) {
    await page.setViewportSize({ width, height: 844 })
    for (const mode of ['Summary', 'Sales', 'Field', 'Evidence', 'History']) {
      await tabs.getByRole('button', { name: new RegExp(`^${mode}`) }).click()
      await page.evaluate(() => window.scrollTo(0, Math.min(900, document.documentElement.scrollHeight - innerHeight)))
      const geometry = await page.evaluate(() => {
        const header = document.querySelector('.reference-top-nav')!.getBoundingClientRect()
        const tabs = document.querySelector('.account-profile-page .account-mode-tabs')!.getBoundingClientRect()
        return { headerBottom: header.bottom, tabTop: tabs.top, tabBottom: tabs.bottom,
          buttons: Array.from(document.querySelectorAll('.account-profile-page .account-mode-tabs button')).map(button => {
            const box = button.getBoundingClientRect()
            return { text: button.textContent, top: box.top, bottom: box.bottom }
          }) }
      })
      measurements.push({ width, mode, ...geometry })
      expect(geometry.tabTop, `${mode} tabs overlap the real header at ${width}px`).toBeGreaterThanOrEqual(geometry.headerBottom)
      for (const button of geometry.buttons) expect(button.top).toBeGreaterThanOrEqual(geometry.headerBottom)
      if (mode === 'Sales') await info.attach(`Sales-header-${width}px`, { body: await page.screenshot({ animations: 'disabled' }), contentType: 'image/png' })
    }
  }
  await info.attach('account-header-rectangles.json', { body: JSON.stringify(measurements, null, 2), contentType: 'application/json' })
})
