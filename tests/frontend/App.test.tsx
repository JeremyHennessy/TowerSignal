import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../../src/App'

vi.mock('../../src/components/TowerMap', () => ({ TowerMap: () => <div data-testid="map">Map</div> }))

const payload = {
  schema_version: '1.0',
  metadata: {
    generated_at: '2026-08-21T20:00:00Z', snapshot_date: '2026-08-21', normalized_system_count: 2,
    source_duplicate_registration_rows: 1, source_missing_registration_system_id_rows: 0, rules_version: 'nyc-2026-05-08', priority_model_version: '1.0',
    sources: [
      { dataset_id:'y4fw-iqfr', name:'NYC Cooling Tower Registrations', retrieved_at:'2026-08-21T20:00:00Z', source_record_count:5900, source_last_updated_at:'2026-08-20T00:00:00Z', url:'https://example.test/a' },
      { dataset_id:'f9wb-g8mb', name:'NYC Cooling Tower System Inspection Results', retrieved_at:'2026-08-21T20:00:00Z', source_record_count:124000, source_last_updated_at:'2026-07-20T00:00:00Z', url:'https://example.test/b' },
    ],
  },
  summary: { registered_systems:2, active_equipment:4, potential_sampling_gaps:1, recent_confirmed_violations:1 },
  systems: [
    { system_id:'SYS-1',bin:'1',bbl:'1',address:'10 ALPHA ST',borough:'Manhattan',zip:'10001',active_equipment:3,latitude:40.75,longitude:-73.99,latest_sample_date:'2026-07-01',days_since_latest_sample:51,latest_inspection_date:'2026-08-01',latest_inspection_type:'Cycle',confirmed_violation:true,recent_confirmed_violation:true,violation_types:['Critical'],signal_types:['CONFIRMED_RECENT_VIOLATION','POTENTIAL_SAMPLING_GAP'],primary_signal:'CONFIRMED_RECENT_VIOLATION',evidence_confidence:'CONFIRMED',priority_score:88,score_components:[{points:40,reason:'confirmed recent violation'}] },
    { system_id:'SYS-2',bin:'2',bbl:'2',address:'20 BETA AVE',borough:'Queens',zip:'11101',active_equipment:1,latitude:40.74,longitude:-73.94,latest_sample_date:'2026-08-15',days_since_latest_sample:6,latest_inspection_date:null,latest_inspection_type:null,confirmed_violation:false,recent_confirmed_violation:false,violation_types:[],signal_types:[],primary_signal:'NO_CURRENT_SIGNAL',evidence_confidence:'STRONG_SIGNAL',priority_score:0,score_components:[] },
  ],
}

const detail = {
  schema_version:'1.0', metadata:payload.metadata,
  identity:{ system_id:'SYS-1',bin:'1',bbl:'1',address:'10 ALPHA ST',borough:'Manhattan',zip:'10001',active_equipment:3,latitude:40.75,longitude:-73.99 },
  sample_history:{ source_raw:'07/01/2026',dates:['2026-07-01'],malformed_values:[],latest_sample_date:'2026-07-01',previous_sample_date:null,latest_sample_interval_days:null,intervals_days:[],sample_count:1 },
  signals:[{ type:'POTENTIAL_SAMPLING_GAP',title:'Potential sampling gap',evidence_confidence:'VERIFY',fact_class:'COMMERCIAL_SIGNAL',date:'2026-07-01',reason:'Operating status must be verified.' }],
  inspection_history:[], scoring:{ score:88,components:[{points:40,reason:'confirmed recent violation'}],priority_model_version:'1.0' },
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    return Promise.resolve({ ok:true, json:() => Promise.resolve(url.includes('/details/') ? detail : payload) }) as unknown as Promise<Response>
  }))
  Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } })
})

afterEach(() => vi.unstubAllGlobals())

test('renders the real-data dashboard shell after dataset load', async () => {
  render(<App />)
  expect(await screen.findByText('Find cooling-tower systems worth investigating today.')).toBeInTheDocument()
  expect(screen.getByText((_, element) => element?.textContent === '2 matching systems')).toBeInTheDocument()
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
})

test('Manhattan quick filter matches title-case source borough values', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('10 ALPHA ST')
  await user.click(screen.getByRole('button', { name: 'Manhattan' }))
  expect(screen.getByText('10 ALPHA ST')).toBeInTheDocument()
  expect(screen.queryByText('20 BETA AVE')).not.toBeInTheDocument()
  expect(screen.getByText((_, element) => element?.textContent === '1 matching system')).toBeInTheDocument()
})
