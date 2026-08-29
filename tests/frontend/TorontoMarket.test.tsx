import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { TorontoMarketPage } from '../../src/components/TorontoMarketPage'

vi.mock('../../src/components/TorontoMarketMap', () => ({ TorontoMarketMap: () => <div data-testid="toronto-map">Toronto map</div> }))
vi.mock('../../src/data/api', () => ({ loadTorontoMarket: vi.fn().mockResolvedValue({
  schema_version: 'toronto-market-app-1.0', generated_at: '2026-08-29T00:00:00Z', feature_status: 'ISOLATED_BETA',
  counts: { canonical_properties: 2, original_poc_properties: 177, original_poc_resolved: 172, original_poc_unresolved: 5, documentary_confirmed_properties: 1, strong_documentary_candidates: 0, aic_document_candidates: null, aerial_review_candidates: 1, source_links: 2, relationship_edges: 1 },
  true_market_coverage: { status: 'UNKNOWN_DENOMINATOR', coverage_percent: null }, source_coverage: {},
  limitations: ['AIC document transport is blocked.'], unresolved_poc: [{ property_key: 'poc-2', input_address: '1 York Rd', resolution_status: 'AMBIGUOUS_MUNICIPAL_ADDRESS', candidate_address_point_ids: ['1', '2'] }],
  properties: [
    { property_id: 'toronto-address-point:100', address_point_id: '100', display_address: '10 Alpha St', municipality: 'Toronto', longitude: -79.38, latitude: 43.65, identity_basis: 'CURRENT_ID', identity_confidence: 'HIGH', is_original_poc_property: true, tower_evidence_status: 'CONFIRMED_DOCUMENTARY_TOWER', source_keys: ['chemtrac_history'], source_links: [{ source_key: 'chemtrac_history', source_record_id: 'chem:1', match_basis: 'EXACT_ADDRESS', source_address: '10 Alpha St' }], relationships: [{ relationship: 'PROPERTY_MANAGER_OF', organization: 'Alpha Management', source_key: 'rentsafe', confidence: 'HIGH', basis: 'EXPLICIT_ROLE' }], aerial_review_rank: null, aerial_visual_similarity_score: null },
    { property_id: 'toronto-address-point:200', address_point_id: '200', display_address: '20 Beta Ave', municipality: 'Toronto', longitude: -79.4, latitude: 43.67, identity_basis: 'CURRENT_ID', identity_confidence: 'HIGH', is_original_poc_property: false, tower_evidence_status: 'AERIAL_REVIEW_CANDIDATE', source_keys: ['toronto_aic_applications'], source_links: [{ source_key: 'toronto_aic_applications', source_record_id: 'aic:1', match_basis: 'EXACT_ADDRESS', source_address: '20 Beta Ave' }], relationships: [], aerial_review_rank: 1, aerial_visual_similarity_score: 0.91 },
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
