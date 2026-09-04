import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { TorontoParityShell } from '../../src/components/TorontoParityShell'

const payload = vi.hoisted(() => ({
  schema_version: 'toronto-market-app-1.0',
  generated_at: '2026-09-04T00:00:00Z',
  feature_status: 'ISOLATED_BETA',
  counts: {
    canonical_properties: 3,
    original_poc_properties: 177,
    original_poc_resolved: 175,
    original_poc_unresolved: 2,
    documentary_confirmed_properties: 2,
    strong_documentary_candidates: 0,
    aic_document_candidates: 1,
    aerial_review_candidates: 0,
    source_links: 5,
    record_level_source_links: 4,
    official_source_families: 4,
    relationship_edges: 2,
  },
  true_market_coverage: { status: 'UNKNOWN_DENOMINATOR', coverage_percent: null },
  source_coverage: {
    toronto_building_permits_active_targeted: {
      status: 'JOINED', source_records: 10, records_with_property_address: 10, matched_records: 9, matched_canonical_properties: 2, unmatched_source_records: 1,
      identity_limitation: 'Exact deterministic address-point match only.',
    },
    chemtrac_history: {
      status: 'JOINED', source_records: 20, records_with_property_address: 20, matched_records: 12, matched_canonical_properties: 2, unmatched_source_records: 8,
    },
  },
  source_catalog: {
    toronto_building_permits_active_targeted: { dataset_url: 'https://open.toronto.ca/', dataset_link_label: 'Open official dataset', link_level: 'DATASET_FALLBACK' },
    chemtrac_history: { dataset_url: 'https://open.toronto.ca/', dataset_link_label: 'Open official dataset', link_level: 'DATASET_FALLBACK' },
  },
  limitations: ['Toronto cooling-tower market denominator remains unknown.'],
  unresolved_poc: [],
  properties: [
    {
      property_id: 'toronto-address-point:100', address_point_id: '100', display_address: '10 Alpha St', municipality: 'Toronto', longitude: -79.38, latitude: 43.65,
      identity_basis: 'CURRENT_ID', identity_confidence: 'HIGH', is_original_poc_property: true, tower_evidence_status: 'CONFIRMED_DOCUMENTARY_TOWER',
      source_keys: ['toronto_building_permits_active_targeted', 'chemtrac_history'],
      source_links: [
        { source_key: 'toronto_building_permits_active_targeted', source_record_id: 'permit:1', match_basis: 'EXACT_ADDRESS', source_address: '10 Alpha St', record_url: null, record_link_label: null, record_title: '26 100000 MSA', record_date: '2026-08-01', record_status: 'Permit Issued', record_details: [{ label: 'Mechanical signals', value: 'cooling tower, chiller' }] },
        { source_key: 'chemtrac_history', source_record_id: 'chem:1', match_basis: 'EXACT_ADDRESS', source_address: '10 Alpha St', record_url: null, record_link_label: null, record_title: 'Alpha Facility', record_date: '2024', record_status: null, record_details: [] },
      ],
      relationships: [{ relationship: 'PROPERTY_MANAGER_OF', organization: 'Alpha Management', source_key: 'rentsafe_registration', confidence: 'HIGH', basis: 'EXPLICIT_ROLE' }],
      aerial_review_rank: null, aerial_visual_similarity_score: null,
    },
    {
      property_id: 'toronto-address-point:200', address_point_id: '200', display_address: '20 Beta Ave', municipality: 'Toronto', longitude: -79.4, latitude: 43.67,
      identity_basis: 'CURRENT_ID', identity_confidence: 'HIGH', is_original_poc_property: false, tower_evidence_status: 'CONFIRMED_DOCUMENTARY_TOWER',
      source_keys: ['chemtrac_history'],
      source_links: [{ source_key: 'chemtrac_history', source_record_id: 'chem:2', match_basis: 'EXACT_ADDRESS', source_address: '20 Beta Ave', record_url: null, record_link_label: null, record_title: 'Beta Facility', record_date: '2024', record_status: null, record_details: [] }],
      relationships: [{ relationship: 'PROPERTY_MANAGER_OF', organization: 'Alpha Management', source_key: 'rentsafe_registration', confidence: 'HIGH', basis: 'EXPLICIT_ROLE' }],
      aerial_review_rank: null, aerial_visual_similarity_score: null,
    },
    {
      property_id: 'toronto-address-point:300', address_point_id: '300', display_address: '30 Gamma Rd', municipality: 'Toronto', longitude: -79.42, latitude: 43.7,
      identity_basis: 'CURRENT_ID', identity_confidence: 'HIGH', is_original_poc_property: false, tower_evidence_status: 'AIC_DOCUMENT_CANDIDATE',
      source_keys: ['toronto_aic_applications'],
      source_links: [{ source_key: 'toronto_aic_applications', source_record_id: 'aic:1', match_basis: 'EXACT_ADDRESS', source_address: '30 Gamma Rd', record_url: null, record_link_label: null, record_title: '26 123456 STE 01 OZ', record_date: '2026-07-01', record_status: 'Under review', record_details: [] }],
      relationships: [], aerial_review_rank: null, aerial_visual_similarity_score: null,
    },
  ],
}))

vi.mock('../../src/data/api', () => ({ loadTorontoMarket: vi.fn().mockResolvedValue(payload) }))

beforeEach(() => {
  window.location.hash = '#/toronto'
  window.localStorage.clear()
})

test('adds a Toronto prospect workspace without presenting the ranking as compliance', async () => {
  const user = userEvent.setup()
  render(<TorontoParityShell explorer={<div>Market explorer</div>} />)
  expect(screen.getByText('Market explorer')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Prospects' }))
  expect(await screen.findByRole('heading', { name: 'Prospect workspace' })).toBeInTheDocument()
  expect(screen.getByText(/This attention index is not a regulatory or compliance score/i)).toBeInTheDocument()
  expect(screen.getByText('10 Alpha St')).toBeInTheDocument()
  expect(screen.getAllByText('Commercial ranking only').length).toBeGreaterThan(0)
  expect(screen.queryByText(/NYC priority score/i)).not.toBeInTheDocument()
})

test('surfaces source-backed opportunity timing and opens the existing evidence route', async () => {
  const user = userEvent.setup()
  render(<TorontoParityShell explorer={<div>Market explorer</div>} />)
  await user.click(screen.getByRole('button', { name: 'Opportunities' }))
  expect(await screen.findByRole('heading', { name: 'Opportunity queues' })).toBeInTheDocument()
  expect(screen.getAllByText('Confirmed tower + mechanical project timing').length).toBeGreaterThan(0)

  const alpha = screen.getByText('10 Alpha St').closest('article')
  expect(alpha).not.toBeNull()
  await user.click(within(alpha as HTMLElement).getByRole('button', { name: 'Open evidence' }))
  expect(window.location.hash).toContain('toronto-address-point%3A100')
  expect(screen.getByText('Market explorer')).toBeInTheDocument()
})

test('aggregates source-backed companies and multi-property portfolios', async () => {
  const user = userEvent.setup()
  render(<TorontoParityShell explorer={<div>Market explorer</div>} />)

  await user.click(screen.getByRole('button', { name: 'Companies' }))
  expect(await screen.findByRole('heading', { name: 'Companies' })).toBeInTheDocument()
  const companyRows = screen.getAllByRole('row')
  expect(companyRows.some(row => within(row).queryByText('Alpha Management'))).toBe(true)

  await user.click(screen.getByRole('button', { name: 'Portfolios' }))
  expect(await screen.findByRole('heading', { name: 'Portfolios' })).toBeInTheDocument()
  const alphaRow = screen.getByText('Alpha Management').closest('tr')
  expect(alphaRow).not.toBeNull()
  expect(within(alphaRow as HTMLElement).getAllByText('2').length).toBeGreaterThanOrEqual(2)
})

test('keeps the Toronto watchlist local to the browser and exposes source health', async () => {
  const user = userEvent.setup()
  render(<TorontoParityShell explorer={<div>Market explorer</div>} />)

  await user.click(screen.getByRole('button', { name: 'Prospects' }))
  await screen.findByRole('heading', { name: 'Prospect workspace' })
  const alphaRow = screen.getByText('10 Alpha St').closest('tr')
  expect(alphaRow).not.toBeNull()
  await user.click(within(alphaRow as HTMLElement).getByRole('button', { name: 'Watch' }))
  expect(JSON.parse(window.localStorage.getItem('towersignal-toronto-watchlist-v1') ?? '[]')).toContain('toronto-address-point:100')

  await user.click(screen.getByRole('button', { name: /Watchlist/ }))
  expect(await screen.findByRole('heading', { name: 'Watchlist' })).toBeInTheDocument()
  expect(screen.getByText('10 Alpha St')).toBeInTheDocument()
  expect(screen.getByText(/stays in this browser/i)).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Sources' }))
  expect(await screen.findByRole('heading', { name: 'Source health & coverage' })).toBeInTheDocument()
  expect(screen.getByText('Active building permits')).toBeInTheDocument()
  expect(screen.getByText('90%')).toBeInTheDocument()
  expect(screen.getByText(/Exact deterministic address-point match only/i)).toBeInTheDocument()
})
