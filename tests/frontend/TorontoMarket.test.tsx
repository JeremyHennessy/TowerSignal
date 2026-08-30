import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { buildTorontoCsv, buildTorontoPropertySearchText, groupTorontoSourceLinks, propertyMatchesTorontoSourceFilters, TorontoMarketPage } from '../../src/components/TorontoMarketPage'

vi.mock('../../src/components/TorontoMarketMap', () => ({ TorontoMarketMap: () => <div data-testid="toronto-map">Toronto map</div> }))
vi.mock('../../src/data/api', () => ({ loadTorontoMarket: vi.fn().mockResolvedValue({
  schema_version: 'toronto-market-app-1.0', generated_at: '2026-08-29T00:00:00Z', feature_status: 'ISOLATED_BETA',
  counts: { canonical_properties: 2, original_poc_properties: 177, original_poc_resolved: 173, original_poc_unresolved: 4, documentary_confirmed_properties: 1, strong_documentary_candidates: 0, aic_document_candidates: null, aerial_review_candidates: 1, source_links: 2, record_level_source_links: 1, official_source_families: 2, relationship_edges: 1 },
  true_market_coverage: { status: 'UNKNOWN_DENOMINATOR', coverage_percent: null },
  source_coverage: { chemtrac_history: { status: 'JOINED', source_records: 10, records_with_property_address: 9, matched_records: 7, matched_canonical_properties: 1, unmatched_source_records: 3 } },
  source_catalog: {
    chemtrac_history: { dataset_url: 'https://open.toronto.ca/dataset/chemical-tracking-chemtrac/', dataset_link_label: 'Open official dataset', link_level: 'RECORD_AND_DATASET' },
    toronto_aic_applications: { dataset_url: 'https://www.toronto.ca/city-government/planning-development/application-details/', dataset_link_label: 'Open current AIC application search', link_level: 'DATASET_FALLBACK' },
  },
  limitations: ['AIC document transport is blocked.'], unresolved_poc: [{ property_key: 'poc-2', input_address: '89 Humber College Blvd', resolution_status: 'NO_CURRENT_ADDRESS_POINT_MATCH', candidate_address_point_ids: [] }],
  properties: [
    { property_id: 'toronto-address-point:100', address_point_id: '100', display_address: '10 Alpha St', municipality: 'Toronto', longitude: -79.38, latitude: 43.65, identity_basis: 'CURRENT_ID', identity_confidence: 'HIGH', is_original_poc_property: true, tower_evidence_status: 'CONFIRMED_DOCUMENTARY_TOWER', source_keys: ['chemtrac_history'], source_links: [{ source_key: 'chemtrac_history', source_record_id: 'chem:1', match_basis: 'EXACT_ADDRESS', source_address: '10 Alpha St', record_url: 'https://secure.toronto.ca/nm/api/individual/notice/123.do', record_link_label: 'Open public notice', record_title: 'Alpha facility', record_date: '2024', record_status: null, record_details: [{ label: 'Chemical', value: 'Nickel' }] }, { source_key: 'chemtrac_history', source_record_id: 'chem:2', match_basis: 'EXACT_ADDRESS', source_address: '10 Alpha St', record_url: null, record_link_label: null, record_title: 'Alpha facility', record_date: '2023', record_status: null, record_details: [{ label: 'Chemical', value: 'Lead' }] }, ...Array.from({ length: 10 }, (_, index) => ({ source_key: 'chemtrac_history', source_record_id: `chem:extra-${index}`, match_basis: 'EXACT_ADDRESS', source_address: '10 Alpha St', record_url: null, record_link_label: null, record_title: 'Alpha facility', record_date: String(2012 + index), record_status: null, record_details: [{ label: 'Chemical', value: `Chemical ${index}` }] }))], relationships: [{ relationship: 'PROPERTY_MANAGER_OF', organization: 'Alpha Management', source_key: 'rentsafe', confidence: 'HIGH', basis: 'EXPLICIT_ROLE' }], aerial_review_rank: null, aerial_visual_similarity_score: null },
    { property_id: 'toronto-address-point:200', address_point_id: '200', display_address: '20 Beta Ave', municipality: 'Toronto', longitude: -79.4, latitude: 43.67, identity_basis: 'CURRENT_ID', identity_confidence: 'HIGH', is_original_poc_property: false, tower_evidence_status: 'AERIAL_REVIEW_CANDIDATE', source_keys: ['toronto_aic_applications'], source_links: [{ source_key: 'toronto_aic_applications', source_record_id: 'aic:1', match_basis: 'EXACT_ADDRESS', source_address: '20 Beta Ave', record_url: null, record_link_label: null, record_title: '24 100000 STE 01 OZ', record_date: '2024-01-01', record_status: 'Under review', record_details: [{ label: 'Application type', value: 'Rezoning' }] }], relationships: [], aerial_review_rank: 1, aerial_visual_similarity_score: 0.91 },
  ],
}) }))

beforeEach(() => { window.location.hash = '#/toronto' })

test('keeps Toronto identity, documentary evidence, aerial review and unknown coverage separate', async () => {
  const user = userEvent.setup()
  render(<TorontoMarketPage />)
  expect(await screen.findByRole('heading', { name: 'Toronto Market', level: 1 })).toBeInTheDocument()
  expect(screen.getByText('Market denominator unknown.')).toBeInTheDocument()
  expect(screen.getAllByText('Confirmed documentary tower').length).toBeGreaterThanOrEqual(1)
  expect(screen.getAllByText('Aerial review candidate').length).toBeGreaterThanOrEqual(1)
  expect(screen.queryByText(/% market coverage/i)).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: '20 Beta Ave' }))
  const detail = screen.getByRole('complementary', { name: 'Toronto property detail' })
  expect(within(detail).getByText(/This is not cooling-tower evidence/)).toBeInTheDocument()
  expect(window.location.hash).toContain('toronto-address-point%3A200')
})

test('filters by source-backed evidence without applying NYC priority semantics', async () => {
  const user = userEvent.setup()
  render(<TorontoMarketPage />)
  await screen.findByText('10 Alpha St')
  await user.selectOptions(screen.getByLabelText('Tower evidence'), 'CONFIRMED_DOCUMENTARY_TOWER')
  expect(screen.getByText('10 Alpha St')).toBeInTheDocument()
  expect(screen.queryByText('20 Beta Ave')).not.toBeInTheDocument()
  expect(screen.queryByText(/priority score/i)).not.toBeInTheDocument()
})

test('searches normalized source evidence and organization identities', async () => {
  const user = userEvent.setup()
  render(<TorontoMarketPage />)
  const search = await screen.findByPlaceholderText('Address, company, application or source record')

  await user.type(search, 'Nickel')
  expect(screen.getByText('10 Alpha St')).toBeInTheDocument()
  expect(screen.queryByText('20 Beta Ave')).not.toBeInTheDocument()

  await user.clear(search)
  await user.type(search, '24 100000 STE 01 OZ')
  expect(screen.queryByText('10 Alpha St')).not.toBeInTheDocument()
  expect(screen.getByText('20 Beta Ave')).toBeInTheDocument()

  await user.clear(search)
  await user.type(search, 'Alpha Management')
  expect(screen.getByText('10 Alpha St')).toBeInTheDocument()
  expect(screen.queryByText('20 Beta Ave')).not.toBeInTheDocument()
})

test('filters Toronto properties by actual organization role and POC scope', async () => {
  const user = userEvent.setup()
  render(<TorontoMarketPage />)
  await screen.findByText('10 Alpha St')

  await user.selectOptions(screen.getByLabelText('Organization role'), 'PROPERTY_MANAGER_OF')
  expect(screen.getByText('10 Alpha St')).toBeInTheDocument()
  expect(screen.queryByText('20 Beta Ave')).not.toBeInTheDocument()

  await user.selectOptions(screen.getByLabelText('Organization role'), '')
  await user.selectOptions(screen.getByLabelText('Property scope'), 'expanded')
  expect(screen.queryByText('10 Alpha St')).not.toBeInTheDocument()
  expect(screen.getByText('20 Beta Ave')).toBeInTheDocument()
})

test('filters by normalized source-specific fields', async () => {
  const user = userEvent.setup()
  render(<TorontoMarketPage />)
  await user.click(await screen.findByText('Source-specific filters'))

  await user.selectOptions(screen.getByLabelText('ChemTRAC chemical'), 'Nickel')
  expect(screen.getByText('10 Alpha St')).toBeInTheDocument()
  expect(screen.queryByText('20 Beta Ave')).not.toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Clear source filters' }))
  await user.type(screen.getByLabelText('AIC application'), '24 100000 STE 01 OZ')
  expect(screen.queryByText('10 Alpha St')).not.toBeInTheDocument()
  expect(screen.getByText('20 Beta Ave')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Clear source filters' }))
  await user.type(screen.getByLabelText('Company'), 'Alpha Management')
  expect(screen.getByText('10 Alpha St')).toBeInTheDocument()
  expect(screen.queryByText('20 Beta Ave')).not.toBeInTheDocument()
})

test('shows measured source coverage and the unresolved identity queue', async () => {
  const user = userEvent.setup()
  render(<TorontoMarketPage />)
  await screen.findByText('10 Alpha St')

  await user.click(screen.getByText('Source coverage and deterministic join results'))
  const coverage = screen.getAllByText('ChemTRAC history').find(item => item.closest('tr'))?.closest('tr')
  expect(coverage).not.toBeNull()
  expect(within(coverage as HTMLElement).getByText('10')).toBeInTheDocument()
  expect(within(coverage as HTMLElement).getByText('7')).toBeInTheDocument()

  await user.click(screen.getByText('Known data limitations'))
  expect(screen.getByText(/89 Humber College Blvd/)).toBeInTheDocument()
})

test('renders normalized record links and labels dataset-only fallbacks honestly', async () => {
  const user = userEvent.setup()
  render(<TorontoMarketPage />)
  await user.click(await screen.findByRole('button', { name: '10 Alpha St' }))
  const detail = screen.getByRole('complementary', { name: 'Toronto property detail' })
  expect(within(detail).getByText('Nickel')).toBeInTheDocument()
  expect(within(detail).getByRole('link', { name: 'Open public notice ↗' })).toHaveAttribute('href', 'https://secure.toronto.ca/nm/api/individual/notice/123.do')
  expect(within(detail).getByRole('link', { name: 'Open official dataset ↗' })).toHaveAttribute('href', 'https://open.toronto.ca/dataset/chemical-tracking-chemtrac/')
  expect(within(detail).getAllByRole('link', { name: 'Open official dataset ↗' })).toHaveLength(1)
  expect(within(detail).getByText('12 records · 2012–2024 · 12 reporting years')).toBeInTheDocument()
  expect(within(detail).queryByText('Chemical 9')).not.toBeInTheDocument()
  await user.click(within(detail).getByRole('button', { name: 'Show 2 more' }))
  expect(within(detail).getByText('Chemical 9')).toBeInTheDocument()

  await user.click(within(detail).getByRole('button', { name: 'Close Toronto property detail' }))
  await user.click(screen.getByRole('button', { name: '20 Beta Ave' }))
  expect(screen.getByText(/No durable row-level URL is published/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Open current AIC application search ↗' })).toHaveAttribute('href', 'https://www.toronto.ca/city-government/planning-development/application-details/')
})

test('groups source histories without dropping underlying records', () => {
  const links = Array.from({ length: 3 }, (_, index) => ({ source_key: 'chemtrac_history', source_record_id: `chem:${index}`, match_basis: 'EXACT_ADDRESS', source_address: '10 Alpha St', record_url: null, record_link_label: null, record_title: 'Alpha facility', record_date: String(2022 + index), record_status: null, record_details: [] }))
  const groups = groupTorontoSourceLinks(links)
  expect(groups).toHaveLength(1)
  expect(groups[0].links).toHaveLength(3)
  expect(groups[0].yearSummary).toBe('2022–2024 · 3 reporting years')
})

test('matches health and environmental source filters without changing tower evidence', () => {
  const property = {
    property_id: 'toronto-address-point:300', address_point_id: '300', display_address: '30 Gamma Rd', municipality: 'Toronto', longitude: -79.3, latitude: 43.7, identity_basis: 'CURRENT_ID', identity_confidence: 'HIGH', is_original_poc_property: false, tower_evidence_status: 'NO_TOWER_ASSERTION' as const, source_keys: ['toronto_highrise_residential_health_hazards', 'ontario_environmental_compliance_reports'], source_links: [
      { source_key: 'toronto_highrise_residential_health_hazards', source_record_id: 'health:1', match_basis: 'EXACT_ADDRESS', source_address: '30 Gamma Rd', record_url: null, record_link_label: null, record_title: 'CASE-1', record_date: '2025-01-01', record_status: 'Closed', record_details: [] },
      { source_key: 'ontario_environmental_compliance_reports', source_record_id: 'environment:42', match_basis: 'EXACT_ADDRESS', source_address: '30 Gamma Rd', record_url: null, record_link_label: null, record_title: 'Gamma Plant', record_date: '2024-01-01', record_status: 'Assessment Underway', record_details: [{ label: 'Contaminant', value: 'Temperature' }] },
    ], relationships: [], aerial_review_rank: null, aerial_visual_similarity_score: null,
  }
  const empty = { chemical: '', reportingYear: '', aicApplication: '', aicStatus: '', healthStatus: '', environmentalRecord: '', company: '' }
  expect(propertyMatchesTorontoSourceFilters(property, { ...empty, healthStatus: 'Closed' })).toBe(true)
  expect(propertyMatchesTorontoSourceFilters(property, { ...empty, environmentalRecord: 'environment:42' })).toBe(true)
  expect(property.tower_evidence_status).toBe('NO_TOWER_ASSERTION')
})

test('builds a Toronto-specific CSV with scope and source-preserved roles', () => {
  const csv = buildTorontoCsv([{
    property_id: 'toronto-address-point:100', address_point_id: '100', display_address: '10 Alpha St', municipality: 'Toronto', longitude: -79.38, latitude: 43.65, identity_basis: 'CURRENT_ID', identity_confidence: 'HIGH', is_original_poc_property: true, tower_evidence_status: 'CONFIRMED_DOCUMENTARY_TOWER', source_keys: ['chemtrac_history'], source_links: [], relationships: [{ relationship: 'PROPERTY_MANAGER_OF', organization: 'Alpha Management', source_key: 'rentsafe', confidence: 'HIGH', basis: 'EXPLICIT_ROLE' }], aerial_review_rank: null, aerial_visual_similarity_score: null,
  }])
  expect(csv).toContain('poc_scope')
  expect(csv).toContain('"ORIGINAL_POC"')
  expect(csv).toContain('"chemtrac_history"')
  expect(csv).toContain('"PROPERTY_MANAGER_OF"')
})

test('builds a normalized property search document without inventing evidence', () => {
  const text = buildTorontoPropertySearchText({
    property_id: 'toronto-address-point:100', address_point_id: '100', display_address: '10 Alpha St', municipality: 'Toronto', longitude: -79.38, latitude: 43.65, identity_basis: 'CURRENT_ID', identity_confidence: 'HIGH', is_original_poc_property: true, tower_evidence_status: 'NO_TOWER_ASSERTION', source_keys: ['chemtrac_history'], source_links: [{ source_key: 'chemtrac_history', source_record_id: 'chem:1', match_basis: 'EXACT_ADDRESS', source_address: '10 Alpha St', record_url: null, record_link_label: null, record_title: 'Alpha facility', record_date: '2024', record_status: null, record_details: [{ label: 'Chemical', value: 'Nickel' }] }], relationships: [{ relationship: 'FACILITY_OPERATOR_AT', organization: 'Alpha Operations', source_key: 'chemtrac_history', confidence: 'HIGH', basis: 'PUBLISHED_ROLE' }], aerial_review_rank: null, aerial_visual_similarity_score: null,
  })
  expect(text).toContain('nickel')
  expect(text).toContain('alpha operations')
  expect(text).not.toContain('confirmed documentary tower')
})
