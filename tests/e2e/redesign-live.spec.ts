import { expect, test } from '@playwright/test'

const expectContained = async (page: import('@playwright/test').Page) => {
  const viewportWidth = page.viewportSize()?.width ?? 0
  const diagnostic = await page.evaluate(() => {
    const viewport = document.documentElement.clientWidth
    const overflowing = [...document.querySelectorAll<HTMLElement>('body *')]
      .map(element => {
        const rect = element.getBoundingClientRect()
        return {
          tag: element.tagName.toLowerCase(),
          className: element.className?.toString().slice(0, 160) ?? '',
          aria: element.getAttribute('aria-label'),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
          clientWidth: element.clientWidth,
          scrollWidth: element.scrollWidth,
        }
      })
      .filter(item => item.right > viewport + 2 || item.left < -2)
      .sort((a, b) => b.right - a.right)
      .slice(0, 20)
    return { viewport, bodyScrollWidth: document.body.scrollWidth, documentScrollWidth: document.documentElement.scrollWidth, overflowing }
  })
  expect(diagnostic.bodyScrollWidth, `Horizontal overflow diagnostic:\n${JSON.stringify(diagnostic, null, 2)}`).toBeLessThanOrEqual(viewportWidth + 2)
}

test('commercial workspace is live and functional', async ({ page }, testInfo) => {
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
  await expect(page.getByText(/sources healthy/)).toBeVisible()
  await expect(page.getByText(/ · FAILED · /)).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath(`prospect-${testInfo.project.name}.png`), fullPage: true })

  const before = await page.locator('.account-table tbody tr').count()
  await page.getByRole('button', { name: 'Manhattan', exact: true }).click()
  await expect(page.getByLabel('Active filters')).toContainText('Borough: Manhattan')
  const after = await page.locator('.account-table tbody tr').count()
  expect(before).toBeGreaterThan(0)
  expect(after).toBeGreaterThan(0)

  await page.locator('.account-table tbody tr').first().click()
  await expect(page.getByLabel('Selected cooling tower detail')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Identity', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Historical profile', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'DOB NOW project activity', exact: true })).toBeVisible()
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
  await expectContained(page)

  await page.getByRole('button', { name: 'NYS Market', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'New York State registry intelligence' })).toBeVisible()
  await expect(page.getByLabel('NYS registry filters')).toBeVisible()
  await expect(page.locator('.nys-table tbody tr').first()).toBeVisible()
  await expect(page.getByLabel('Filtered New York State cooling tower registry map')).toBeVisible()
  await expectContained(page)

  await page.getByRole('button', { name: 'NYS Changes', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'New York State registry changes' })).toBeVisible()
  await expect(page.getByText('NYS history collection began')).toBeVisible()
  await expectContained(page)

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})
