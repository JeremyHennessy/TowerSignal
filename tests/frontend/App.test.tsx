import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from '../../src/App'

vi.mock('../../src/components/TowerMap', () => ({ TowerMap: () => <div data-testid="map">Map</div> }))
vi.mock('../../src/components/NysTowerMap', () => ({ NysTowerMap: () => <div data-testid="nys-map">NYS Map</div> }))

const payload = {
  schema_version: '1.0',
  metadata: {
    generated_at: '2026-08-21T20:00:00Z', snapshot_date: '2026-08-21', normalized_system_count: 2,
    source_duplicate_registration_rows: 1, source_missing_registration_system_id_rows: 0, invalid_coordinate_system_count: 0,
    oath_requested_ticket_count: 1, oath_matched_ticket_count: 1, oath_unmatched_ticket_count: 0, oath_match_basis: 'SUMMONS_NUMBER_EXACT',
    dob_requested_bbl_count: 2, dob_matched_bbl_count: 1, dob_matched_filing_count: 1, dob_explicit_cooling_tower_filing_count: 1, dob_mechanical_or_boiler_filing_count: 1,
    rules_version: 'nyc-2026-05-08', priority_model_version: '1.0',
    sources: [
      { dataset_id:'y4fw-iqfr', name:'NYC Cooling Tower Registrations', retrieved_at:'2026-08-21T20:00:00Z', source_record_count:5900, source_last_updated_at:'2026-08-20T00:00:00Z', url:'https://example.test/a' },
      { dataset_id:'f9wb-g8mb', name:'NYC Cooling Tower System Inspection Results', retrieved_at:'2026-08-21T20:00:00Z', source_record_count:124000, source_last_updated_at:'2026-07-20T00:00:00Z', url:'https://example.test/b' },
      { dataset_id:'jz4z-kudi', name:'OATH Hearings Division Case Status', retrieved_at:'2026-08-21T20:00:00Z', source_record_count:1, matched_record_count:1, source_query_scope:'Exact ticket_number queries', source_last_updated_at:'2026-08-19T00:00:00Z', url:'https://example.test/c' },
      { dataset_id:'w9ak-ipjd', name:'DOB NOW: Build – Job Application Filings', retrieved_at:'2026-08-21T20:00:00Z', source_record_count:940000, matched_record_count:1, source_query_scope:'Exact BBL subsets', source_last_updated_at:'2026-08-21T00:00:00Z', url:'https://example.test/d' },
    ],
  },
  summary: { registered_systems:2, active_equipment:4, potential_sampling_gaps:1, recent_confirmed_violations:1, systems_with_oath_cases:1, systems_with_pluto_context:2, systems_with_dob_activity:1, systems_with_recent_dob_activity:1, systems_with_explicit_cooling_tower_dob_activity:1 },
  systems: [
    { system_id:'SYS-1',bin:'1',bbl:'1',address:'10 ALPHA ST',borough:'Manhattan',zip:'10001',active_equipment:3,latitude:40.75,longitude:-73.99,coordinate_status:'VALID',latest_sample_date:'2026-07-01',days_since_latest_sample:51,latest_inspection_date:'2026-08-01',latest_inspection_type:'Cycle',confirmed_violation:true,recent_confirmed_violation:true,violation_types:['Critical'],signal_types:['CONFIRMED_RECENT_VIOLATION','POTENTIAL_SAMPLING_GAP'],primary_signal:'CONFIRMED_RECENT_VIOLATION',evidence_confidence:'CONFIRMED',priority_score:88,score_components:[{points:40,reason:'confirmed recent violation'}],oath_case_count:1,pluto_match:true,pluto_owner_name:'ALPHA OWNER LLC',pluto_building_area_sqft:500000,hpd_contact_count:2,dob_activity_count:1,dob_recent_activity_count:1,dob_explicit_cooling_tower_count:1,dob_mechanical_or_boiler_count:1,latest_dob_activity_date:'2026-08-20' },
    { system_id:'SYS-2',bin:'2',bbl:'2',address:'20 BETA AVE',borough:'Queens',zip:'11101',active_equipment:1,latitude:40.74,longitude:-73.94,coordinate_status:'VALID',latest_sample_date:'2026-08-15',days_since_latest_sample:6,latest_inspection_date:null,latest_inspection_type:null,confirmed_violation:false,recent_confirmed_violation:false,violation_types:[],signal_types:[],primary_signal:'NO_CURRENT_SIGNAL',evidence_confidence:'STRONG_SIGNAL',priority_score:0,score_components:[],oath_case_count:0,pluto_match:true,pluto_owner_name:'ALPHA OWNER LLC',pluto_building_area_sqft:250000,hpd_contact_count:0,dob_activity_count:0,dob_recent_activity_count:0,dob_explicit_cooling_tower_count:0,dob_mechanical_or_boiler_count:0,latest_dob_activity_date:null },
  ],
}

const changes = {
  history_schema_version:'1.1',
  history_started_at:'2026-08-20T20:00:00Z',
  observed_at:'2026-08-21T20:00:00Z',
  baseline_initialized:false,
  new_event_count:1,
  events:[{
    event_type:'SAMPLE_REPORTED',system_id:'SYS-1',bbl:'1',bin:'1',address:'10 ALPHA ST',borough:'Manhattan',detected_at:'2026-08-21T20:00:00Z',source_observation_date:'2026-08-21',previous_value:null,new_value:'2026-08-21',source:'NYC_COOLING_TOWER_REGISTRATIONS',evidence_basis:'SYSTEM_ID_EXACT',priority_score:88,evidence_confidence:'CONFIRMED',contact_available:true,
  }],
}

const nysPayload = {
  schema_version:'1.0',
  metadata:{
    schema_version:'1.0', generated_at:'2026-08-21T20:05:00Z', jurisdiction:'NEW_YORK_STATE_EXCLUDING_NYC', source_regime:'NYS_COOLING_TOWER_REGISTRY_WEEKLY_EXTRACT',
    source:{ dataset_id:'24a4-muw7',name:'New York State Cooling Tower Registry Weekly Extract',retrieved_at:'2026-08-21T20:05:00Z',source_record_count:2,source_last_updated_at:'2026-08-18T00:00:00Z',url:'https://example.test/nys',scope_note:'Official NYS weekly extract; county is source provenance.' },
    normalized_equipment_count:2,source_duplicate_equipment_rows:0,source_missing_equipment_id_rows:0,invalid_coordinate_equipment_count:0,missing_coordinate_equipment_count:0,unique_property_count:1,multi_equipment_property_count:1,equipment_at_multi_equipment_properties:2,max_equipment_per_property:2,
    source_health:[{source_key:'nys_registry',dataset_id:'24a4-muw7',name:'New York State Cooling Tower Registry Weekly Extract',entity_unit:'NYS cooling-tower Equipment_ID records',retrieved_record_count:2,requested_entity_count:2,normalized_entity_count:2,matched_entity_count:2,attached_entity_count:2,displayed_entity_count:2,coverage_percentage:100,previous_coverage_percentage:null,coverage_change_percentage_points:null,coverage_note:'Current source represented.',status:'HEALTHY',status_reasons:[]}],
  },
  summary:{registered_equipment:2,mapped_equipment:2,non_compliant:1,compliant:1,sample_required:1,update_required:0,missing_legionella_result:0,disinfection_required:0,decommissioned:0,out_of_service:0,multi_equipment_properties:1,equipment_at_multi_equipment_properties:2,max_equipment_per_property:2,published_county_counts:{Madison:2},status_counts:{Sample_Required:1,'Legionella Sampled':1},compliance_counts:{'Non-compliant':1,Compliant:1},sample_result_counts:{lt20:2},operation_duration_counts:{'Year-round':2}},
  systems:[
    {system_id:'NYS-100',source_equipment_id:'100',jurisdiction:'NEW_YORK_STATE_EXCLUDING_NYC',source_regime:'NYS_COOLING_TOWER_REGISTRY_WEEKLY_EXTRACT',address:'252 Genesee St',city:'Oneida',zip:'13421',source_county:'Madison',property_key:'252 genesee st|oneida|13421',property_equipment_count:2,regulation_compliance:'Non-compliant',ct_status:'Sample_Required',last_update_days:8,last_sampled_days:99,latest_sample_date:'2026-05-11',latest_sample_result:'lt20',operation_duration:'Year-round',latitude:43.078739,longitude:-75.6493,coordinate_status:'VALID',source_latitude_raw:'43.078739',source_longitude_raw:'-75.6493'},
    {system_id:'NYS-101',source_equipment_id:'101',jurisdiction:'NEW_YORK_STATE_EXCLUDING_NYC',source_regime:'NYS_COOLING_TOWER_REGISTRY_WEEKLY_EXTRACT',address:'252 Genesee St',city:'Oneida',zip:'13421',source_county:'Madison',property_key:'252 genesee st|oneida|13421',property_equipment_count:2,regulation_compliance:'Compliant',ct_status:'Legionella Sampled',last_update_days:2,last_sampled_days:29,latest_sample_date:'2026-07-20',latest_sample_result:'lt20',operation_duration:'Year-round',latitude:43.078739,longitude:-75.6493,coordinate_status:'VALID',source_latitude_raw:'43.078739',source_longitude_raw:'-75.6493'},
  ],
}

const nysChanges = {
  history_schema_version:'1.0',history_started_at:'2026-08-20T20:05:00Z',observed_at:'2026-08-21T20:05:00Z',baseline_initialized:false,new_event_count:1,
  events:[{event_type:'NYS_CT_STATUS_CHANGED',system_id:'NYS-100',source_equipment_id:'100',address:'252 Genesee St',city:'Oneida',zip:'13421',source_county:'Madison',detected_at:'2026-08-21T20:05:00Z',source_observation_date:null,previous_value:'Legionella Sampled',new_value:'Sample_Required',source:'NYS_COOLING_TOWER_REGISTRY_WEEKLY_EXTRACT',evidence_basis:'EQUIPMENT_ID_EXACT'}],
}

const procurementHealth = {
  schema_version:'1.0', source:'NYC_CITY_RECORD', status:'HEALTHY', last_success:'2026-08-21T20:00:00Z', last_attempt:'2026-08-21T20:00:00Z', record_count:2, relevant_record_count:1, normalized_contract_count:0, normalized_notice_count:1, resolved_company_count:0, unresolved_vendor_count:0, facility_link_count:0, exact_tower_link_count:0, pagination_complete:true, schema_valid:true, freshness:'CURRENT', status_reasons:[],
}

const cityRecordProcurement = {
  schema_version:'1.0', generated_at:'2026-08-21T20:00:00Z',
  source:{dataset_id:'dg92-zbpx',name:'NYC City Record Online (CROL)',retrieved_at:'2026-08-21T20:00:00Z',as_of_date:'2026-08-21',award_lookback_days:730},
  summary:{scoped_record_count:2,relevant_record_count:1,open_relevant_opportunities:1,recent_relevant_awards:0,unresolved_vendor_count:0,classification_counts:{COOLING_TOWER_MAINTENANCE:1}},
  source_health:procurementHealth,
  notices:[{schema_version:'1.0',procurement_id:'notice-city-1',source:'NYC_CITY_RECORD',source_record_id:'city-1',notice_id:'N1',agency:'DCAS',title:'Cooling tower maintenance services',procurement_text:'Cooling tower maintenance services',service_category:'COOLING_TOWER_MAINTENANCE',service_confidence:'CONFIRMED',classification_terms:['cooling tower maintenance'],classification_reason:'Explicit cooling-tower maintenance language',due_date:'2026-09-15',status:'OPEN',scope:'OPEN_SOLICITATIONS',source_url:'https://example.test/city-record/1',retrieved_at:'2026-08-21T20:00:00Z'}],
}

const checkbookProcurement = {
  schema_version:'1.0',generated_at:'2026-08-21T20:00:00Z',
  source:{name:'Checkbook NYC Contracts API',api_url:'https://example.test/checkbook-api',documentation_url:'https://example.test/checkbook-docs',retrieved_at:'2026-08-21T20:00:00Z'},
  summary:{citywide_source_transaction_count:2,citywide_subvendor_source_transaction_count:0,citywide_unique_prime_contract_count:2,citywide_relevant_contract_count:1,edc_source_transaction_count:0,edc_unique_prime_contract_count:0,edc_unique_contract_line_count:0,edc_relevant_contract_count:0,relevant_contract_count:1,unresolved_vendor_count:1,classification_counts:{WATER_TREATMENT:1},value_semantics:'Observed source-reported public contract values; not company revenue.'},
  source_health:{NYC_CHECKBOOK_CITYWIDE:{...procurementHealth,source:'NYC_CHECKBOOK_CITYWIDE',record_count:2,relevant_record_count:1,normalized_contract_count:1,normalized_notice_count:0,unresolved_vendor_count:1,status:'WARNING',status_reasons:['ENTITY_RESOLUTION_UNCERTAINTY']}},
  contracts:[{schema_version:'1.0',procurement_id:'contract-checkbook-1',source:'NYC_CHECKBOOK_CITYWIDE',source_record_id:'PC1',source_contract_id:'PC1',vendor_raw:'ALPHA WATER SERVICES LLC',vendor_role:'PRIME',company_id:null,company_match_confidence:'UNRESOLVED',company_resolution_method:'NO_SAFE_MATCH',buyer_name:'DCAS',agency:'DCAS',title:'Water treatment services',description:'Water treatment services',service_category:'WATER_TREATMENT',service_confidence:'CONFIRMED',classification_terms:['water treatment'],classification_reason:'Explicit water-treatment language',current_amount:250000,original_amount:250000,spend_to_date:100000,start_date:'2026-01-01',end_date:'2027-01-01',status:'REGISTERED',observed_value_evidence:'SOURCE_REPORTED_PUBLIC_CONTRACT',source_url:'https://example.test/checkbook/PC1',retrieved_at:'2026-08-21T20:00:00Z',facility_match_confidence:'UNLINKED',tower_link_confidence:'UNLINKED'}],
}

const detail = {
  schema_version:'1.0', metadata:payload.metadata,
  identity:{ system_id:'SYS-1',bin:'1',bbl:'1',address:'10 ALPHA ST',borough:'Manhattan',zip:'10001',active_equipment:3,latitude:40.75,longitude:-73.99,coordinate_status:'VALID',source_latitude_raw:'40.75',source_longitude_raw:'-73.99' },
  dob_activity_history:[{ job_filing_number:'M0001-I1',bbl:'1',filing_status:'Approved',job_type:'Alteration',job_description:'Replace existing cooling tower and associated piping.',initial_cost:100000,filing_date:'2026-06-01',current_status_date:'2026-08-20',first_permit_date:null,approved_date:'2026-07-01',signoff_date:null,activity_date:'2026-08-20',mechanical_systems:true,boiler_equipment:false,explicit_cooling_tower_mention:true,commercial_relevance:'COOLING_TOWER_EXPLICIT',owner_business_name:'ALPHA OWNER LLC',applicant_business_name:'ALPHA ENGINEERING PC',source:'NYC_DOB_NOW_JOB_APPLICATION_FILINGS',match_basis:'BBL_EXACT' }],
  sample_history:{ source_raw:'07/01/2026',dates:['2026-07-01'],malformed_values:[],latest_sample_date:'2026-07-01',previous_sample_date:null,latest_sample_interval_days:null,intervals_days:[],sample_count:1 },
  signals:[{ type:'POTENTIAL_SAMPLING_GAP',title:'Potential sampling gap',evidence_confidence:'VERIFY',fact_class:'COMMERCIAL_SIGNAL',date:'2026-07-01',reason:'Operating status must be verified.' }],
  inspection_history:[],
  oath_case_history:[{ ticket_number:'0880900460',ticket_number_source_raw:'0880900460',match_basis:'SUMMONS_NUMBER_EXACT',issuing_agency:'DOHMH',violation_date:'2026-06-10',violation_location:{borough:'Manhattan',block:'1',lot:'1',house:'10',street_name:'ALPHA ST',zip:'10001'},hearing_status:'HEARING COMPLETED',hearing_result:'IN VIOLATION',hearing_date:'2026-07-01',decision_date:'2026-07-15',compliance_status:null,violation_description:'Cooling tower violation',penalty_imposed:1000,paid_amount:250,additional_penalties_or_late_fees:0,balance_due:750,total_violation_amount:1000,date_judgment_docketed:null,charges:[{code:'CT01',code_section:'24 RCNY 8',description:'Cooling tower violation',infraction_amount:1000}] }],
  scoring:{ score:88,components:[{points:40,reason:'confirmed recent violation'}],priority_model_version:'1.0' },
}

beforeEach(() => {
  window.location.hash = ''
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    const responsePayload = url.includes('/details/') ? detail
      : url.includes('/data/procurement-city-record.json') ? cityRecordProcurement
      : url.includes('/data/procurement-checkbook.json') ? checkbookProcurement
      : url.includes('/data/nys-changes.json') ? nysChanges
      : url.includes('/data/nys-systems.json') ? nysPayload
      : url.includes('/data/changes.json') ? changes
      : payload
    return Promise.resolve({ ok:true, json:() => Promise.resolve(responsePayload) }) as unknown as Promise<Response>
  }))
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: vi.fn().mockResolvedValue(undefined) } })
})

afterEach(() => vi.unstubAllGlobals())

test('renders the redesigned commercial account-intelligence workspace after dataset load', async () => {
  render(<App />)
  expect(await screen.findByRole('heading', { name:'Prospect workspace', level:1 })).toBeInTheDocument()
  expect(screen.getByText((_, element) => element?.textContent === '2 matching systems')).toBeInTheDocument()
  expect(screen.getByText('High priority accounts')).toBeInTheDocument()
  expect(screen.getByText('Sampling follow-up')).toBeInTheDocument()
  for (const name of ['Monitor','Map','NYS Market','NYS Changes','Opportunities','Portfolios','Workflow']) {
    expect(screen.getByRole('button', { name })).toBeInTheDocument()
  }
  expect(screen.getByRole('button', { name:'Source Health & Coverage' })).toBeInTheDocument()
})

test('filters records and opens a shareable full account profile with DOB project history', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('10 ALPHA ST')
  await user.type(screen.getByPlaceholderText('Address, system ID, BIN…'), 'BETA')
  expect(screen.queryByText('10 ALPHA ST')).not.toBeInTheDocument()
  expect(screen.getByText('20 BETA AVE')).toBeInTheDocument()
  await user.clear(screen.getByPlaceholderText('Address, system ID, BIN…'))
  await user.click(screen.getByText('10 ALPHA ST'))
  await waitFor(() => expect(screen.getByRole('heading', { name:'Identity' })).toBeInTheDocument())
  expect(window.location.hash).toBe('#/account/SYS-1')
  expect(screen.getByRole('button', { name:'Copy account link' })).toBeInTheDocument()
  const detailPanel = screen.getByRole('complementary', { name: 'Selected cooling tower detail' })
  expect(within(detailPanel).getByText('Potential sampling gap')).toBeInTheDocument()
  expect(within(detailPanel).getByRole('heading', { name:'DOB NOW project activity' })).toBeInTheDocument()
  expect(within(detailPanel).getByText('Cooling tower mention')).toBeInTheDocument()
  expect(within(detailPanel).getByText('Replace existing cooling tower and associated piping.')).toBeInTheDocument()
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

test('opens the Monitor product mode with source-backed change evidence', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('10 ALPHA ST')
  await user.click(screen.getByRole('button', { name:'Monitor' }))
  expect(screen.getByRole('heading', { name:'Monitor workspace', level:1 })).toBeInTheDocument()
  expect(screen.getAllByText('New public sample reported').length).toBeGreaterThan(0)
  expect(screen.getByText('Source: NYC_COOLING_TOWER_REGISTRATIONS')).toBeInTheDocument()
  expect(screen.getByText('Evidence: SYSTEM_ID_EXACT')).toBeInTheDocument()
})

test('opens the NYS Market mode without NYC score semantics', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('10 ALPHA ST')
  await user.click(screen.getByRole('button', { name:'NYS Market' }))
  expect(screen.getByRole('heading', { name:'NYS Market', level:1 })).toBeInTheDocument()
  expect(screen.getByText('Source non-compliant')).toBeInTheDocument()
  expect(screen.getByText((_, element) => element?.textContent === '2 matching NYS equipment records')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name:'Non-compliant' }))
  expect(screen.getByText((_, element) => element?.textContent === '1 matching NYS equipment records')).toBeInTheDocument()
  expect(screen.queryByText('Priority score')).not.toBeInTheDocument()
})

test('opens NYS Changes and shows Equipment_ID-exact evidence', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('10 ALPHA ST')
  await user.click(screen.getByRole('button', { name:'NYS Changes' }))
  expect(await screen.findByRole('heading', { name:'NYS Changes', level:1 })).toBeInTheDocument()
  expect(screen.getAllByText('NYS cooling-tower status changed')).toHaveLength(2)
  expect(screen.getByText('Evidence: EQUIPMENT_ID_EXACT')).toBeInTheDocument()
})

test('opens the commercial, portfolio, workflow and source-health workspaces without fabricating unsupported data', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByText('10 ALPHA ST')

  await user.click(screen.getByRole('button', { name:'Opportunities' }))
  expect(screen.getByRole('heading', { name:'Opportunities workspace', level:1 })).toBeInTheDocument()
  expect(await screen.findByText('LIVE SOURCE DATA')).toBeInTheDocument()
  expect(screen.getByText('Public procurement intelligence')).toBeInTheDocument()
  expect(screen.getByText('Cooling tower maintenance services')).toBeInTheDocument()
  expect(screen.getByText('ALPHA WATER SERVICES LLC')).toBeInTheDocument()
  expect(screen.getAllByText('$250,000').length).toBeGreaterThanOrEqual(1)
  expect(screen.getByText('Current account timing opportunities')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name:'Portfolios' }))
  expect(screen.getByRole('heading', { name:'Portfolios', level:1 })).toBeInTheDocument()
  expect(screen.getAllByText('ALPHA OWNER LLC').length).toBeGreaterThanOrEqual(2)
  expect(screen.getByText('1 multi-property group')).toBeInTheDocument()
  expect(screen.getByText('2 cooling-tower accounts · 4 active equipment · 1 contact-ready · 750,000 sq ft PLUTO building area')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name:'Workflow' }))
  expect(screen.getByRole('heading', { name:/Workflow workspace/, level:1 })).toBeInTheDocument()
  expect(screen.getByText('Sign in from the profile control to sync workflow state across sessions and devices.')).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name:'Source Health & Coverage' }))
  expect(screen.getByRole('heading', { name:'Source Health & Coverage', level:1 })).toBeInTheDocument()
  expect(screen.getByText('Source-health metrics are not available in this payload.')).toBeInTheDocument()
  expect(await screen.findByText('Procurement sources')).toBeInTheDocument()
  expect(screen.getByText('NYC_CITY_RECORD')).toBeInTheDocument()
  expect(screen.getByText('NYC_CHECKBOOK_CITYWIDE')).toBeInTheDocument()
})