import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

test.use({ trace: 'off' })
test.setTimeout(180_000)

test('Account Evidence loads bounded account projection, never global procurement payloads', async ({ page }, info) => {
  const globalRequests: string[] = [], projectionResponses: Array<{ url: string; status: number; bytes: number }> = []
  const pending: Promise<void>[] = []
  page.on('request', request => {
    if (/\/data\/procurement-(city-record|checkbook|nys-authorities|openbook-water|nycha-water)\.json/.test(request.url())) globalRequests.push(request.url())
  })
  page.on('response', response => {
    if (!response.url().includes('/data/account-procurement/')) return
    pending.push((async () => projectionResponses.push({ url: response.url(), status: response.status(), bytes: (await response.body()).length }))().then(() => {}))
  })
  await signInForProject(page, info.project.name, '#/account/2000015564?view=evidence')
  const workspace = page.locator('.account-evidence-workspace')
  await expect(workspace.locator(':scope > details')).toHaveCount(7, { timeout: 120_000 })
  const commercial = workspace.locator(':scope > details').filter({ has: page.locator('summary strong', { hasText: 'Procurement / Commercial' }) })
  await commercial.locator(':scope > summary').click()
  await expect(commercial.getByText(/Showing \d+ of \d+ explicitly linked procurement records/)).toBeVisible({ timeout: 60_000 })
  await Promise.all(pending)
  expect(globalRequests).toEqual([])
  expect(projectionResponses.length).toBeGreaterThan(0)
  for (const response of projectionResponses) {
    expect(response.status).toBe(200)
    expect(response.bytes).toBeLessThanOrEqual(response.url.endsWith('/index.json') ? 64 * 1024 : 256 * 1024)
  }
  await info.attach('account-procurement-network.json', { body: JSON.stringify({ globalRequests, projectionResponses }, null, 2), contentType: 'application/json' })
  await info.attach('Account-Evidence-bounded', { body: await page.screenshot({ animations: 'disabled' }), contentType: 'image/png' })
})

test('missing Account procurement projection stays unavailable without bulk fallback', async ({ page }, info) => {
  const bulk: string[] = []
  page.on('request', request => { if (/\/data\/procurement-/.test(request.url())) bulk.push(request.url()) })
  await signInForProject(page, info.project.name, '#/account/2000015564')
  await expect(page.locator('.account-mode-tabs')).toBeVisible({ timeout: 120_000 })
  await page.route('**/data/account-procurement/**/index.json', route => route.fulfill({ status: 404, body: 'Projection unavailable test' }))
  await page.locator('.account-mode-tabs').getByRole('button', { name: /^Evidence/ }).click()
  const commercial = page.locator('.account-evidence-workspace > details').filter({ has: page.locator('summary strong', { hasText: 'Procurement / Commercial' }) })
  await commercial.locator(':scope > summary').click()
  await expect(commercial.getByText('Procurement evidence unavailable.', { exact: true })).toBeVisible()
  await expect(commercial).toContainText('No zero-contract or no-vendor conclusion is inferred.')
  await expect(commercial.getByText(/Showing 0 of 0/)).toHaveCount(0)
  expect(bulk).toEqual([])
})
