import { mkdir } from 'node:fs/promises'
import { expect, test } from './fixtures'

const baseline = process.env.SOURCE_HEALTH_BASELINE === '1'

async function screenshotDirectory() {
  await mkdir('source-health-proof', { recursive: true })
}

test('Source Health baseline screenshot', async ({ page }, testInfo) => {
  test.skip(!baseline, 'Baseline-only screenshot; candidate assertions run separately')
  await page.evaluate(() => { window.location.hash = '#/source-health' })
  await expect(page.getByRole('heading', { name: 'Source Health & Coverage', exact: true })).toBeVisible()
  await expect(page.getByText('Loading completeness audit…')).toHaveCount(0)
  await screenshotDirectory()
  await page.screenshot({ path: `source-health-proof/baseline-${testInfo.project.name}.png`, fullPage: true })
})

test('Source Health reports actual enforcement counts, refresh coverage, 12 channels and published cache artifacts', async ({ page }, testInfo) => {
  test.skip(baseline, 'Candidate-only assertions')
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))
  await page.evaluate(() => { window.location.hash = '#/source-health' })
  await expect(page.getByRole('heading', { name: 'Source Health & Coverage', exact: true })).toBeVisible()
  const property = page.getByTestId('property-enforcement-source-health')
  const refresh = page.getByTestId('source-refresh-coverage')
  const legionella = page.getByTestId('legionella-source-health')
  await expect(property).toBeVisible()
  await expect(refresh).toBeVisible()
  await expect(refresh.locator('tbody tr')).toHaveCount(8)
  await expect(refresh).toContainText('Daily · 10:17 UTC')
  await expect(refresh).toContainText('Daily · 08:23 UTC')
  await expect(refresh).toContainText('Daily · 08:41 UTC')
  await expect(refresh).toContainText('Every 6 hours · :23 UTC')
  await expect(refresh).toContainText('Refresh time is not source observation time.')
  await expect(legionella.locator('tbody tr')).toHaveCount(12)
  await expect(property.locator('tbody tr')).toHaveCount(3)
  await expect(property.getByText('AVAILABLE', { exact: true })).toHaveCount(3)
  await expect(legionella.getByText('SNAPSHOT RETRIEVED', { exact: true })).toHaveCount(12)
  await expect(page.getByText('Coverage audit unavailable.')).toHaveCount(0)

  const expected = await page.evaluate(async () => {
    const response = await fetch(new URL('data/systems.json', window.location.href), { cache: 'no-store' })
    if (!response.ok) throw new Error(`Systems HTTP ${response.status}`)
    const data = await response.json()
    return [
      ['wvxf-dwi5', 'hpd_violation_count', 'bbl'],
      ['eabe-havv', 'stop_work_order_event_count', 'bin'],
      ['xubg-57si', 'facade_compliance_filing_count', 'bin'],
    ].map(([id, field, identity]) => {
      const source = data.metadata.sources.find((item: { dataset_id: string }) => item.dataset_id === id)
      const matched = data.systems.filter((row: Record<string, unknown>) => Number(row[field]) > 0)
      return { id, records: source.matched_record_count, sourceRows: source.source_record_count, attached: matched.length, properties: new Set(matched.map((row: Record<string, unknown>) => row[identity])).size, total: data.systems.length }
    })
  })
  const number = new Intl.NumberFormat('en-US')
  for (const value of expected) {
    const row = property.locator('tbody tr').filter({ hasText: value.id })
    await expect(row.locator('td').nth(2)).toHaveText(number.format(value.sourceRows))
    await expect(row.locator('td').nth(3)).toHaveText(number.format(value.records))
    await expect(row.locator('td').nth(5)).toContainText(number.format(value.properties))
    await expect(row.locator('td').nth(6)).toHaveText(`${number.format(value.attached)} / ${number.format(value.total)}`)
  }
  await expect(property).toContainText('not a generic Labor Law filing feed')
  await expect(property).toContainText('Not a complete or current active-SWO ledger')
  await expect(page.getByRole('cell', { name: 'property-enforcement.json', exact: true })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'legionella-alerts.json', exact: true })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'historical-311-context.json', exact: true })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)
  expect(overflow).toBe(false)
  expect(errors).toEqual([])
  await screenshotDirectory()
  const stage = process.env.CANDIDATE_ROOT ? 'candidate' : 'hosted'
  await page.screenshot({ path: `source-health-proof/${stage}-${testInfo.project.name}-page.png`, fullPage: true })
  await property.screenshot({ path: `source-health-proof/${stage}-${testInfo.project.name}-enforcement.png` })
  await refresh.screenshot({ path: `source-health-proof/${stage}-${testInfo.project.name}-refresh.png` })
  await legionella.screenshot({ path: `source-health-proof/${stage}-${testInfo.project.name}-legionella.png` })
})

test('Source Health keeps a failed Legionnaires request visible without zero or healthy fallback', async ({ page }) => {
  test.skip(baseline, 'Candidate-only failure-state assertion')
  await page.route('**/data/legionella-alerts.json', route => route.fulfill({ status: 503, body: 'Source-health test failure' }))
  await page.evaluate(() => { window.location.hash = '#/source-health' })
  const panel = page.getByTestId('legionella-source-health')
  await expect(panel).toContainText('Legionnaires source health unavailable.')
  await expect(panel).toContainText('HTTP 503')
  await expect(panel.getByText('SNAPSHOT RETRIEVED', { exact: true })).toHaveCount(0)
  await expect(panel.getByText('Retained relevant items', { exact: true })).toHaveCount(0)
})
