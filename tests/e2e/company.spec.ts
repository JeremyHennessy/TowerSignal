import { expect, test } from './fixtures'
import { isIphoneProject } from './iphone.helpers'

const expectContained = async (page: import('@playwright/test').Page) => {
  const viewportWidth = page.viewportSize()?.width ?? 0
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
}

async function openCompanies(page: import('@playwright/test').Page, projectName: string) {
  if (projectName.includes('iphone')) {
    await page.getByRole('button', { name: 'Open workspace menu', exact: true }).click()
    const menu = page.getByRole('dialog', { name: 'TowerSignal workspace menu', exact: true })
    await expect(menu).toBeVisible()
    await menu.getByRole('button', { name: 'Known Firms', exact: true }).click()
    return
  }
  await page.getByRole('button', { name: /^More/ }).click()
  await page.getByRole('menu').getByRole('menuitem', { name: 'Known Firms', exact: true }).click()
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

  // Preserve the authenticated fixture's same-document Safari navigation.
  await expect(page).toHaveURL(/#\/home$/)
  if (isIphoneProject(testInfo)) {
    await expect(page.getByRole('button', { name: 'Open workspace menu', exact: true })).toBeVisible()
  } else {
    await expect(page.getByRole('button', { name: /^More/ })).toBeVisible()
  }
  await openCompanies(page, testInfo.project.name)
  await expect(page).toHaveURL(/#\/companies$/)
  await expect(page.getByRole('heading', { name: 'Known companies & firms', exact: true })).toBeVisible()
  await expect(page.getByLabel('Known firm search', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Known firm identity confidence')).toBeVisible()
  await expect(page.locator('.known-firms-page table')).toHaveCount(1)
  await page.getByLabel('Known firm role', { exact: true }).selectOption('PROCUREMENT_VENDOR')
  const table = page.locator('.known-firms-master-table')
  await table.getByRole('button', { name: 'Public contracts', exact: true }).click()
  const firstRow = table.locator('tbody tr').first()
  await expect(firstRow).toBeVisible()
  await expect(firstRow.locator('.health-badge')).toHaveText(/CONFIRMED|STRONG|VERIFY|UNRESOLVED/)
  const canonicalName = await firstRow.locator('td:first-child strong').innerText()
  await expectContained(page)
  await firstRow.locator('td').first().click()
  await expect(page).toHaveURL(/#\/company\//)
  await expect(page.getByRole('heading', { level: 1, name: canonicalName, exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Copy firm link', exact: true })).toBeVisible()
  await expect(page.getByText('Identity & observed roles', { exact: true })).toBeVisible()
  await expect(page.getByText(/not revenue/i).first()).toBeVisible()
  await expect(page.locator('.firm-profile-boundaries')).toContainText(/not.*proof.*work was completed/i)
  await expect(page.locator('.company-procurement-table tbody tr').first()).toBeVisible()
  await expectContained(page)

  const companyUrl = page.url()
  const profileHeading = await page.locator('.company-profile-heading h1').innerText()
  await page.getByRole('button', { name: 'Copy firm link', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Link copied', exact: true })).toBeVisible()
  await testInfo.attach(`company-profile-${testInfo.project.name}.png`, { body: await page.screenshot(), contentType: 'image/png' })

  if (testInfo.project.name === 'desktop-chromium') {
    await page.reload({ waitUntil: 'networkidle' })
    await expect(page).toHaveURL(companyUrl)
    await expect(page.locator('.company-profile-heading h1')).toHaveText(profileHeading)
    await expect(page.getByText('Identity & observed roles', { exact: true })).toBeVisible()
    await expect(page.locator('.company-procurement-table tbody tr').first()).toBeVisible()
    await expectContained(page)
  }

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})
