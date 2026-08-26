import { expect, test } from '@playwright/test'

const requireAcris = process.env.REQUIRE_ACRIS === 'true'

const expectContained = async (page: import('@playwright/test').Page) => {
  const viewportWidth = page.viewportSize()?.width ?? 0
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
}

test('hosted TowerSignal redesigned workspace is functional, linkable and source-backed', async ({ page }, testInfo) => {
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

  for (const name of ['Prospect','Monitor','Map','NYS Market','NYS Changes','Opportunities','Portfolios','Workflow']) {
    await expect(page.getByRole('button', { name, exact: true })).toBeVisible()
  }
  await expect(page.getByRole('button', { name: 'Source Health & Coverage', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible()
  await expect(page.getByLabel('Lead filters')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Sales-ready accounts', exact: true })).toBeVisible()
  await expect(page.locator('.account-table tbody tr').first()).toBeVisible()
  await expect(page.getByLabel('Commercial signal summary')).toBeVisible()
  await expect(page.getByText('High priority accounts', { exact: true })).toBeVisible()
  await expect(page.getByText('Sampling follow-up', { exact: true })).toBeVisible()
  await expectContained(page)

  const acrisQuick = page.getByRole('button', { name: 'Recent ACRIS activity', exact: true })
  const acrisSelect = page.getByLabel('ACRIS recorded activity')
  const acrisAvailable = await acrisQuick.count() > 0
  if (requireAcris) expect(acrisAvailable, 'Required ACRIS deployment did not expose the verified cache').toBe(true)
  if (acrisAvailable) {
    await expect(acrisSelect).toBeEnabled()
    await acrisQuick.click()
    await expect(page.getByLabel('Active filters')).toContainText('ACRIS activity: Yes')
    await expect(page.locator('.account-table tbody tr').first()).toBeVisible()
    await expect(page.locator('.account-table tbody tr').first().getByText(/ACRIS · \d+/)).toBeVisible()
    await page.locator('.account-table tbody tr').first().click()
    await expect(page.getByRole('heading', { name: 'ACRIS property activity', exact: true })).toBeVisible()
    await expect(page.getByText(/relevant recorded document/)).toBeVisible()
    await expect(page.getByText(/ACRIS is joined by exact borough\/block\/lot BBL and exact document ID only/)).toBeVisible()
    await expect(page.getByRole('button', { name: 'Copy account link', exact: true })).toBeVisible()
    await expect(page).toHaveURL(/#\/account\//)
    await page.getByRole('button', { name: '← Back', exact: true }).click()
  } else {
    await expect(acrisSelect).toBeDisabled()
    const unavailableChip = page.getByText('ACRIS timing unavailable', { exact: true })
    if (testInfo.project.name === 'desktop-chromium') await expect(unavailableChip).toBeVisible()
  }

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
  await expect(page.getByRole('heading', { name: 'ACRIS property activity', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'TowerSignal History', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Source & provenance', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Copy lead brief', exact: true })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Copy account link', exact: true })).toBeVisible()
  await expect(page).toHaveURL(/#\/account\//)

  const accountUrl = page.url()
  await page.reload({ waitUntil: 'networkidle' })
  await expect(page).toHaveURL(accountUrl)
  await expect(page.getByLabel('Selected cooling tower detail')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Identity', exact: true })).toBeVisible()
  await page.getByRole('button', { name: '← Back', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible()

  if (testInfo.project.name === 'desktop-chromium') {
    const exportButton = page.getByRole('button', { name: /^Export .* accounts$/ })
    await expect(exportButton).toBeVisible()
    const downloadPromise = page.waitForEvent('download')
    await exportButton.click()
    const download = await downloadPromise
    expect(download.suggestedFilename()).toMatch(/\.csv$/i)
  }

  await page.getByRole('button', { name: 'Monitor', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Monitor workspace', exact: true })).toBeVisible()
  await expect(page.getByText(/new events/)).toBeVisible()
  await expect(page).toHaveURL(/#\/monitor$/)
  await expectContained(page)

  await page.getByRole('button', { name: 'Map', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Map workspace', exact: true })).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()
  await expect(page.getByText('Matching accounts', { exact: true })).toBeVisible()
  const mapContainment = await page.locator('.map-shell').evaluate(element => {
    const style = getComputedStyle(element)
    return { overflow: style.overflow, isolation: style.isolation, position: style.position }
  })
  expect(mapContainment).toEqual({ overflow: 'hidden', isolation: 'isolate', position: 'relative' })
  await expectContained(page)

  await page.getByRole('button', { name: 'NYS Market', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'NYS Market', exact: true })).toBeVisible()
  await expect(page.getByLabel('NYS registry filters')).toBeVisible()
  await expect(page.locator('.nys-table tbody tr').first()).toBeVisible()
  await expect(page.getByLabel('Filtered New York State cooling tower registry map')).toBeVisible()
  await expect(page.getByText(/matching NYS equipment records/)).toBeVisible()
  await expectContained(page)

  await page.getByRole('button', { name: 'NYS Changes', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'NYS Changes', exact: true })).toBeVisible()
  await expect(page.getByText('NYS history collection began')).toBeVisible()
  await expectContained(page)

  await page.getByRole('button', { name: 'Opportunities', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Opportunities workspace', exact: true })).toBeVisible()
  await expect(page.getByText('Procurement intelligence is not in the current production account payload.', { exact: true })).toBeVisible()
  await expect(page.locator('.opportunity-table tbody tr').first()).toBeVisible()
  await expectContained(page)

  await page.getByRole('button', { name: 'Portfolios', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Portfolios', exact: true })).toBeVisible()
  await expect(page.getByText('Portfolio research candidates', { exact: true })).toBeVisible()
  await expectContained(page)

  await page.getByRole('button', { name: 'Workflow', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Workflow workspace/ })).toBeVisible()
  await expect(page.getByText('New York City · private workspace', { exact: true })).toBeVisible()
  await expectContained(page)

  await page.getByRole('button', { name: 'Source Health & Coverage', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Source Health & Coverage', exact: true })).toBeVisible()
  await expect(page.locator('.source-health-table tbody tr').first()).toBeVisible()
  await expect(page.locator('.health-failed')).toHaveCount(0)
  await expectContained(page)

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})
