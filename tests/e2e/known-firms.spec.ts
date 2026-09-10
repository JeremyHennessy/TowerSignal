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

test('Known Companies master table and Prospect-style site drillthrough are source-backed and linkable', async ({ page }, testInfo) => {
  await page.evaluate(() => { window.location.hash = '#/companies' })
  await expect(page.getByRole('heading', { name: 'Known companies & firms', exact: true })).toBeVisible()
  await expect(page.getByLabel('Known firm search')).toBeVisible()
  await expect(page.getByLabel('Known firm role')).toBeVisible()
  await expect(page.getByLabel('Known firm relationship')).toBeVisible()
  await expect(page.locator('.known-firms-master-table tbody tr').first()).toBeVisible()
  await testInfo.attach('company-table-accessibility', {
    body: await page.locator('.known-firms-master-table').ariaSnapshot(),
    contentType: 'text/plain',
  })
  // WebKit exposes CSS text-transform: uppercase in the accessible name.
  // Require the same semantic column headers without depending on casing.
  await expect(page.getByRole('columnheader', { name: /Company \/ firm/i })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Service footprint/i })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Tower accounts/i })).toBeVisible()
  await expectContained(page)

  const firm = await selectMappedFirm(page)
  await page.evaluate(firmId => { window.location.hash = `#/company/${encodeURIComponent(firmId)}` }, firm.firm_id)
  await expect(page).toHaveURL(new RegExp(`#\\/company\\/${firm.firm_id.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`))
  await expect(page.getByRole('heading', { name: firm.canonical_name, exact: true })).toBeVisible()
  await expect(page.getByText(`Sites connected to ${firm.canonical_name}`, { exact: true })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Known firm site relationship map', exact: true })).toBeVisible()
  await expect(page.locator('.firm-prospect-sites-table tbody tr').first()).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Priority/i })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /^Timing signal$/i })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /^Contact$/i })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Sampling/i })).toBeVisible()
  await expect(page.getByRole('columnheader', { name: /Activity/i })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Everything TowerSignal knows about this firm', exact: true })).toBeVisible()
  await expect(page.getByText('Intelligence workspace unavailable', { exact: true })).toHaveCount(0)
  await expectContained(page)

  const evidence = page.locator('.known-firm-evidence-grid')
  await expect(evidence).toHaveCSS('display', 'grid')
  await expect(evidence.locator('.company-evidence-card')).toHaveCount(2)
  await expect(evidence.locator('.detail-grid').first()).toHaveCSS('display', 'grid')
  await expect(evidence.locator('.detail-grid dd').first()).toHaveCSS('margin-left', '0px')
  const expectedColumns = (page.viewportSize()?.width ?? 1440) <= 820 ? 1 : 2
  await expect.poll(() => evidence.evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length)).toBe(expectedColumns)
  await page.locator('.firm-evidence-heading').scrollIntoViewIfNeeded()
  await testInfo.attach('firm-evidence-layout', { body: await page.screenshot(), contentType: 'image/png' })
  await expectContained(page)
})
