import { expect, test } from './fixtures'
import { expectContained } from './iphone.helpers'

test.setTimeout(120_000)

type FirmSeed = {
  firm_id: string
  canonical_name: string
  mapped_site_count: number
  observed_site_count: number
  serviced_site_count: number
}

async function selectMappedFirm(page: import('@playwright/test').Page): Promise<FirmSeed> {
  return page.evaluate(async () => {
    const base = window.location.href.split('#')[0]
    const response = await fetch(new URL('data/known-firms.json', base).toString(), { cache: 'no-store' })
    if (!response.ok) throw new Error(`known-firms.json HTTP ${response.status}`)
    const payload = await response.json() as { firms?: FirmSeed[] }
    const firms = payload.firms ?? []
    const selected = firms.find(firm => firm.mapped_site_count > 0 && firm.observed_site_count > 0)
    if (!selected) throw new Error('Known Firms has no firm with a mapped site relationship')
    return selected
  })
}

test('Known Firms summary and site-map drillthrough are source-backed and linkable', async ({ page }) => {
  await page.evaluate(() => { window.location.hash = '#/companies' })
  await expect(page.getByRole('heading', { name: 'Known firms', exact: true })).toBeVisible()
  await expect(page.getByText('Normalized firm summary', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Known firm search')).toBeVisible()
  await expect(page.getByLabel('Known firm role')).toBeVisible()
  await expect(page.getByLabel('Known firm relationship')).toBeVisible()
  await expect(page.locator('.known-firms-table tbody tr').first()).toBeVisible()
  await expect(page.getByText('Serviced site', { exact: true })).toBeVisible()
  await expect(page.getByText('Contracted site', { exact: true })).toBeVisible()
  await expect(page.getByText('Related site', { exact: true })).toBeVisible()
  await expectContained(page)

  const firm = await selectMappedFirm(page)
  await page.evaluate(firmId => { window.location.hash = `#/company/${encodeURIComponent(firmId)}` }, firm.firm_id)
  await expect(page).toHaveURL(new RegExp(`#\\/company\\/${firm.firm_id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`))
  await expect(page.getByRole('heading', { name: firm.canonical_name, exact: true })).toBeVisible()
  await expect(page.getByText('Firm sites & roles', { exact: true })).toBeVisible()
  await expect(page.getByText('Identity & role evidence', { exact: true })).toBeVisible()
  await expect(page.getByText('Commercial footprint', { exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Known firm site relationship map', exact: true })).toBeVisible()
  await expect(page.locator('.firm-sites-table tbody tr').first()).toBeVisible()
  await expect(page.getByText('Intelligence workspace unavailable', { exact: true })).toHaveCount(0)
  await expectContained(page)
})
