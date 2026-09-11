import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'
import { signInForProject } from './auth.helpers'

const authenticatedRoutes = [
  ['home', '#/home', 'Move from signal to action.'],
  ['prospect', '#/prospect', 'Prospect workspace'],
  ['monitor', '#/monitor', 'Monitor workspace'],
  ['map', '#/map', 'Map workspace'],
  ['opportunities', '#/opportunities', 'Opportunities workspace'],
  ['nys-market', '#/nys', 'NYS Market'],
  ['nys-changes', '#/nys-changes', 'NYS Changes'],
  ['companies', '#/companies', 'Company & vendor intelligence'],
  ['water-quality', '#/water-quality', 'Water Quality'],
  ['portfolios', '#/portfolios', 'Portfolios'],
  ['workflow', '#/workflow', 'Workflow'],
  ['source-health', '#/source-health', 'Source Health & Coverage'],
  ['nyc-account-2000012577', '#/account/2000012577', '2000012577'],
  ['my-account', '#/my-account', 'E2E Verification'],
] as const

function screenshotPath(project: string, name: string) {
  const dir = join('test-results', 'live-page-audit', project)
  mkdirSync(dir, { recursive: true })
  return join(dir, `${name}.png`)
}

async function capturePage(page: import('@playwright/test').Page, project: string, name: string) {
  const geometry = await page.evaluate(() => ({
    height: Math.max(document.body.scrollHeight, document.documentElement.scrollHeight),
    viewport: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio || 1,
  }))
  const safeFullPageCssHeight = Math.floor(24_000 / Math.max(1, geometry.devicePixelRatio))
  const isIphoneProject = project.toLowerCase().includes('iphone')
  if (!isIphoneProject && geometry.height <= safeFullPageCssHeight) {
    await page.screenshot({ path: screenshotPath(project, name), fullPage: true })
    return
  }

  const step = Math.max(500, geometry.viewport - 100)
  let part = 1
  for (let y = 0; y < geometry.height; y += step) {
    await page.evaluate(scrollY => window.scrollTo(0, scrollY), y)
    await page.waitForTimeout(75)
    await page.screenshot({ path: screenshotPath(project, `${name}-part-${String(part).padStart(2, '0')}`), fullPage: false })
    part += 1
  }
  await page.evaluate(() => window.scrollTo(0, 0))
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

  await capturePage(page, project, name)
  expect(errors, `${name} emitted browser errors: ${errors.join(' | ')}`).toEqual([])

  page.off('console', onConsole)
  page.off('pageerror', onPageError)
}

async function assertAuthenticatedWorkspace(page: import('@playwright/test').Page, expectedText: string) {
  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toHaveCount(0)
  await expect(page.locator('body')).toContainText(expectedText)
}

async function dataId(page: import('@playwright/test').Page, file: string, arrayKey: string, idKeys: string[]): Promise<string> {
  return page.evaluate(async ({ file, arrayKey, idKeys }) => {
    const base = window.location.href.split('#')[0]
    const response = await fetch(new URL(`data/${file}`, base).toString(), { cache: 'no-store' })
    if (!response.ok) throw new Error(`${file} HTTP ${response.status}`)
    const payload = await response.json() as Record<string, unknown>
    const rows = payload[arrayKey]
    if (!Array.isArray(rows) || rows.length === 0) throw new Error(`${file} has no ${arrayKey}`)
    const first = rows[0] as Record<string, unknown>
    for (const key of idKeys) {
      const value = first[key]
      if (typeof value === 'string' && value.trim()) return value
    }
    throw new Error(`${file} first ${arrayKey} row has no usable ID`)
  }, { file, arrayKey, idKeys })
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
  for (const [name, hash, expectedText] of authenticatedRoutes) {
    test(`${name} screenshot`, async ({ page }, testInfo) => {
      await signInForProject(page, testInfo.project.name, hash)
      await assertAuthenticatedWorkspace(page, expectedText)
      await auditPage(page, testInfo.project.name, name)
    })
  }

  test('company profile screenshot', async ({ page }, testInfo) => {
    await signInForProject(page, testInfo.project.name, '#/companies')
    await assertAuthenticatedWorkspace(page, 'Company & vendor intelligence')
    const companyId = await dataId(page, 'companies.json', 'companies', ['company_id'])
    await page.goto(`./#/company/${encodeURIComponent(companyId)}`, { waitUntil: 'networkidle' })
    await expect(page).toHaveURL(/#\/company\//)
    await assertAuthenticatedWorkspace(page, 'Observed public procurement vendor profile')
    await auditPage(page, testInfo.project.name, 'company-profile')
  })

  test('nys equipment profile screenshot', async ({ page }, testInfo) => {
    await signInForProject(page, testInfo.project.name, '#/nys')
    await assertAuthenticatedWorkspace(page, 'NYS Market')
    const equipmentId = await dataId(page, 'nys-systems.json', 'systems', ['system_id', 'source_equipment_id'])
    await page.goto(`./#/nys-account/${encodeURIComponent(equipmentId)}`, { waitUntil: 'networkidle' })
    await expect(page).toHaveURL(/#\/nys-account\//)
    await assertAuthenticatedWorkspace(page, equipmentId)
    await auditPage(page, testInfo.project.name, 'nys-equipment-profile')
  })
})
