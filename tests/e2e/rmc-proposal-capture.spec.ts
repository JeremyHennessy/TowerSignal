import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'

const OUT = 'proposal-captures'
mkdirSync(OUT, { recursive: true })

test.use({ viewport: { width: 1440, height: 1100 } })

test('capture proposal-grade live desktop examples', async ({ page }) => {
  test.setTimeout(180_000)

  const go = async (hash: string) => {
    await page.goto(`./${hash}`, { waitUntil: 'domcontentloaded', timeout: 120_000 })
    await expect(page.locator('.app-shell')).toBeVisible({ timeout: 120_000 })
    await expect(page.locator('.loading-page')).toHaveCount(0, { timeout: 120_000 })
    await page.waitForTimeout(2500)
  }

  const snap = async (name: string, locator: ReturnType<typeof page.locator>) => {
    if (await locator.count()) {
      const target = locator.first()
      await target.scrollIntoViewIfNeeded()
      await page.waitForTimeout(700)
      await target.screenshot({ path: `${OUT}/${name}.png`, animations: 'disabled' })
    }
  }

  await go('#/prospect?borough=Manhattan&minScore=70')
  await snap('01-prospect-manhattan-high-priority', page.locator('.prospect-reference-page'))
  await snap('01a-prospect-metrics', page.locator('.prospect-reference-metrics'))
  await snap('01b-prospect-ranked-accounts', page.locator('.reference-table-card').last())

  await go('#/map?borough=Manhattan&minScore=70')
  await page.waitForTimeout(4500)
  await snap('02-map-manhattan-high-priority', page.locator('.map-shell'))

  await go('#/account/2000015564')
  await expect(page.locator('.sales-precall-pack')).toBeVisible({ timeout: 120_000 })
  await snap('03-account-sales-precall', page.locator('.sales-precall-pack'))
  await snap('03a-account-sales-metrics', page.locator('.sales-pack-metrics'))
  await snap('03b-account-call-objective', page.locator('.sales-pack-objective'))
  const salesPanels = page.locator('.sales-pack-panel')
  for (let i = 0; i < Math.min(await salesPanels.count(), 5); i += 1) {
    await snap(`03c-account-sales-panel-${i + 1}`, salesPanels.nth(i))
  }
  await snap('04-account-field-pack', page.locator('.technician-field-pack'))
  await page.waitForTimeout(4000)
  await snap('05-account-roof-intelligence', page.locator('.planimetric-section'))
  await snap('05a-account-roof-map', page.locator('.planimetric-map-shell'))

  await go('#/opportunities')
  await expect(page.getByRole('heading', { name: /Opportunities/i })).toBeVisible({ timeout: 120_000 })
  const service = page.getByLabel('Procurement service category')
  if (await service.count()) {
    const options = await service.locator('option').evaluateAll(options => options.map(option => ({ value: (option as HTMLOptionElement).value, text: option.textContent ?? '' })))
    const cooling = options.find(option => /cooling tower/i.test(option.text))
    if (cooling) {
      await service.selectOption(cooling.value)
      await page.waitForTimeout(900)
    }
  }
  await snap('06-opportunities-procurement', page.locator('.opportunities-page'))
  await snap('06a-opportunities-procurement-table', page.locator('.reference-table-card').first())

  await go('#/companies')
  await expect(page.getByRole('heading', { name: /Companies|Known companies/i })).toBeVisible({ timeout: 120_000 })
  const companySearch = page.getByLabel(/Company search|Search companies/i)
  if (await companySearch.count()) {
    await companySearch.fill('METRO GROUP')
    await page.waitForTimeout(900)
  }
  await snap('07-companies-metro-group', page.locator('.companies-page, .known-companies-page'))
  const metroRow = page.locator('tr').filter({ hasText: /METRO GROUP/i }).first()
  if (await metroRow.count()) {
    await metroRow.click()
    await page.waitForTimeout(2200)
    await snap('07a-company-metro-group-profile', page.locator('.product-page'))
  }

  await go('#/portfolios')
  await expect(page.getByRole('heading', { name: 'Portfolios', exact: true })).toBeVisible({ timeout: 120_000 })
  await snap('08-portfolios', page.locator('.portfolios-page'))
})
