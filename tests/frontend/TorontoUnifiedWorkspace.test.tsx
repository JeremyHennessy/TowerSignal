import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { TorontoUnifiedWorkspace } from '../../src/components/TorontoUnifiedWorkspace'

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
    toronto_aic_applications: { dataset_url: 'https://www.toronto.ca/', dataset_link_label: 'Open official dataset', link_level: 'DATASET_FALLBACK' },
  },
  limitations: ['Toronto cooling-tower market denominator remains unknown.'],
  unresolved_poc: [],
  properties: [
    {
      property_id: 'toronto-address-point:100', address_point_id: '100', display_address: '10 Alpha St', municipality: 'Toronto', longitude: -79.38, latitude: 43.65,
      identity_basis: 'CURRENT_ID', identity_confidence: 'HIGH', is_original_poc_property: true, tower_evidence_status: 'CONFIRMED_DOCUMENTARY_TOWER',
      source_keys: ['toronto_building_permits_active_targeted', 'chemtrac_history'],
      source_links: [
        { source_key: 'toronto_building_permits_active_targeted', source_record_id: 'permit:1', match_basis: 'EXACT_ADDRESS', source_address: '10 Alpha St', record_url: 'https://open.toronto.ca/permit/1', record_link_label: 'Open permit', record_title: '26 100000 MSA', record_date: '2026-08-01', record_status: 'Permit Issued', record_details: [{ label: 'Mechanical signals', value: 'cooling tower, chiller' }] },
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

function setRoute(hash: string) {
  act(() => {
    window.location.hash = hash
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  })
}

beforeEach(() => {
  window.localStorage.clear()
  window.location.hash = '#/toronto/home'
})

test('uses the NY-style Toronto route flow and drills Prospect into a full property profile with back navigation', async () => {
  const user = userEvent.setup()
  render(<TorontoUnifiedWorkspace explorer={<div>Market explorer</div>} mapExplorer={<div>Map explorer</div>} />)
  expect(await screen.findByRole('heading', { name: 'TowerSignal Toronto' })).toBeInTheDocument()

  setRoute('#/toronto/prospect')
  expect(await screen.findByRole('heading', { name: 'Prospect workspace' })).toBeInTheDocument()
  const alphaRow = screen.getByText('10 Alpha St').closest('tr')
  expect(alphaRow).not.toBeNull()
  await user.click(within(alphaRow as HTMLElement).getByRole('button', { name: 'Open profile →' }))

  expect(await screen.findByRole('heading', { name: '10 Alpha St' })).toBeInTheDocument()
  expect(window.location.hash).toContain('#/toronto/property/toronto-address-point%3A100')
  expect(screen.getByText('Source evidence')).toBeInTheDocument()
  expect(screen.getByText('Organizations & roles')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: '← Back' }))
  expect(await screen.findByRole('heading', { name: 'Prospect workspace' })).toBeInTheDocument()
})

test('drills company to organization profile, then cross-links to a property profile and back', async () => {
  const user = userEvent.setup()
  render(<TorontoUnifiedWorkspace explorer={<div>Market explorer</div>} mapExplorer={<div>Map explorer</div>} />)
  await screen.findByRole('heading', { name: 'TowerSignal Toronto' })

  setRoute('#/toronto/companies')
  expect(await screen.findByRole('heading', { name: 'Companies' })).toBeInTheDocument()
  const companyRow = screen.getByText('Alpha Management').closest('tr')
  expect(companyRow).not.toBeNull()
  await user.click(within(companyRow as HTMLElement).getByRole('button', { name: 'Open company →' }))

  expect(await screen.findByRole('heading', { name: 'Alpha Management' })).toBeInTheDocument()
  expect(screen.getByText('Linked Toronto properties')).toBeInTheDocument()
  const alphaPropertyRow = screen.getByText('10 Alpha St').closest('tr')
  expect(alphaPropertyRow).not.toBeNull()
  await user.click(within(alphaPropertyRow as HTMLElement).getByRole('button', { name: 'Open profile →' }))
  expect(await screen.findByRole('heading', { name: '10 Alpha St' })).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: '← Back' }))
  expect(await screen.findByRole('heading', { name: 'Alpha Management' })).toBeInTheDocument()
})

test('drills multi-property portfolio and keeps company/portfolio views cross-linked', async () => {
  const user = userEvent.setup()
  render(<TorontoUnifiedWorkspace explorer={<div>Market explorer</div>} mapExplorer={<div>Map explorer</div>} />)
  await screen.findByRole('heading', { name: 'TowerSignal Toronto' })

  setRoute('#/toronto/portfolios')
  expect(await screen.findByRole('heading', { name: 'Portfolios' })).toBeInTheDocument()
  const portfolioRow = screen.getByText('Alpha Management').closest('tr')
  expect(portfolioRow).not.toBeNull()
  await user.click(within(portfolioRow as HTMLElement).getByRole('button', { name: 'Open portfolio →' }))
  expect(await screen.findByRole('heading', { name: 'Alpha Management' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Open company view' })).toBeInTheDocument()
  expect(screen.getByText('20 Beta Ave')).toBeInTheDocument()
})

test('keeps Monitor and Toronto Changes evidence-limited while Market and Map are real routes', async () => {
  render(<TorontoUnifiedWorkspace explorer={<div>Market explorer</div>} mapExplorer={<div>Map explorer</div>} />)
  await screen.findByRole('heading', { name: 'TowerSignal Toronto' })

  setRoute('#/toronto/monitor')
  expect(await screen.findByRole('heading', { name: 'Monitor workspace' })).toBeInTheDocument()
  expect(screen.getByText(/does not yet publish a validated snapshot-to-snapshot event stream/i)).toBeInTheDocument()

  setRoute('#/toronto/changes')
  expect(await screen.findByRole('heading', { name: 'Toronto Changes' })).toBeInTheDocument()
  expect(screen.getByText('No fabricated Toronto change events.')).toBeInTheDocument()

  setRoute('#/toronto/map')
  expect(await screen.findByText('Map explorer')).toBeInTheDocument()

  setRoute('#/toronto/market')
  expect(await screen.findByText('Market explorer')).toBeInTheDocument()
})
