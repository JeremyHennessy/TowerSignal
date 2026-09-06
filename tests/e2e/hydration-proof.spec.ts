import { expect, test } from './fixtures'

test.setTimeout(300_000)

test('hosted iPhone procurement hydrates to real source-backed controls and rows', async ({ page }) => {
  const consoleErrors: string[] = []
  const sameOriginFailures: string[] = []
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()) })
  page.on('requestfailed', request => {
    try {
      if (new URL(request.url()).origin === new URL(page.url()).origin) {
        sameOriginFailures.push(`${request.url()} :: ${request.failure()?.errorText}`)
      }
    } catch { /* ignore non-URL diagnostics */ }
  })

  await page.evaluate(() => { window.location.hash = '#/opportunities' })
  await expect(page.getByRole('heading', { name: 'Opportunities workspace', exact: true })).toBeVisible()

  const procurementSource = page.getByLabel('Procurement source')
  await expect(procurementSource).toBeVisible({ timeout: 180_000 })
  await expect(page.getByText('Public procurement intelligence', { exact: true })).toBeVisible()
  await expect(page.locator('.procurement-table tbody tr').first()).toBeVisible()
  await expect(procurementSource.locator('option[value="NYS_AUTHORITIES"]')).toHaveCount(1)
  await expect(page.getByText(/NYS authorities · 4\/4 healthy/)).toBeVisible()
  await procurementSource.selectOption('NYS_AUTHORITIES')
  await expect(page.locator('.procurement-table tbody tr').first()).toContainText('NYS Authority Report')
  await expect(page.getByText('Loading verified procurement intelligence…', { exact: true })).toHaveCount(0)

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})
