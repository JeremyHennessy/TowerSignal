import { expect, test } from '@playwright/test'

test('hosted TowerSignal loads data, changes, historical profile, OATH lifecycle and map without app errors', async ({ page }, testInfo) => {
  const consoleErrors: string[] = []
  const sameOriginFailures: string[] = []
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()) })
  page.on('requestfailed', request => {
    try {
      if (new URL(request.url()).origin === new URL(testInfo.project.use.baseURL as string).origin) sameOriginFailures.push(`${request.url()} :: ${request.failure()?.errorText}`)
    } catch { /* ignore non-URL diagnostics */ }
  })

  await page.goto('./', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'TowerSignal' })).toBeVisible()
  await expect(page.getByText('Registered systems')).toBeVisible()
  await expect(page.getByText('Systems with OATH cases')).toBeVisible()
  await expect(page.locator('tbody tr').first()).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()
  await expect(page.locator('.marker-cluster, .tower-marker').first()).toBeVisible()

  await page.getByRole('button', { name: 'Changes' }).click()
  await expect(page.getByRole('heading', { name: 'What changed?' })).toBeVisible()
  await expect(page.getByText('History collection began')).toBeVisible()
  await expect(page.getByText(/change.*in current view/)).toBeVisible()
  await page.getByRole('button', { name: 'Leads' }).click()

  const before = await page.locator('tbody tr').count()
  await page.getByRole('button', { name: 'Manhattan' }).click()
  await expect(page.getByText(/matching systems/)).toBeVisible()
  const after = await page.locator('tbody tr').count()
  expect(before).toBeGreaterThan(0)
  expect(after).toBeGreaterThan(0)

  await page.getByRole('button', { name: 'OATH cases' }).click()
  await expect(page.locator('tbody tr').first()).toBeVisible()
  await page.locator('tbody tr').first().click()
  await expect(page.getByRole('heading', { name: 'Identity' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Historical profile' })).toBeVisible()
  await expect(page.getByText('Reported samples')).toBeVisible()
  await expect(page.getByText('NYC Health inspections')).toBeVisible()
  await expect(page.getByText('OATH penalty imposed')).toBeVisible()
  await expect(page.getByText(/Descriptive history derived from the current authoritative NYC registration/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'OATH case lifecycle' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'TowerSignal History' })).toBeVisible()
  await expect(page.getByText(/Matched by exact NYC Health summons number to OATH ticket number/).first()).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Source & provenance' })).toBeVisible()
  await page.reload({ waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'TowerSignal' })).toBeVisible()

  expect(sameOriginFailures, `Same-origin request failures: ${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors: ${consoleErrors.join('\n')}`).toEqual([])
})

test('mobile layout keeps Leads and Changes controls readable and usable', async ({ page }) => {
  await page.goto('./', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'TowerSignal' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Export filtered CSV' })).toBeVisible()
  await expect(page.getByLabel('Lead filters')).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()
  await page.getByRole('button', { name: 'Changes' }).click()
  await expect(page.getByRole('heading', { name: 'What changed?' })).toBeVisible()
  await expect(page.getByText('History collection began')).toBeVisible()
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  const viewportWidth = page.viewportSize()?.width ?? 0
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
})
