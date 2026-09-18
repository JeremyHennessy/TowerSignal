import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

test.use({ trace: 'off' })
test.setTimeout(240_000)

test('225 Broadway keeps complete Account navigation above every mode and preserves source-backed content', async ({ page }, info) => {
  const errors: string[] = [], bulkRequests: string[] = [], measurements: unknown[] = []
  page.on('pageerror', error => errors.push(error.message))
  page.on('request', request => {
    if (/\/data\/procurement-(city-record|checkbook|nys-authorities|openbook-water|nycha-water)\.json(?:\?|$)/.test(request.url())) bulkRequests.push(request.url())
  })
  await signInForProject(page, info.project.name, '#/account/2000010998?view=sales')
  const panel = page.locator('.account-profile-page .detail-panel')
  const tabs = panel.locator('.account-mode-tabs')
  await expect(panel.getByRole('heading', { name: '225 BROADWAY', exact: true })).toBeVisible({ timeout: 90_000 })
  await expect(tabs).toBeVisible()
  const modes = [
    ['Sales', '.sales-precall-pack'], ['Summary', '.account-decision-summary'],
    ['Field', '.technician-field-pack'], ['Evidence', '.account-evidence-workspace'],
    ['History', '.account-unified-timeline'], ['Sales', '.sales-precall-pack'],
  ] as const
  for (const [mode, selector] of modes) {
    await tabs.getByRole('button', { name: new RegExp(`^${mode}`) }).click()
    await expect(tabs.getByRole('button', { name: new RegExp(`^${mode}`) })).toHaveAttribute('aria-pressed', 'true')
    const content = panel.locator(selector)
    await expect(content).toBeVisible({ timeout: 90_000 })
    await page.evaluate(() => window.scrollTo(0, 0))
    const navBox = await tabs.boundingBox(), contentBox = await content.boundingBox()
    expect(navBox).not.toBeNull(); expect(contentBox).not.toBeNull()
    expect(navBox!.y + navBox!.height, `${mode}: navigation must precede the actual content`).toBeLessThanOrEqual(contentBox!.y + 1)
    const viewport = page.viewportSize()!
    const buttonBoxes = await tabs.getByRole('button').evaluateAll(buttons => buttons.map(button => {
      const box = button.getBoundingClientRect()
      return { text: button.querySelector('strong')?.textContent, left: box.left, right: box.right }
    }))
    expect(buttonBoxes.map(box => box.text)).toEqual(['Summary', 'Sales', 'Field', 'Evidence', 'History'])
    for (const box of buttonBoxes) { expect(box.left).toBeGreaterThanOrEqual(-1); expect(box.right).toBeLessThanOrEqual(viewport.width + 1) }
    expect(await page.evaluate(() => document.body.scrollWidth)).toBeLessThanOrEqual(viewport.width + 1)
    if (mode === 'Evidence') {
      const groups = content.locator(':scope > details.account-evidence-group')
      await expect(groups).toHaveCount(7)
      for (const group of await groups.all()) {
        await group.locator(':scope > summary').click()
        await expect(group).toHaveAttribute('open', '')
      }
      await expect(content.getByText(/Loading source-backed account evidence/)).toHaveCount(0)
    }
    measurements.push({ mode, viewport, navBox, contentBox, buttonBoxes, url: page.url() })
    await page.evaluate(() => window.scrollTo(0, 0))
    await info.attach(`225-Broadway-${mode}-top`, { body: await page.screenshot({ animations: 'disabled' }), contentType: 'image/png' })
    await info.attach(`225-Broadway-${mode}-full`, { body: await page.screenshot({ fullPage: true, animations: 'disabled' }), contentType: 'image/png' })
    await page.evaluate(() => window.scrollTo(0, Math.min(650, document.documentElement.scrollHeight - innerHeight)))
    const sticky = await page.evaluate(() => {
      const header = document.querySelector('.reference-top-nav')!.getBoundingClientRect()
      const nav = document.querySelector('.account-profile-page .account-mode-tabs')!.getBoundingClientRect()
      return { headerBottom: header.bottom, navTop: nav.top }
    })
    expect(sticky.navTop).toBeGreaterThanOrEqual(sticky.headerBottom)
  }
  await expect(page).toHaveURL(/#\/account\/2000010998\?view=sales$/)
  expect(errors).toEqual([])
  expect(bulkRequests, 'An Account visit must never load citywide procurement bundles').toEqual([])
  await info.attach('225-Broadway-acceptance.json', { body: JSON.stringify({ errors, bulkRequests, measurements }, null, 2), contentType: 'application/json' })
})
