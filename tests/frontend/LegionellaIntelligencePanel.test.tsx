import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LegionellaIntelligencePanel } from '../../src/components/LegionellaIntelligencePanel'
import { relatedEvidence, officialDate, displayHeadline } from '../../src/utils/legionellaIntelligence'
import type { LegionellaAlertItem } from '../../src/types/enforcement'
import type { LegionellaPropertyMatches, NamedBuildingObservation } from '../../src/types/legionellaIntelligence'

const url = 'https://www.nyc.gov/site/doh/about/press/pr2026/bronx-notice.page'
const item: LegionellaAlertItem = { item_id: 'notice', url, title: 'bronx-legionnaires-update', agency: 'NYC Health Department', channel_key: 'PRESS', channel_kind: 'PRESS_RELEASE_INDEX', document_type: 'HTML', published_date: '2026-09-13', discovered_from: null, content_sha256: 'sha', content_bytes: 100, retrieved_at: '2026-09-15', match_terms: { legionella: true, cooling_tower: true } }
const observation: NamedBuildingObservation = { observation_id: 'obs', cluster_id: 'bronx-2026', cluster_status: 'INVESTIGATION_REPORTED', borough: 'BRONX', address: '234 E. 149th St.', bin: '2000001', result: 'PCR_POSITIVE', action: 'REMEDIATION_ORDER_REPORTED', completion: 'NOT_ESTABLISHED', document_date: '2026-09-13', event_date: '2026-09-12', source_url: url, related_article_urls: ['https://www.nyc.gov/earlier-notice'], retrieved_at: '2026-09-15', content_sha256: 'sha', match_basis: 'NORMALIZED_ADDRESS_BOROUGH_SINGLE_BIN', match_scope: 'NAMED_BUILDING_NOT_INDIVIDUAL_SYSTEM', system_ids: ['2000000660','2000000661'] }
const matches: LegionellaPropertyMatches = { domain: 'LEGIONELLA_PROPERTY_MATCHES', generated_at: '2026-09-15', registry_generated_at: '2026-09-15', evidence_boundary: 'Building scope only', matched_observations: [observation], unresolved: [], sources: [], summary: { named_buildings_matched: 1, systems_with_named_building_evidence: 2, matched_observation_count: 1, unresolved_observation_count: 0, systems_with_area_context: 40 } }
const alerts = { domain: 'LEGIONELLA_PUBLIC_HEALTH_ALERTS', generated_at: '2026-09-15', items: [item, ...Array.from({ length: 7 }, (_, n) => ({ ...item, item_id: `older-${n}`, url: `https://www.nyc.gov/older-${n}`, title: `Earlier notice ${n}`, published_date: `2026-08-${String(20-n).padStart(2,'0')}` }))], summary: { source_channel_count: 12, retrieval_error_count: 0 } }
function mockFetch(matchOk = true, alertOk = true) {
  vi.stubGlobal('fetch', vi.fn(async (input: string) => ({ ok: input.includes('property-matches') ? matchOk : alertOk, status: 503, json: async () => input.includes('property-matches') ? matches : alerts })))
}
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('Home official intelligence', () => {
  it('keeps collection dates separate from publication dates and makes slug titles readable', () => {
    expect(officialDate(null)).toBe('Not published')
    expect(officialDate('2026-09-13')).toBe('Sep 13, 2026')
    expect(displayHeadline(item)).toBe('Bronx Legionnaires Update')
  })
  it('deduplicates buildings and excludes ZIP-only systems from the linked count', () => {
    const result = relatedEvidence(item, { ...matches, matched_observations: [observation, { ...observation, observation_id: 'second' }] })
    expect(result.buildings).toHaveLength(1)
    expect(result.systems).toBe(2)
    expect(result.direct).toBe(true)
  })
  it('does not pretend an earlier cluster article itself names a building', () => {
    expect(relatedEvidence({ ...item, url: 'https://www.nyc.gov/earlier-notice' }, matches).direct).toBe(false)
    expect(relatedEvidence({ ...item, url: 'https://www.nyc.gov/unrelated-bronx-2015' }, matches).buildings).toHaveLength(0)
  })
  it('renders, searches, paginates and expands actual account links', async () => {
    mockFetch(); const user = userEvent.setup(); render(<LegionellaIntelligencePanel />)
    await screen.findByRole('link', { name: /Bronx Legionnaires Update/ })
    expect(screen.getByText('12 official channels')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Earlier notice/ })).toHaveLength(5)
    await user.click(screen.getByRole('button', { name: 'Next intelligence page' }))
    expect(screen.queryByRole('link', { name: /Bronx Legionnaires Update/ })).not.toBeInTheDocument()
    await user.type(screen.getByRole('searchbox', { name: 'Search official intelligence' }), '149th')
    await user.click(screen.getByRole('button', { name: /1 building/ }))
    expect(screen.getByRole('link', { name: 'Open tower account 2000000660' })).toHaveAttribute('href', '#/account/2000000660')
    expect(screen.getByText(/does not identify which system tested positive/)).toBeInTheDocument()
    expect(screen.getByText(/Cleaning order reported; completion not established/)).toBeInTheDocument()
  })
  it('keeps publications visible when the independent match index is unavailable', async () => {
    mockFetch(false); render(<LegionellaIntelligencePanel />)
    await screen.findByRole('link', { name: /Bronx Legionnaires Update/ })
    await screen.findByText(/Building matching is unavailable/)
    expect(screen.queryByRole('button', { name: /1 building/ })).not.toBeInTheDocument()
    expect(screen.getAllByText('Not assessed').length).toBeGreaterThan(0)
  })
  it('reports source failure instead of showing zero alerts', async () => {
    mockFetch(true, false); render(<LegionellaIntelligencePanel />)
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('not a report of zero alerts'))
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })
})
