import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../../src/App'

vi.mock('../../src/components/TowerMap', () => ({ TowerMap: () => <div data-testid="map">Map</div> }))

const payload = {
  schema_version: '1.0',
  metadata: {
    generated_at: '2026-08-21T20:00:00Z', snapshot_date: '2026-08-21', normalized_system_count: 2,
    source_duplicate_registration_rows: 1, source_missing_registration_system_id_rows: 0, invalid_coordinate_system_count: 0,
    oath_requested_ticket_count: 1, oath_matched_ticket_count: 1, oath_unmatched_ticket_count: 0, oath_match_basis: 'SUMMONS_NUMBER_EXACT',
    rules_version: 'nyc-2026-05-08', priority_model_version: '1.0',
    sources: [
      { dataset_id:'y4fw-iqfr', name:'NYC Cooling Tower Registrations', retrieved_at:'2026-08-21T20:00:00Z', source_record_count:5900, source_last_updated_at:'2026-08-20T00:00:00Z', url:'https://example.test/a' },
      { dataset_id:'f9wb-g8mb', name:'NYC Cooling Tower System Inspection Results', retrieved_at:'2026-08-21T20:00:00Z', source_record_count:124000, source_last_updated_at:'2026-07-20T00:00:00Z', url:'https://example.test/b' },
      { dataset_id:'jz4z-kudi', name:'OATH Hearings Division Case Status', retrieved_at:'2026-08-21T20:00:00Z', source_record_count:1, matched_record_count:1, source_query_scope:'Exact ticket_number queries', source_last_updated_at:'2026-08-19T00:00:00Z', url:'https://example.test/c' },
    ],
  },
  summary: { registered_systems:2, active_equipment:4, potential_sampling_gaps:1, recent_confirmed_violations:1, systems_with_oath_cases:1 },
  systems: [
    { system_id:'SYS-1',bin:'1',bbl:'1',address:'10 ALPHA ST',borough:'Manhattan',zip:'10001',active_equipment:3,latitude:40.75,longitude:-73.99,coordinate_status:'VALID',latest_sample_date:'2026-07-01',days_since_latest_sample:51,latest_inspection_date:'2026-08-01',latest_inspection_type:'Cycle',confirmed_violation:true,recent_confirmed_violation:true,violation_types:['Critical'],signal_types:['CONFIRMED_RECENT_VIOLATION','POTENTIAL_SAMPLING_GAP'],primary_signal:'CONFIRMED_RECENT_VIOLATION',evidence_confidence:'CONFIRMED',priority_score:88,score_components:[{points:40,reason:'confirmed recent violation'}],oath_case_count:1 },
    { system_id:'SYS-2',bin:'2',bbl:'2',address:'20 BETA AVE',borough:'Queens',zip:'11101',active_equipment:1,latitude:40.74,longitude:-73.94,coordinate_status:'VALID',latest_sample_date:'2026-08-15',days_since_latest_sample:6,latest_inspection_date:null,latest_inspection_type:null,confirmed_violation:false,recent_confirmed_violation:false,violation_types:[],signal_types:[],primary_signal:'NO_CURRENT_SIGNAL',evidence_confidence:'STRONG_SIGNAL',priority_score:0,score_components:[],oath_case_count:0 },
  ],
}

const changes = {
  history_schema_version:'1.0',
  history_started_at:'2026-08-20T20:00:00Z',
  observed_at:'2026-08-21T20:00:00Z',
  baseline_initialized:false,
  new_event_count:1,
  events:[{
    event_type:'SAMPLE_REPORTED',system_id:'SYS-1',bbl:'1',bin:'1',address:'10 ALPHA ST',borough:'Manhattan',detected_at:'2026-08-21T20:00:00Z',source_observation_date:'2026-08-21',previous_value:null,new_value:'2026-08-21',source:'NYC_COOLING_TOWER_REGISTRATIONS',evidence_basis:'SYSTEM_ID_EXACT',priority_score:88,evidence_confidence:'CONFIRMED',contact_available:true,
  }],
}

const detail = {
  schema_version:'1.0', metadata:payload.metadata,
  identity:{ system_id:'SYS-1',bin:'1',bbl:'1',address:'10 ALPHA ST',borough:'Manhattan',zip:'10001',active_equipment:3,latitude:40.75,longitude:-73.99,coordinate_status:'VALID',source_latitude_raw:'40.75',source_longitude_raw:'-73.99' },
  sample_history:{ source_raw:'07/01/2026',dates:['2026-07-01'],malformed_values:[],latest_sample_date:'2026-07-01',previous_sample_date:null,latest_sample_interval_days:null,intervals_days:[],sample_count:1 },
  signals:[{ type:'POTENTIAL_SAMPLING_GAP',title:'Potential sampling gap',evidence_confidence:'VERIFY',fact_class:'COMMERCIAL_SIGNAL',date:'2026-07-01',reason:'Operating status must be verified.' }],
  inspection_history:[],
  oath_case_history:[{ ticket_number:'0880900460',ticket_number_source_raw:'0880900460',match_basis:'SUMMONS_NUMBER_EXACT',issuing_agency:'DOHMH',violation_date:'2026-06-10',violation_location:{borough:'Manhattan',block:'1',lot:'1',house:'10',street_name:'ALPHA ST',zip:'10001'},hearing_status:'HEARING COMPLETED',hearing_result:'IN VIOLATION',hearing_date:'2026-07-01',decision_date:'2026-07-15',compliance_status:null,violation_description:'Cooling tower violation',penalty_imposed:1000,paid_amount:250,additional_penalties_or_late_fees:0,balance_due:750,total_violation_amount:1000,date_judgment_docketed:null,charges:[{code:'CT01',code_section:'24 RCNY 8',description:'Cooling tower violation',infraction_amount:1000}] }],
  scoring:{ score:88,components:[{points:40,reason:'confirmed recent violation'}],priority_model_version:'1.0' },
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    const responsePayload = url.includes('/details/') ? detail : url.includes('/data/changes.json') ? changes : payload
    return Promise.resolve({ ok:true, json:() => Promise.resolve(responsePayload) }) as unknown as Promise<Response>
  }))
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: vi.fn().mockResolvedValue(undefined) } })
})

afterEach(() => vi.unstubAllGlobals())

test('renders the real-data dashboard shell after dataset load', async () => {
  render(<App />)
  expect(await screen.findByText('Find cooling-tower systems worth investigating today.')).toBeInTheDocument()
  expect(screen.getByText((_, element) => element?.textContent === '2 matching systems')).toBeInTheDocument()
  expect(screen.getByText('Systems with OATH cases')).toBeInTheDocument()
  expect(screen.getByRole('button', { name:'Changes' })).toBeInTheDocument()
})

test('filters records and opens details', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('10 ALPHA ST')
  await user.type(screen.getByPlaceholderText('Address, system ID, BIN…'), 'BETA')
  expect(screen.queryByText('10 ALPHA ST')).not.toBeInTheDocument()
  expect(screen.getByText('20 BETA AVE')).toBeInTheDocument()
  await user.clear(screen.getByPlaceholderText('Address, system ID, BIN…'))
  await user.click(screen.getByText('10 ALPHA ST'))
  await waitFor(() => expect(screen.getByRole('heading', { name:'Identity' })).toBeInTheDocument())
  const detailPanel = screen.getByRole('complementary', { name: 'Selected cooling tower detail' })
  expect(within(detailPanel).getByText('Potential sampling gap')).toBeInTheDocument()
  expect(within(detailPanel).getByRole('heading', { name:'OATH case lifecycle' })).toBeInTheDocument()
  expect(within(detailPanel).getByRole('heading', { name:'TowerSignal History' })).toBeInTheDocument()
  expect(within(detailPanel).getByText(/Ticket 0880900460/)).toBeInTheDocument()
  expect(within(detailPanel).getByText('IN VIOLATION')).toBeInTheDocument()
})

test('Manhattan quick filter matches title-case source borough values', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('10 ALPHA ST')
  await user.click(screen.getByRole('button', { name: 'Manhattan' }))
  expect(screen.getByText('10 ALPHA ST')).toBeInTheDocument()
  expect(screen.queryByText('20 BETA AVE')).not.toBeInTheDocument()
  expect(screen.getByText((_, element) => element?.textContent === '1 matching systems')).toBeInTheDocument()
})

test('OATH quick filter returns only exact-matched systems', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('10 ALPHA ST')
  await user.click(screen.getByRole('button', { name: 'OATH cases' }))
  expect(screen.getByText('10 ALPHA ST')).toBeInTheDocument()
  expect(screen.queryByText('20 BETA AVE')).not.toBeInTheDocument()
  expect(screen.getByText((_, element) => element?.textContent === '1 matching systems')).toBeInTheDocument()
})

test('opens the Changes product mode with source-backed change evidence', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('10 ALPHA ST')
  await user.click(screen.getByRole('button', { name:'Changes' }))
  expect(screen.getByRole('heading', { name:'What changed?' })).toBeInTheDocument()
  expect(screen.getAllByText('New public sample reported')).toHaveLength(2)
  expect(screen.getByText('Source: NYC_COOLING_TOWER_REGISTRATIONS')).toBeInTheDocument()
  expect(screen.getByText('Evidence: SYSTEM_ID_EXACT')).toBeInTheDocument()
})
