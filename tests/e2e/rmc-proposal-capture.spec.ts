import { expect, test } from '@playwright/test'
import { mkdirSync } from 'node:fs'

const OUT = 'proposal-captures'
mkdirSync(OUT, { recursive: true })

test.use({ viewport: { width: 1440, height: 1100 } })

test('capture proposal-grade live desktop examples', async ({ page }) => {
  test.setTimeout(240_000)

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
  const marketMap = page.locator('.map-shell')
  await snap('02-map-manhattan-high-priority-z10', marketMap)
  const zoomIn = marketMap.locator('.leaflet-control-zoom-in')
  for (let i = 0; i < 2 && await zoomIn.count(); i += 1) {
    await zoomIn.click()
    await page.waitForTimeout(1200)
  }
  await snap('02a-map-manhattan-high-priority-zoomed', marketMap)

  const captureAccount = async (id: string, label: string, includeSales: boolean) => {
    await go(`#/account/${id}`)
    await expect(page.locator('.detail-panel')).toBeVisible({ timeout: 120_000 })
    if (includeSales) {
      await expect(page.locator('.sales-precall-pack')).toBeVisible({ timeout: 120_000 })
      await snap(`${label}-sales-precall`, page.locator('.sales-precall-pack'))
      await snap(`${label}-sales-metrics`, page.locator('.sales-pack-metrics'))
      await snap(`${label}-call-objective`, page.locator('.sales-pack-objective'))
      const panels = page.locator('.sales-pack-panel')
      for (let i = 0; i < Math.min(await panels.count(), 5); i += 1) await snap(`${label}-sales-panel-${i + 1}`, panels.nth(i))
    }
    await snap(`${label}-field-pack`, page.locator('.technician-field-pack'))
    await page.waitForTimeout(4000)
    await snap(`${label}-roof-intelligence`, page.locator('.planimetric-section'))
    await snap(`${label}-roof-map`, page.locator('.planimetric-map-shell'))
  }

  // High priority institutional campus: confirmed violation, sampling-gap signal,
  // eight active units, six mapped tower footprints and recent DOB activity.
  await captureAccount('2000012577', '03-cuny-oriental', true)

  // Dense Midtown commercial property: four active units, seven mapped tower
  // footprints, recent property activity, substantial DOB and OATH evidence.
  await captureAccount('2000000452', '04-madison-250', false)

  // Iconic Manhattan field example: seven active units and twelve mapped roof
  // footprints provide a visually dense technician-preparation aerial.
  await captureAccount('2000000855', '05-central-park-south', false)

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
    await page.waitForTimeout(2500)
    await snap('07a-company-metro-group-profile', page.locator('.product-page'))
  }

  await go('#/portfolios')
  await expect(page.getByRole('heading', { name: 'Portfolios', exact: true })).toBeVisible({ timeout: 120_000 })
  await snap('08-portfolios', page.locator('.portfolios-page'))
})
