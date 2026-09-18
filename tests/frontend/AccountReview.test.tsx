import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { AccountEvidenceWorkspace } from '../../src/components/AccountEvidenceWorkspace'
import { AccountDecisionSummary } from '../../src/components/AccountDecisionSummary'
import { collectAccountFirmRoleEvidence } from '../../src/domain/accountEvidence'
import type { SystemDetail, SystemSummary } from '../../src/types/data'
import type { SystemDetailWithDomesticWater } from '../../src/components/DomesticWaterSection'
import type { ProcurementBundle } from '../../src/types/procurement'

const api = vi.hoisted(() => ({ loadSystemDetail: vi.fn(), loadProcurement: vi.fn(), loadAccountProcurementManifest: vi.fn(), loadAccountProcurementPage: vi.fn() }))
vi.mock('../../src/data/api', () => api)
vi.mock('../../src/data/accountProcurement', () => api)
vi.mock('../../src/components/BuildingWaterSignalsSection', () => ({ BuildingWaterSignalsSection: () => null }))
vi.mock('../../src/components/DomesticWaterSection', () => ({ DomesticWaterSection: () => null }))
vi.mock('../../src/components/InstitutionalFacilitySection', () => ({ InstitutionalFacilitySection: () => null }))
vi.mock('../../src/components/LeadServiceLineSection', () => ({ LeadServiceLineSection: () => null }))
vi.mock('../../src/components/LegacyDobProjectSection', () => ({ LegacyDobProjectSection: () => null }))
vi.mock('../../src/components/OfficialSwoSnapshotSection', () => ({ OfficialSwoSnapshotSection: () => null }))

// Synthetic boundary fixture, not a claim about a real property or contract.
const detail = {
  metadata: {
    generated_at: '2026-09-18T10:31:33Z', rules_version: 'rules-review-fixture', priority_model_version: 'model-review-fixture',
    sources: [{ dataset_id: 'fixture-source', name: 'Fixture publisher', retrieved_at: '2026-09-17T00:00:00Z', source_record_count: 21, matched_record_count: 21, url: 'https://example.com/source' }],
    oath_match_basis: 'SUMMONS_NUMBER_EXACT', oath_requested_ticket_count: 11, oath_matched_ticket_count: 7,
    pluto_requested_bbl_count: 10, pluto_matched_bbl_count: 8,
  },
  identity: { system_id: 'REVIEW-1', bbl: '1000010001', bin: '1000010', active_equipment: 2, coordinate_status: 'MISSING' },
  building_context: { owner_name: 'FIXTURE OWNER', lot_area_sqft: 12345, building_area_sqft: 25000 },
  hpd_registration: { registration_id: 'REG-REVIEW', last_registration_date: '2024-10-12', contacts: [{
    registration_contact_id: 'CONTACT-REVIEW', corporation_name: 'FIXTURE MANAGEMENT LLC', person_name: 'PERSON PARITY FIXTURE',
    type: 'ManagingAgent', title: 'CONTACT TITLE FIXTURE', business_address: 'ADDRESS PARITY FIXTURE',
  }] },
  dob_activity_history: Array.from({ length: 21 }, (_, index) => ({
    job_filing_number: `DOB-REVIEW-${String(index + 1).padStart(2, '0')}`, job_description: `Source filing ${index + 1}`,
    activity_date: '2026-09-12', filing_status: 'STATUS PARITY FIXTURE', job_type: 'TYPE PARITY FIXTURE', initial_cost: 123456,
    filing_date: '2026-01-01', current_status_date: '2026-02-02', first_permit_date: '2026-03-03', approved_date: '2026-04-04', signoff_date: '2026-05-05',
    mechanical_systems: true, boiler_equipment: false, explicit_cooling_tower_mention: false, commercial_relevance: 'PROPERTY_PROJECT',
    applicant_business_name: 'APPLICANT PARITY FIXTURE', owner_business_name: 'DOB OWNER PARITY FIXTURE',
  })),
  inspection_history: [{ inspection_date: '2017-06-15', violation_count: 1, violations: [{ violation_text: 'HISTORICAL VIOLATION FIXTURE' }] }],
  oath_case_history: [], sample_history: { sample_count: 0, latest_sample_date: null },
  signals: [{ type: 'OFFICIAL_BUILDING_FOLLOWUP', title: 'Current official building follow-up', date: '2026-09-12', reason: 'CURRENT FOLLOWUP REASON FIXTURE', evidence_confidence: 'VERIFY' }],
} as unknown as SystemDetailWithDomesticWater

const bundle = {
  cityRecord: { notices: Array.from({ length: 21 }, (_, index) => ({
    schema_version: '1.0', procurement_id: `PROC-REVIEW-${String(index + 1).padStart(2, '0')}`, source: 'TEST', source_record_id: `${index}`,
    title: `Procurement parity ${index + 1}`, service_category: 'WATER_TREATMENT', service_confidence: 'CONFIRMED', retrieved_at: '2026-09-18',
    tower_account_system_ids: ['REVIEW-1'], tower_link_confidence: 'CONFIRMED',
  })) },
  checkbook: { contracts: [] }, nysAuthorities: { contracts: [] }, openBookWater: null, nychaWater: { records: [] },
  sourceErrors: { openBookWater: 'HTTP 503 fixture source failure' },
} as unknown as ProcurementBundle

beforeEach(() => {
  api.loadSystemDetail.mockResolvedValue(detail)
  api.loadAccountProcurementManifest.mockResolvedValue({
    system_id: 'REVIEW-1', generated_at: detail.metadata.generated_at,
    record_count: 21, pages: [{ record_count: 20 }, { record_count: 1 }],
    sources: [{ file: 'procurement-openbook-water.json', name: 'Open Book NY', status: 'UNAVAILABLE', reason: 'HTTP 503 fixture source failure', record_count: null }],
  })
  api.loadAccountProcurementPage.mockImplementation((_manifest: unknown, index: number) => Promise.resolve(bundle.cityRecord.notices.slice(index * 20, (index + 1) * 20)))
})
afterEach(cleanup)

async function openWorkspace() {
  const result = render(<AccountEvidenceWorkspace systemId="REVIEW-1" />)
  await screen.findByText('DOB NOW project activity')
  await screen.findByText('Procurement parity 1')
  result.container.querySelectorAll('details').forEach(element => { element.open = true })
  return result
}

test('all DOB filings remain reachable and retain original lifecycle fields', async () => {
  const { container } = await openWorkspace()
  const more = screen.getByRole('button', { name: /show.*more.*filing/i })
  fireEvent.click(more)
  expect(screen.getByText('DOB-REVIEW-21')).toBeInTheDocument()
  expect(container.textContent).toContain('STATUS PARITY FIXTURE')
  expect(container.textContent).toContain('TYPE PARITY FIXTURE')
  for (const field of ['Initial cost', 'Filing date', 'Current status date', 'First permit date', 'Approved date', 'Signoff date', 'Mechanical systems flag', 'Boiler equipment flag']) {
    expect(screen.getAllByText(field).length).toBeGreaterThan(0)
  }
})

test('property/contact and provenance fields survive Evidence grouping', async () => {
  const { container } = await openWorkspace()
  expect(screen.getByText('Lot area')).toBeInTheDocument()
  expect(container.textContent).toContain('12,345')
  expect(screen.getByText('PERSON PARITY FIXTURE')).toBeInTheDocument()
  expect(screen.getByText('FIXTURE MANAGEMENT LLC')).toBeInTheDocument()
  expect(container.textContent).toContain('Oct 12, 2024')
  expect(container.textContent).toContain('rules-review-fixture')
  expect(container.textContent).toContain('model-review-fixture')
  expect(container.textContent).toMatch(/7 matched of 11/)
  expect(container.textContent).toMatch(/8 matched of 10/)
})

test('partial procurement failure remains explicit without dropping available links or later records', async () => {
  const { container } = await openWorkspace()
  expect(screen.getByText('Procurement coverage incomplete.')).toBeInTheDocument()
  expect(container.textContent).toContain('HTTP 503 fixture source failure')
  expect(screen.getByText('Procurement parity 1')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /show.*more.*procurement/i }))
  expect(await screen.findByText('Procurement parity 21')).toBeInTheDocument()
})

test('observed firm chronology normalizes source date keys without changing raw evidence dates', () => {
  const fixture = { identity: { bin: '1000010' }, domestic_water: { self_report_history: [
    { inspection_by_firm: 'Fixture Water LLC', inspection_date: '10/06/2025', reporting_year: '2025' },
    { inspection_by_firm: 'Fixture Water LLC', inspection_date: '10/11/2023', reporting_year: '2023' },
  ] } } as unknown as SystemDetailWithDomesticWater
  expect(collectAccountFirmRoleEvidence(fixture).map(row => row.observedDate)).toEqual(['10/06/2025', '10/11/2023'])
})

test('Summary does not attach a historical violation to a different current primary signal', () => {
  const row = { system_id: 'REVIEW-1', priority_score: 12, evidence_confidence: 'VERIFY', active_equipment: 2,
    primary_signal: 'OFFICIAL_BUILDING_FOLLOWUP', recent_confirmed_violation: false, score_components: [], violation_types: ['HISTORICAL VIOLATION FIXTURE'],
  } as unknown as SystemSummary
  const { container } = render(<AccountDecisionSummary row={row} detail={detail as SystemDetail} historyEvents={[]} />)
  const trigger = container.querySelector('.account-decision-evidence-grid article') as HTMLElement
  expect(within(trigger).queryByText(/HISTORICAL VIOLATION FIXTURE/)).not.toBeInTheDocument()
  expect(trigger.textContent).toContain('Sep 12, 2026')
  expect(trigger.textContent).toContain('CURRENT FOLLOWUP REASON FIXTURE')
  expect(trigger.textContent).not.toContain('Jun 15, 2017')
})
