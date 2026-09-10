import { expect, test } from './fixtures'
import { expectContained } from './iphone.helpers'

test.setTimeout(120_000)

type FirmSeed = {
  firm_id: string
  canonical_name: string
  mapped_site_count: number
  observed_site_count: number
  serviced_site_count: number
  tower_account_count: number
}

async function selectMappedFirm(page: import('@playwright/test').Page): Promise<FirmSeed> {
  return page.evaluate(async () => {
    const base = window.location.href.split('#')[0]
    const response = await fetch(new URL('data/known-firms.json', base).toString(), { cache: 'no-store' })
    if (!response.ok) throw new Error(`known-firms.json HTTP ${response.status}`)
    const payload = await response.json() as { firms?: FirmSeed[] }
    const firms = payload.firms ?? []
    const selected = firms.find(firm => firm.mapped_site_count > 0 && firm.observed_site_count > 0 && firm.tower_account_count > 0)
    if (!selected) throw new Error('Known Firms has no firm with a mapped TowerSignal site relationship')
    return selected
  })
}

test('Known Companies master table and Prospect-style site drillthrough are source-backed and linkable', async ({ page }) => {
  await page.evaluate(() => { window.location.hash = '#/companies' })
  await expect(page.getByRole('heading', { name: 'Known companies & firms', exact: true })).toBeVisible()
  await expect(page.getByLabel('Known firm search')).toBeVisible()
  await expect(page.getByLabel('Known firm role')).toBeVisible()
  await expect(page.getByLabel('Known firm relationship')).toBeVisible()
  await expect(page.locator('.known-firms-master-table tbody tr').first()).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Company \/ firm/ })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Service footprint/ })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Tower accounts/ })).toBeVisible()
  await expectContained(page)

  const firm = await selectMappedFirm(page)
  await page.evaluate(firmId => { window.location.hash = `#/company/${encodeURIComponent(firmId)}` }, firm.firm_id)
  await expect(page).toHaveURL(new RegExp(`#\\/company\\/${firm.firm_id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`))
  await expect(page.getByRole('heading', { name: firm.canonical_name, exact: true })).toBeVisible()
  await expect(page.getByText(`Sites connected to ${firm.canonical_name}`, { exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Known firm site relationship map', exact: true })).toBeVisible()
  await expect(page.locator('.firm-prospect-sites-table tbody tr').first()).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Priority/ })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Timing signal', exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: 'Contact', exact: true })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Sampling/ })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Activity/ })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Everything TowerSignal knows about this firm', exact: true })).toBeVisible()
  await expect(page.getByText('Intelligence workspace unavailable', { exact: true })).toHaveCount(0)
  await expectContained(page)
})
