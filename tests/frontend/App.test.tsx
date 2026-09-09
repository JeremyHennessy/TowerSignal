import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import App from '../../src/App'
import type { ChangesPayload } from '../../src/types/history'
import type { SystemsPayload } from '../../src/types/data'

const systems: SystemsPayload = {
  schema_version:'2.0',
  metadata:{
    generated_at:'2026-02-25T20:00:00Z', snapshot_date:'2026-02-25', sources:[], normalized_system_count:2, source_duplicate_registration_rows:0,
    source_missing_registration_system_id_rows:0, invalid_coordinate_system_count:0, oath_requested_ticket_count:1, oath_matched_ticket_count:1,
    oath_unmatched_ticket_count:0, oath_match_basis:'SUMMONS_NUMBER_EXACT', pluto_requested_bbl_count:2, pluto_matched_bbl_count:2,
    dob_requested_bbl_count:2, dob_matched_bbl_count:1, dob_matched_filing_count:2, dob_explicit_cooling_tower_filing_count:1, dob_mechanical_or_boiler_filing_count:1,
    hpd_requested_bbl_count:2, hpd_matched_registration_bbl_count:1, hpd_matched_contact_bbl_count:1,
    planimetric_requested_bin_count:2, planimetric_matched_bin_count:1, planimetric_matched_feature_count:1, planimetric_match_basis:'BIN_EXACT', planimetric_feature_identity_basis:'fixture', planimetric_imagery_year:2022,
    building_footprint_requested_bin_count:2, building_footprint_matched_bin_count:2, building_footprint_matched_feature_count:2, building_footprint_match_basis:'BIN_EXACT',
    bbl_registry_source_count:2, bbl_recovered_exact_bin_mappluto_count:0, bbl_canonical_count:2, bbl_unresolved_count:0, bbl_identity_recovery_contract:'fixture', rules_version:'fixture', priority_model_version:'fixture',
  },
  summary:{registered_systems:2,active_equipment:3,potential_sampling_gaps:1,recent_confirmed_violations:1,systems_with_oath_cases:1,systems_with_pluto_context:2,systems_with_dob_activity:1,systems_with_recent_dob_activity:1,systems_with_explicit_cooling_tower_dob_activity:1,systems_with_hpd_registration:1,systems_with_hpd_contacts:1,systems_with_planimetric_bin_match:1,systems_with_building_footprint_match:2,systems_with_registry_source_bbl:2,systems_with_recovered_bbl:0,systems_with_canonical_bbl:2,systems_with_unresolved_bbl:0},
  systems:[
    {system_id:'SYS-1',bin:'100001',bbl:'1000010001',registry_bbl:'1000010001',bbl_identity_basis:'REGISTRY_BBL',bbl_identity_status:'SOURCE',address:'10 ALPHA ST',borough:'Manhattan',zip:'10001',active_equipment:2,latitude:40.75,longitude:-73.99,coordinate_status:'VALID',registration_date:'2020-01-01',sample_count:3,inspection_count:2,violation_citation_count:1,latest_violation_date:'2026-01-15',oath_balance_due_total:1000,latest_sample_date:'2025-12-01',days_since_latest_sample:86,latest_inspection_date:'2026-01-15',latest_inspection_type:'ROUTINE',confirmed_violation:true,recent_confirmed_violation:true,violation_types:['fixture'],signal_types:['CONFIRMED_RECENT_VIOLATION'],primary_signal:'CONFIRMED_RECENT_VIOLATION',evidence_confidence:'CONFIRMED',priority_score:92,score_components:[],oath_case_count:1,pluto_match:true,pluto_owner_name:'ALPHA OWNER',pluto_building_area_sqft:100000,dob_activity_count:2,dob_recent_activity_count:2,dob_explicit_cooling_tower_count:1,dob_mechanical_or_boiler_count:1,latest_dob_activity_date:'2026-02-01',hpd_contact_count:1,planimetric_bin_match:true,planimetric_building_tower_count:1,building_footprint_bin_match:true,building_footprint_count:1},
    {system_id:'SYS-2',bin:'200001',bbl:'2000010001',registry_bbl:'2000010001',bbl_identity_basis:'REGISTRY_BBL',bbl_identity_status:'SOURCE',address:'20 BETA AVE',borough:'Brooklyn',zip:'11201',active_equipment:1,latitude:40.69,longitude:-73.99,coordinate_status:'VALID',registration_date:'2021-01-01',sample_count:1,inspection_count:1,violation_citation_count:0,latest_violation_date:null,oath_balance_due_total:0,latest_sample_date:'2026-02-01',days_since_latest_sample:24,latest_inspection_date:'2026-02-10',latest_inspection_type:'ROUTINE',confirmed_violation:false,recent_confirmed_violation:false,violation_types:[],signal_types:['RECENT_NYC_HEALTH_INSPECTION'],primary_signal:'RECENT_NYC_HEALTH_INSPECTION',evidence_confidence:'STRONG_SIGNAL',priority_score:51,score_components:[],oath_case_count:0,pluto_match:true,pluto_owner_name:'BETA OWNER',pluto_building_area_sqft:50000,dob_activity_count:0,dob_recent_activity_count:0,dob_explicit_cooling_tower_count:0,dob_mechanical_or_boiler_count:0,latest_dob_activity_date:null,hpd_contact_count:0,planimetric_bin_match:false,planimetric_building_tower_count:0,building_footprint_bin_match:true,building_footprint_count:1},
  ],
}

const changes: ChangesPayload = {
  schema_version:'1.0', generated_at:'2026-02-25T20:00:00Z', history_started_at:'2026-02-20T00:00:00Z', previous_snapshot_at:'2026-02-24T20:00:00Z', summary:{new_event_count:1,event_counts:{VIOLATION_ADDED:1}},
  events:[{event_id:'evt-1',event_type:'VIOLATION_ADDED',event_at:'2026-02-25T20:00:00Z',system_id:'SYS-1',address:'10 ALPHA ST',borough:'Manhattan',summary:'Violation added',detail:'Fixture history event',previous_value:null,current_value:'fixture'}],
}

const detail = {
  schema_version:'2.0',metadata:systems.metadata,identity:{system_id:'SYS-1',bin:'100001',bbl:'1000010001',registry_bbl:'1000010001',bbl_identity_basis:'REGISTRY_BBL',bbl_identity_status:'SOURCE',bbl_identity_evidence:{},address:'10 ALPHA ST',borough:'Manhattan',zip:'10001',active_equipment:2,latitude:40.75,longitude:-73.99,coordinate_status:'VALID',source_latitude_raw:'40.75',source_longitude_raw:'-73.99'},historical_profile:{registration_date:'2020-01-01',sample:{reported_sample_count:3},inspection:{inspection_count:2,violation_citation_count:1,latest_violation_date:'2026-01-15'},oath:{balance_due_total:1000}},building_context:{owner_name:'ALPHA OWNER'},dob_activity_history:[{job_filing_number:'DOB-1',activity_date:'2026-02-01',job_description:'Cooling tower replacement',applicant_business_name:'ALPHA ENGINEERING',owner_business_name:'ALPHA OWNER'}],hpd_registration:null,planimetric_building_tower_features:[],building_footprints:[],sample_history:{source_raw:'',dates:['2025-12-01'],malformed_values:[],latest_sample_date:'2025-12-01',previous_sample_date:null,latest_sample_interval_days:null,intervals_days:[],sample_count:1},signals:[],inspection_history:[{inspection_date:'2026-01-15',inspection_type:'ROUTINE',violation_count:1,violations:[{summons_number:'0880000001'}]}],oath_case_history:[{ticket_number:'0880000001',match_basis:'SUMMONS_NUMBER_EXACT',penalty_imposed:1000,balance_due:1000}],scoring:{score:92,components:[]},
}

vi.mock('../../src/data/api', () => ({
  loadSystems: vi.fn(() => Promise.resolve(systems)),
  loadChanges: vi.fn(() => Promise.resolve(changes)),
  loadSystemDetail: vi.fn(() => Promise.resolve(detail)),
  loadNysSystems: vi.fn(() => Promise.resolve({schema_version:'1.0',metadata:{generated_at:'2026-02-25T20:00:00Z',normalized_equipment_count:0,source:{}},summary:{equipment_count:0},systems:[]})),
  loadNysChanges: vi.fn(() => Promise.resolve({schema_version:'1.0',generated_at:'2026-02-25T20:00:00Z',history_started_at:'2026-02-20T00:00:00Z',previous_snapshot_at:null,summary:{new_event_count:0,event_counts:{}},events:[]})),
  loadProcurement: vi.fn(() => Promise.resolve({cityRecord:{schema_version:'1.0',generated_at:'2026-02-25T20:00:00Z',source:{},summary:{},source_health:{},notices:[]},checkbook:{schema_version:'1.0',generated_at:'2026-02-25T20:00:00Z',source:{},summary:{},source_health:{},contracts:[]},nysAuthorities:null,openBookWater:null,nychaWater:null,sourceErrors:{}})),
  loadCompanies: vi.fn(() => Promise.resolve({schema_version:'1.0',generated_at:'2026-02-25T20:00:00Z',summary:{observed_vendor_company_count:0,procurement_observation_count:0,cross_source_exact_label_company_count:0,companies_requiring_resolution_review:0,unresolved_observation_count:0,value_semantics:''},companies:[],unresolved_vendor_observations:[]})),
  loadKnownFirms: vi.fn(() => Promise.resolve({schema_version:'1.0',generated_at:'2026-02-25T20:00:00Z',domain:'TOWERSIGNAL_KNOWN_FIRMS',summary:{known_firm_count:0,firms_with_site_relationships:0,firms_with_serviced_sites:0,firms_with_contracted_sites:0,firms_with_procurement_evidence:0,firms_with_dwt_service_evidence:0,unique_related_site_count:0,unique_serviced_site_count:0,unique_contracted_site_count:0,firm_site_relationship_count:0,firm_serviced_site_relationship_count:0,mapped_firm_site_relationship_count:0,role_firm_counts:{}},evidence_semantics:{normalization:'fixture',serviced_sites:'fixture'},firms:[]})),
  loadDomesticWaterMarket: vi.fn(() => Promise.resolve(null)),
  loadProviderResolution: vi.fn(() => Promise.resolve(null)),
  loadNysPublicWater: vi.fn(() => Promise.resolve(null)),
  loadNysLsliDetails: vi.fn(() => Promise.resolve(null)),
  loadNysServiceLineSummary: vi.fn(() => Promise.resolve(null)),
  loadNycDistributionWater: vi.fn(() => Promise.resolve(null)),
  loadNycWaterSignals: vi.fn(() => Promise.resolve(null)),
  loadElapProbe: vi.fn(() => Promise.resolve(null)),
  loadCoverageAudit: vi.fn(() => Promise.resolve(null)),
}))

beforeEach(() => {
  window.location.hash = '#/prospect'
  vi.clearAllMocks()
})

async function clickWorkspace(user: ReturnType<typeof userEvent.setup>, name: string) {
  const direct = screen.queryByRole('button', { name })
  if (direct) {
    await user.click(direct)
    return
  }
  await user.click(screen.getByRole('button', { name: /^More/ }))
  await user.click(screen.getByRole('menuitem', { name }))
}

test('renders the redesigned commercial account-intelligence workspace after dataset load', async () => {
  const user = userEvent.setup()
  render(<App />)
  expect(await screen.findByRole('heading', { name:'Prospect workspace', level:1 })).toBeInTheDocument()
  expect(screen.getByText((_, element) => element?.textContent === '2 matching systems')).toBeInTheDocument()
  expect(screen.getByText('High priority accounts')).toBeInTheDocument()
  expect(screen.getByText('Sampling follow-up')).toBeInTheDocument()
  for (const name of ['Home','Monitor','Map','Opportunities','NYS Market']) {
    expect(screen.getByRole('button', { name })).toBeInTheDocument()
  }
  expect(screen.getByRole('button', { name:/^More/ })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name:/^More/ }))
  for (const name of ['NYS Changes','Known Firms','Portfolios','Workflow']) {
    expect(screen.getByRole('menuitem', { name })).toBeInTheDocument()
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
  expect(within(detailPanel).getByText('Cooling tower replacement')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name:'← Back' }))
  await screen.findByRole('heading', { name:'Prospect workspace' })
})

test('navigation opens monitor, map, NYS, opportunities and workflow views', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('heading', { name:'Prospect workspace' })
  await clickWorkspace(user, 'Monitor')
  expect(screen.getByRole('heading', { name:'Monitor workspace' })).toBeInTheDocument()
  await clickWorkspace(user, 'Map')
  expect(screen.getByRole('heading', { name:'Map workspace' })).toBeInTheDocument()
  await clickWorkspace(user, 'NYS Market')
  expect(screen.getByRole('heading', { name:'NYS Market' })).toBeInTheDocument()
  await clickWorkspace(user, 'Opportunities')
  expect(screen.getByRole('heading', { name:'Opportunities workspace' })).toBeInTheDocument()
  await clickWorkspace(user, 'Workflow')
  expect(screen.getByRole('heading', { name:/Workflow workspace/ })).toBeInTheDocument()
})

test('source health page opens from the global source-health button', async () => {
  render(<App />)
  await screen.findByRole('heading', { name:'Prospect workspace' })
  fireEvent.click(screen.getByRole('button', { name:'Source Health & Coverage' }))
  expect(await screen.findByRole('heading', { name:'Source Health & Coverage' })).toBeInTheDocument()
})

test('account route is shareable across reload', async () => {
  window.location.hash = '#/account/SYS-1'
  render(<App />)
  expect(await screen.findByRole('heading', { name:'Identity' })).toBeInTheDocument()
  expect(window.location.hash).toBe('#/account/SYS-1')
})

test('deep-linked missing account falls back to prospect without fixture substitution', async () => {
  window.location.hash = '#/account/UNKNOWN'
  render(<App />)
  expect(await screen.findByRole('heading', { name:'Prospect workspace' })).toBeInTheDocument()
})

test('home button routes to portal home hash', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('heading', { name:'Prospect workspace' })
  await user.click(screen.getByRole('button', { name:'Home', exact:true }))
  expect(window.location.hash).toBe('#/home')
})

test('mobile menu exposes all workspace destinations', async () => {
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('heading', { name:'Prospect workspace' })
  await user.click(screen.getByRole('button', { name:'Open workspace menu' }))
  const dialog = screen.getByRole('dialog', { name:'TowerSignal workspace menu' })
  for (const name of ['Prospect','Monitor','Map','Opportunities','NYS Market','NYS Changes','Known Firms','Water Quality','Portfolios','Workflow']) {
    expect(within(dialog).getByRole('button', { name:new RegExp(`^${name}`) })).toBeInTheDocument()
  }
}
