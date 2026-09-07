import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const authenticatedRoutes = [
  ['home', '#/home'],
  ['prospect', '#/prospect'],
  ['monitor', '#/monitor'],
  ['map', '#/map'],
  ['opportunities', '#/opportunities'],
  ['nys-market', '#/nys'],
  ['nys-changes', '#/nys-changes'],
  ['companies', '#/companies'],
  ['water-quality', '#/water-quality'],
  ['portfolios', '#/portfolios'],
  ['workflow', '#/workflow'],
  ['source-health', '#/source-health'],
  ['nyc-account-2000012577', '#/account/2000012577'],
  ['my-account', '#/my-account'],
] as const

function screenshotPath(project: string, name: string) {
  const dir = join('test-results', 'live-page-audit', project)
  mkdirSync(dir, { recursive: true })
  return join(dir, `${name}.png`)
}

async function auditPage(page: import('@playwright/test').Page, project: string, name: string) {
  const errors: string[] = []
  const onConsole = (message: import('@playwright/test').ConsoleMessage) => {
    if (message.type() === 'error') errors.push(message.text())
  }
  const onPageError = (error: Error) => errors.push(error.message)
  page.on('console', onConsole)
  page.on('pageerror', onPageError)

  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(500)
  await expect(page.locator('body')).not.toContainText('Intelligence workspace unavailable')

  const geometry = await page.evaluate(() => ({
    innerWidth: window.innerWidth,
    bodyScrollWidth: document.body.scrollWidth,
    docScrollWidth: document.documentElement.scrollWidth,
    bodyTextLength: document.body.innerText.trim().length,
  }))
  expect(geometry.bodyTextLength, `${name} should render meaningful content`).toBeGreaterThan(80)
  expect(Math.max(geometry.bodyScrollWidth, geometry.docScrollWidth), `${name} should not overflow horizontally`).toBeLessThanOrEqual(geometry.innerWidth + 2)

  await page.screenshot({ path: screenshotPath(project, name), fullPage: true })
  expect(errors, `${name} emitted browser errors: ${errors.join(' | ')}`).toEqual([])

  page.off('console', onConsole)
  page.off('pageerror', onPageError)
}

test.describe('public live pages', () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test('marketing and login screenshots', async ({ page }, testInfo) => {
    await page.goto('./', { waitUntil: 'networkidle' })
    await auditPage(page, testInfo.project.name, 'marketing')

    await page.goto('./#/login', { waitUntil: 'networkidle' })
    await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
    await auditPage(page, testInfo.project.name, 'login')
  })
})

test.describe('authenticated live workspaces', () => {
  for (const [name, hash] of authenticatedRoutes) {
    test(`${name} screenshot`, async ({ page }, testInfo) => {
      await page.goto(`./${hash}`, { waitUntil: 'networkidle' })
      await auditPage(page, testInfo.project.name, name)
    })
  }

  test('company profile screenshot', async ({ page }, testInfo) => {
    await page.goto('./#/companies', { waitUntil: 'networkidle' })
    const companyLink = page.locator('a[href*="#/company/"]').first()
    if (await companyLink.count()) {
      await companyLink.click()
    } else {
      const row = page.locator('tbody tr').first()
      await expect(row).toBeVisible()
      await row.click()
    }
    await page.waitForURL(/#\/company\//)
    await auditPage(page, testInfo.project.name, 'company-profile')
  })

  test('nys equipment profile screenshot', async ({ page }, testInfo) => {
    await page.goto('./#/nys', { waitUntil: 'networkidle' })
    const accountLink = page.locator('a[href*="#/nys-account/"]').first()
    if (await accountLink.count()) {
      await accountLink.click()
    } else {
      const row = page.locator('tbody tr').first()
      await expect(row).toBeVisible()
      await row.click()
    }
    await page.waitForURL(/#\/nys-account\//)
    await auditPage(page, testInfo.project.name, 'nys-equipment-profile')
  })
})
