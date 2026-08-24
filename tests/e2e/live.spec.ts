import { expect, test } from '@playwright/test'

const expectContained = async (page: import('@playwright/test').Page) => {
  const viewportWidth = page.viewportSize()?.width ?? 0
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
}

test('hosted TowerSignal commercial workspace is functional across NYC and NYS modes', async ({ page }, testInfo) => {
  const consoleErrors: string[] = []
  const sameOriginFailures: string[] = []
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()) })
  page.on('requestfailed', request => {
    try {
      if (new URL(request.url()).origin === new URL(testInfo.project.use.baseURL as string).origin) {
        sameOriginFailures.push(`${request.url()} :: ${request.failure()?.errorText}`)
      }
    } catch { /* ignore non-URL diagnostics */ }
  })

  await page.goto('./', { waitUntil: 'networkidle' })

  await expect(page.getByRole('button', { name: 'Prospect', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Monitor', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Map', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'NYS Market', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'NYS Changes', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Know which cooling-tower accounts deserve attention now.' })).toBeVisible()
  await expect(page.getByLabel('Lead filters')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Sales-ready accounts' })).toBeVisible()
  await expect(page.locator('.account-table tbody tr').first()).toBeVisible()
  await expect(page.getByText(/NYC Cooling Tower Registrations · HEALTHY/)).toBeVisible()
  await expect(page.getByText(/ · FAILED · /)).toHaveCount(0)
  await expectContained(page)

  const before = await page.locator('.account-table tbody tr').count()
  await page.getByRole('button', { name: 'Manhattan', exact: true }).click()
  await expect(page.getByLabel('Active filters')).toContainText('Borough: Manhattan')
  const after = await page.locator('.account-table tbody tr').count()
  expect(before).toBeGreaterThan(0)
  expect(after).toBeGreaterThan(0)

  await page.getByRole('button', { name: 'OATH cases', exact: true }).click()
  await expect(page.locator('.account-table tbody tr').first()).toBeVisible()
  await page.locator('.account-table tbody tr').first().click()
  await expect(page.getByLabel('Selected cooling tower detail')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Identity', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Historical profile', exact: true })).toBeVisible()
  await expect(page.getByText('Reported samples')).toBeVisible()
  await expect(page.getByText('NYC Health inspections', { exact: true })).toBeVisible()
  await expect(page.getByText('OATH penalty imposed')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'OATH case lifecycle', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'DOB NOW project activity', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'TowerSignal History', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Source & provenance', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Copy lead brief', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Close details' }).click()

  const exportButton = page.getByRole('button', { name: /^Export .* accounts$/ })
  await expect(exportButton).toBeVisible()
  const downloadPromise = page.waitForEvent('download')
  await exportButton.click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/\.csv$/i)

  await page.getByRole('button', { name: 'Monitor', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'What changed since the last observation?' })).toBeVisible()
  await expect(page.getByText(/new events/)).toBeVisible()
  await expectContained(page)

  await page.getByRole('button', { name: 'Map', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Explore the current opportunity set geographically.' })).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()
  await expect(page.getByText('matching accounts', { exact: true })).toBeVisible()
  const mapContainment = await page.locator('.map-shell').evaluate(element => {
    const style = getComputedStyle(element)
    return { overflow: style.overflow, isolation: style.isolation, position: style.position }
  })
  expect(mapContainment).toEqual({ overflow: 'hidden', isolation: 'isolate', position: 'relative' })
  await expectContained(page)

  await page.getByRole('button', { name: 'NYS Market', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'New York State registry intelligence' })).toBeVisible()
  await expect(page.getByLabel('NYS registry filters')).toBeVisible()
  await expect(page.locator('.nys-table tbody tr').first()).toBeVisible()
  await expect(page.getByLabel('Filtered New York State cooling tower registry map')).toBeVisible()
  await expect(page.getByText(/matching NYS equipment records/)).toBeVisible()
  await expectContained(page)

  await page.getByRole('button', { name: 'NYS Changes', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'New York State registry changes' })).toBeVisible()
  await expect(page.getByText('NYS history collection began')).toBeVisible()
  await expectContained(page)

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})
