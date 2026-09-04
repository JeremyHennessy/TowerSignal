import { expect, test } from './fixtures'

const expectContained = async (page: import('@playwright/test').Page) => {
  const viewportWidth = page.viewportSize()?.width ?? 0
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
}

test('hosted Companies and Company Profile are source-backed, shareable and reload-safe', async ({ page }, testInfo) => {
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

  // The authenticated fixture already leaves this tab on #/home. Do not
  // perform an immediate document reload on Safari/WebKit because github.io
  // cannot recover the cross-site neon.tech auth cookie after navigation.
  await expect(page).toHaveURL(/#\/home$/)
  await expect(page.getByRole('button', { name:'Companies', exact:true })).toBeVisible()
  await page.getByRole('button', { name:'Companies', exact:true }).click()
  await expect(page).toHaveURL(/#\/companies$/)
  await expect(page.getByRole('heading', { name:'Companies', exact:true })).toBeVisible()
  await expect(page.getByText('Company & vendor intelligence', { exact:true })).toBeVisible()
  await expect(page.locator('.companies-table tbody tr').first()).toBeVisible()
  await expect(page.getByText(/Public Checkbook values · not revenue/)).toBeVisible()
  await expect(page.getByLabel('Company resolution confidence')).toBeVisible()
  await expectContained(page)

  const firstRow = page.locator('.companies-table tbody tr').first()
  await expect(firstRow.locator('.health-badge')).toHaveText(/STRONG|VERIFY/)
  await firstRow.getByRole('button', { name:'Open company →', exact:true }).click()
  await expect(page).toHaveURL(/#\/company\//)
  await expect(page.getByText('Observed public procurement vendor profile', { exact:true })).toBeVisible()
  await expect(page.getByRole('button', { name:'Copy company link', exact:true })).toBeVisible()
  await expect(page.getByText('Cross-source resolution', { exact:true }).first()).toBeVisible()
  await expect(page.getByText(/not revenue/i).first()).toBeVisible()
  await expect(page.getByText(/No parent, sponsor, acquisition or private-company financial claims/)).toBeVisible()
  await expect(page.locator('.company-procurement-table tbody tr').first()).toBeVisible()
  await expectContained(page)

  const companyUrl = page.url()
  const profileHeading = await page.locator('.company-profile-heading h1').innerText()
  await page.getByRole('button', { name:'Copy company link', exact:true }).click()
  await expect(page.getByRole('button', { name:'Link copied', exact:true })).toBeVisible()

  if (testInfo.project.name === 'desktop-chromium') {
    await page.reload({ waitUntil:'networkidle' })
    await expect(page).toHaveURL(companyUrl)
    await expect(page.locator('.company-profile-heading h1')).toHaveText(profileHeading)
    await expect(page.getByText('Cross-source resolution', { exact:true }).first()).toBeVisible()
    await expect(page.locator('.company-procurement-table tbody tr').first()).toBeVisible()
    await expectContained(page)
  }

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})
