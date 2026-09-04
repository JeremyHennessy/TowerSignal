import { expect, test, vi } from 'vitest'
import type { TorontoProperty } from '../../src/types/toronto'
import { buildTorontoCompanyCsv, buildTorontoLeadSummary, buildTorontoProspectCsv, copyText, downloadCsv } from '../../src/utils/torontoCommercialExport'

const property: TorontoProperty = {
  property_id: 'toronto-address-point:100',
  address_point_id: '100',
  display_address: '10 Alpha St, Toronto',
  municipality: 'Toronto',
  longitude: -79.38,
  latitude: 43.65,
  identity_basis: 'CURRENT_ID',
  identity_confidence: 'HIGH',
  is_original_poc_property: true,
  tower_evidence_status: 'CONFIRMED_DOCUMENTARY_TOWER',
  source_keys: ['chemtrac_history', 'toronto_building_permits_active_targeted'],
  source_links: [],
  relationships: [{ relationship: 'PROPERTY_MANAGER_OF', organization: 'Alpha Management', source_key: 'rentsafe_registration', confidence: 'HIGH', basis: 'EXPLICIT_ROLE' }],
  aerial_review_rank: null,
  aerial_visual_similarity_score: null,
}

const prospect = {
  property,
  attention: 82,
  tier: 'HIGH' as const,
  factors: ['Documentary-confirmed tower', 'Mechanical permit signal'],
  opportunities: ['Confirmed tower + mechanical project timing'],
}

test('builds an auditable prospect CSV with source and relationship context', () => {
  const csv = buildTorontoProspectCsv([prospect])
  expect(csv).toContain('Property ID,Address Point ID,Address,Attention,Tier,Tower evidence')
  expect(csv).toContain('toronto-address-point:100')
  expect(csv).toContain('Alpha Management')
  expect(csv).toContain('chemtrac_history | toronto_building_permits_active_targeted')
})

test('builds a lead summary with explicit commercial-score and verification caveats', () => {
  const summary = buildTorontoLeadSummary(prospect)
  expect(summary).toContain('Commercial attention: 82/100 (HIGH); this is not a regulatory or compliance score.')
  expect(summary).toContain('Alpha Management — PROPERTY MANAGER OF')
  expect(summary).toContain('Verify the cited source records')
})

test('builds company export rows without inventing roles', () => {
  const csv = buildTorontoCompanyCsv([{ name: 'Alpha Management', propertyIds: new Set(['a', 'b']), confirmedPropertyIds: new Set(['a']), highAttentionPropertyIds: new Set(['a']), roles: new Set(['PROPERTY_MANAGER_OF']), sources: new Set(['rentsafe_registration']) }])
  expect(csv).toContain('Alpha Management,2,1,1,PROPERTY_MANAGER_OF,rentsafe_registration')
})

test('downloads CSV through a temporary object URL', () => {
  const createObjectURL = vi.fn(() => 'blob:test')
  const revokeObjectURL = vi.fn()
  vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
  downloadCsv('prospects.csv', 'a,b\r\n1,2\r\n')
  expect(createObjectURL).toHaveBeenCalledOnce()
  expect(click).toHaveBeenCalledOnce()
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:test')
  click.mockRestore()
  vi.unstubAllGlobals()
})

test('copies lead text with the clipboard API when available', async () => {
  const writeText = vi.fn().mockResolvedValue(undefined)
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
  await copyText('lead summary')
  expect(writeText).toHaveBeenCalledWith('lead summary')
})
