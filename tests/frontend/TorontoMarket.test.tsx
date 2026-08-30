import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { buildTorontoCsv, TorontoMarketPage } from '../../src/components/TorontoMarketPage'

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
    { property_id: 'toronto-address-point:100', address_point_id: '100', display_address: '10 Alpha St', municipality: 'Toronto', longitude: -79.38, latitude: 43.65, identity_basis: 'CURRENT_ID', identity_confidence: 'HIGH', is_original_poc_property: true, tower_evidence_status: 'CONFIRMED_DOCUMENTARY_TOWER', source_keys: ['chemtrac_history'], source_links: [{ source_key: 'chemtrac_history', source_record_id: 'chem:1', match_basis: 'EXACT_ADDRESS', source_address: '10 Alpha St', record_url: 'https://secure.toronto.ca/nm/api/individual/notice/123.do', record_link_label: 'Open public notice', record_title: 'Alpha facility', record_date: '2024', record_status: null, record_details: [{ label: 'Chemical', value: 'Nickel' }] }], relationships: [{ relationship: 'PROPERTY_MANAGER_OF', organization: 'Alpha Management', source_key: 'rentsafe', confidence: 'HIGH', basis: 'EXPLICIT_ROLE' }], aerial_review_rank: null, aerial_visual_similarity_score: null },
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

  await user.click(within(detail).getByRole('button', { name: 'Close Toronto property detail' }))
  await user.click(screen.getByRole('button', { name: '20 Beta Ave' }))
  expect(screen.getByText(/No durable row-level URL is published/)).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Open current AIC application search ↗' })).toHaveAttribute('href', 'https://www.toronto.ca/city-government/planning-development/application-details/')
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
