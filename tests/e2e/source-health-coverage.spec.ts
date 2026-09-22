import { mkdir } from 'node:fs/promises'
import { expect, test } from './fixtures'

const baseline = process.env.SOURCE_HEALTH_BASELINE === '1'
const LABOR_LAW_DATASET_ID = 'NYS_OFFICIAL_REPORTS_LABOR_LAW_PUBLISHED_DECISIONS'
const OFFICIAL_SWO_DATASET_ID = 'NYCDOB_SWOS_ISSUED_RESCINDED_SNAPSHOT_20240205'

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
  const diagnostics = page.locator('.reference-table.source-health-table').first()
  const property = page.getByTestId('property-enforcement-source-health')
  const refresh = page.getByTestId('source-refresh-coverage')
  const legionella = page.getByTestId('legionella-source-health')
  const procurementSources = page.locator('.procurement-health-table')
  await expect(property).toBeVisible()
  await expect(refresh).toBeVisible()
  await expect(refresh.locator('tbody tr')).toHaveCount(8)
  await expect(refresh).toContainText('Daily · 10:17 UTC')
  await expect(refresh).toContainText('Daily · 08:23 UTC')
  await expect(refresh).toContainText('Daily · 08:41 UTC')
  await expect(refresh).toContainText('Every 6 hours · :23 UTC')
  await expect(refresh).toContainText('Refresh time is not source observation time.')
  await expect(refresh).toContainText('dated DOB snapshot do not establish current SWO status')
  await expect(refresh).toContainText('not a comprehensive filing feed')
  await expect(legionella.locator('tbody tr')).toHaveCount(12)
  await expect(property.locator('tbody tr')).toHaveCount(4)
  await expect(property.getByText('AVAILABLE', { exact: true })).toHaveCount(3)
  await expect(property.getByText('WARNING', { exact: true })).toHaveCount(1)
  await expect(legionella.getByText('SNAPSHOT RETRIEVED', { exact: true })).toHaveCount(12)
  await expect(page.getByText('Coverage audit unavailable.')).toHaveCount(0)
  await expect(procurementSources).toBeVisible()

  const diagnosticRows = diagnostics.locator('tbody tr')
  const diagnosticRowCount = await diagnosticRows.count()
  expect(diagnosticRowCount).toBeGreaterThan(0)
  await expect(diagnostics.locator('tbody tr td:first-child a[target="_blank"]')).toHaveCount(diagnosticRowCount)
  await expect(property.locator('tbody tr td:first-child a[target="_blank"]')).toHaveCount(4)
  await expect(legionella.locator('tbody tr td:last-child a[target="_blank"]')).toHaveCount(12)
  const procurementRowCount = await procurementSources.locator('tbody tr').count()
  expect(procurementRowCount).toBeGreaterThan(0)
  await expect(procurementSources.locator('tbody tr td:first-child a[target="_blank"]')).toHaveCount(procurementRowCount)

  const allExternalSourceHrefs = await page.locator([
    '.reference-table.source-health-table:first-of-type tbody tr td:first-child a',
    '[data-testid="property-enforcement-source-health"] tbody tr td:first-child a',
    '[data-testid="legionella-source-health"] tbody tr td:last-child a',
    '.procurement-health-table tbody tr td:first-child a',
  ].join(',')).evaluateAll(elements => elements.map(element => element.getAttribute('href') ?? ''))
  expect(allExternalSourceHrefs.length).toBeGreaterThanOrEqual(diagnosticRowCount + 4 + 12 + procurementRowCount)
  expect(allExternalSourceHrefs.every(href => href.startsWith('https://'))).toBe(true)

  const nysRegistryLink = diagnosticRows.filter({ hasText: '24a4-muw7' }).locator('a').first()
  await expect(nysRegistryLink).toHaveAttribute('href', 'https://health.data.ny.gov/Health/New-York-State-Cooling-Tower-Registry-Weekly-Extr/24a4-muw7')
  const laborLawLink = diagnosticRows.filter({ hasText: LABOR_LAW_DATASET_ID }).locator('a').first()
  await expect(laborLawLink).toHaveAttribute('href', 'https://www.nycourts.gov/reporter/RSS.shtml')
  const acrisLink = diagnosticRows.filter({ hasText: 'bnx9-e6tj+8h5j-fqxa+636b-3b5g' }).locator('a').first()
  await expect(acrisLink).toHaveAttribute('href', 'https://data.cityofnewyork.us/City-Government/ACRIS-Real-Property-Master/bnx9-e6tj')

  const expected = await page.evaluate(async () => {
    const response = await fetch(new URL('data/systems.json', window.location.href), { cache: 'no-store' })
    if (!response.ok) throw new Error(`Systems HTTP ${response.status}`)
    const data = await response.json()
    return [
      ['wvxf-dwi5', 'hpd_violation_count', 'bbl'],
      ['eabe-havv', 'stop_work_order_event_count', 'bin'],
      ['NYCDOB_SWOS_ISSUED_RESCINDED_SNAPSHOT_20240205', 'official_swo_snapshot_record_count', 'bin'],
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
  await expect(property).toContainText('dated 2022–2024 observation')
  await expect(property).toContainText('does not establish current 2026 SWO status')

  const swoHealth = property.locator('tbody tr').filter({ hasText: OFFICIAL_SWO_DATASET_ID })
  await expect(swoHealth).toBeVisible()
  await expect(swoHealth.getByText('WARNING', { exact: true })).toBeVisible()
  await expect(swoHealth).toContainText('Current status: not available from this source.')
  await expect(swoHealth).toContainText('status at that dated snapshot, not current 2026 SWO status')

  const swoSource = await page.evaluate(async datasetId => {
    const response = await fetch(new URL('data/systems.json', window.location.href), { cache: 'no-store' })
    if (!response.ok) throw new Error(`Systems HTTP ${response.status}`)
    const data = await response.json()
    const source = data.metadata.sources.find((item: { dataset_id: string }) => item.dataset_id === datasetId)
    return {
      currentStatusAvailable: source?.current_status_available,
      sourceHealthStatus: source?.source_health_status,
      observationStart: source?.source_observation_start_at,
      observationEnd: source?.source_observation_end_at,
    }
  }, OFFICIAL_SWO_DATASET_ID)
  expect(swoSource.currentStatusAvailable).toBe(false)
  expect(swoSource.sourceHealthStatus).toBe('WARNING')
  expect(swoSource.observationStart).toBeTruthy()
  expect(swoSource.observationEnd).toBeTruthy()

  const laborHealth = page.locator('.source-health-table tbody tr').filter({ hasText: LABOR_LAW_DATASET_ID })
  await expect(laborHealth).toBeVisible()
  await expect(laborHealth.getByText('WARNING', { exact: true })).toBeVisible()
  await expect(laborHealth).toContainText('published Labor Law decisions')
  await expect(laborHealth).toContainText('not a comprehensive Supreme Court filing or NYSCEF docket feed')
  await expect(laborHealth).toContainText('zero coverage is not evidence that no Labor Law filing or litigation exists')

  const laborPayload = await page.evaluate(async () => {
    const response = await fetch(new URL('data/labor-law-decisions.json', window.location.href), { cache: 'no-store' })
    if (!response.ok) throw new Error(`Labor Law cache HTTP ${response.status}`)
    const data = await response.json()
    return {
      domain: data.domain,
      currentFilingStatusAvailable: data.source?.current_filing_status_available,
      sourceHealthStatus: data.source?.source_health_status,
      retainedDecisionCount: data.summary?.retained_labor_law_decision_count,
      matchedSystemCount: data.summary?.matched_system_count,
      coverageBoundary: data.evidence_boundaries?.coverage,
    }
  })
  expect(laborPayload.domain).toBe('NYS_LABOR_LAW_PUBLISHED_DECISIONS')
  expect(laborPayload.currentFilingStatusAvailable).toBe(false)
  expect(laborPayload.sourceHealthStatus).toBe('WARNING')
  expect(Number(laborPayload.retainedDecisionCount)).toBeGreaterThanOrEqual(0)
  expect(Number(laborPayload.matchedSystemCount)).toBeGreaterThanOrEqual(0)
  expect(laborPayload.coverageBoundary).toContain('not a comprehensive filing/docket feed')

  const enforcementArtifact = page.getByRole('link', { name: 'property-enforcement.json', exact: true })
  const legionellaArtifact = page.getByRole('link', { name: 'legionella-alerts.json', exact: true })
  const historical311Artifact = page.getByRole('link', { name: 'historical-311-context.json', exact: true })
  await expect(enforcementArtifact).toBeVisible()
  await expect(legionellaArtifact).toBeVisible()
  await expect(historical311Artifact).toBeVisible()
  await expect(enforcementArtifact).toHaveAttribute('href', /data\/property-enforcement\.json$/)
  await expect(legionellaArtifact).toHaveAttribute('href', /data\/legionella-alerts\.json$/)
  await expect(historical311Artifact).toHaveAttribute('href', /data\/historical-311-context\.json$/)
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
