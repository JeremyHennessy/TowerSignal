import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { CompaniesPage } from '../../src/components/CompaniesPage'
import { CompanyProfilePage } from '../../src/components/CompanyProfilePage'

vi.mock('../../src/components/FirmSiteMap', () => ({
  FirmSiteMap: () => <div role="region" aria-label="Known firm site relationship map" data-testid="firm-site-map">Map</div>,
}))

const alphaFirm = {
  firm_id:'observed-company-alpha', canonical_name:'ALPHA WATER SERVICES LLC', strict_name:'ALPHA WATER SERVICES LLC', normalized_name:'ALPHA WATER SERVICES',
  identity_confidence:'STRONG', resolution_method:'EXACT_SOURCE_LABEL_SUFFIX_PRESERVED', candidate_related_company_ids:[], procurement_company_id:'observed-company-alpha',
  roles:['DWT_INSPECTION_PROVIDER','PROCUREMENT_VENDOR'], primary_role:'DWT_INSPECTION_PROVIDER', role_counts:{DWT_INSPECTION_PROVIDER:4,PROCUREMENT_VENDOR:1},
  source_classes:['NYC_DWT_TANK_INSPECTIONS','NYC_CHECKBOOK_CITYWIDE'], observation_count:5, observed_site_count:3, serviced_site_count:2, contracted_site_count:1,
  project_site_count:0, tower_account_count:2, mapped_site_count:2, first_observed_date:'2026-01-01', latest_observed_date:'2026-08-21', active_last_12m:true,
  qualification_count:0, active_qualification_count:0, observed_contract_count:1, active_contract_count:1, observed_customer_count:1, repeat_buyer_count:0,
  observed_contract_value:250000, service_categories:['WATER_TREATMENT'], detail_path:'firm-details/ob/observed-company-alpha.json',
}

const rmcFirm = {
  ...alphaFirm,
  firm_id:'observed-company-rmc', canonical_name:'RMC', strict_name:'RMC', normalized_name:'RMC', identity_confidence:'VERIFY',
  resolution_method:'AMBIGUOUS_SHORT_OR_GENERIC_VENDOR_LABEL', procurement_company_id:'observed-company-rmc', roles:['PROCUREMENT_VENDOR'], primary_role:'PROCUREMENT_VENDOR',
  role_counts:{PROCUREMENT_VENDOR:1}, source_classes:['NYC_CHECKBOOK_CITYWIDE'], observation_count:1, observed_site_count:0, serviced_site_count:0, contracted_site_count:0,
  project_site_count:0, tower_account_count:0, mapped_site_count:0, qualification_count:0, active_qualification_count:0, observed_contract_value:0,
  detail_path:'firm-details/ob/observed-company-rmc.json',
}

const extraFirms = Array.from({ length: 101 }, (_, index) => {
  const n = String(index + 1).padStart(3, '0')
  return {
    ...rmcFirm,
    firm_id:`observed-company-fixture-${n}`,
    canonical_name:`FIRM ${n}`,
    strict_name:`FIRM ${n}`,
    normalized_name:`FIRM ${n}`,
    identity_confidence:'STRONG',
    resolution_method:'EXACT_SOURCE_LABEL_SUFFIX_PRESERVED',
    procurement_company_id:`observed-company-fixture-${n}`,
    detail_path:`firm-details/fi/observed-company-fixture-${n}.json`,
  }
})

const knownFirmsPayload = {
  schema_version:'1.0', generated_at:'2026-08-21T20:00:00Z', domain:'TOWERSIGNAL_KNOWN_FIRMS',
  summary:{known_firm_count:103,firms_with_site_relationships:1,firms_with_serviced_sites:1,firms_with_contracted_sites:1,firms_with_procurement_evidence:103,firms_with_dwt_service_evidence:1,unique_related_site_count:3,unique_serviced_site_count:2,unique_contracted_site_count:1,firm_site_relationship_count:3,firm_serviced_site_relationship_count:2,mapped_firm_site_relationship_count:2,role_firm_counts:{DWT_INSPECTION_PROVIDER:1,PROCUREMENT_VENDOR:103}},
  evidence_semantics:{normalization:'Legal suffixes are preserved and ambiguous labels remain separate.',serviced_sites:'A serviced site requires explicit DWT inspection-provider or laboratory evidence.',related_sites:'Related does not mean serviced.',last_active:'Latest public-record observation.',procurement_value:'Observed public procurement value is not company revenue.'},
  firms:[alphaFirm, ...extraFirms, rmcFirm],
}

const alphaDetail = {
  schema_version:'1.0', generated_at:'2026-08-21T20:00:00Z', domain:'TOWERSIGNAL_KNOWN_FIRM_DETAIL', firm:alphaFirm,
  aliases:[
    {name:'ALPHA WATER SERVICES LLC',source_class:'NYC_CHECKBOOK_CITYWIDE',role:'PROCUREMENT_VENDOR',observation_count:1},
    {name:'Alpha Water Services LLC',source_class:'NYC_DWT_TANK_INSPECTIONS',role:'DWT_INSPECTION_PROVIDER',observation_count:4},
  ],
  site_relationships:[{
    site_id:'NYC-BIN-100001', bin:'100001', bbl:'1000010001', address:'10 ALPHA ST', borough:'Manhattan', zip:'10001',
    latitude:40.75, longitude:-73.99, system_ids:['SYS-1'], roles:['DWT_INSPECTION_PROVIDER'], relationship_classes:['OBSERVED_SERVICE'],
    evidence_classes:['DWT_INSPECTION_BY_FIRM_OBSERVED_SERVICE'], source_record_ids:['DWT-1'], observation_count:4,
    first_observed_date:'2026-01-01', last_observed_date:'2026-08-21', serviced:true, contracted:false, project_role:false, tower_account_count:1, mapped:true,
  }],
  qualifications:[],
  procurement:{company_id:'observed-company-alpha',canonical_name:'ALPHA WATER SERVICES LLC',observed_sources:['NYC_CHECKBOOK_CITYWIDE'],observed_buyers:['DCAS'],service_categories:['WATER_TREATMENT'],procurement_ids:['contract-checkbook-1'],metrics:{observed_contract_count:1,active_contract_count:1,observed_contract_value:250000,observed_customer_count:1,repeat_buyer_count:0},value_semantics:'Observed public procurement values; not company revenue.'},
  evidence_boundaries:{identity:'Firm identities normalize source-reported names conservatively. Legal suffixes are preserved.',serviced_site:'Serviced-site counts include only DWT source rows that explicitly name an inspection firm or laboratory at a building/tank.',contracted_site:'A confirmed public contract relationship is not represented as proof that work was completed.',project_roles:'DOB applicant/owner business names are project roles, not incumbent provider claims.',qualification:'DEC Category 7G registration supports qualification only.'},
}

const systemsPayload = {
  schema_version:'2.0',
  metadata:{generated_at:'2026-08-21T20:00:00Z',snapshot_date:'2026-08-21',sources:[],normalized_system_count:1,source_duplicate_registration_rows:0,source_missing_registration_system_id_rows:0,invalid_coordinate_system_count:0,rules_version:'fixture',priority_model_version:'1.0'},
  summary:{registered_systems:1,active_equipment:3,potential_sampling_gaps:1,recent_confirmed_violations:1},
  systems:[{
    system_id:'SYS-1',bin:'100001',bbl:'1000010001',address:'10 ALPHA ST',borough:'Manhattan',zip:'10001',active_equipment:3,latitude:40.75,longitude:-73.99,coordinate_status:'VALID',
    latest_sample_date:'2026-07-01',days_since_latest_sample:51,latest_inspection_date:'2026-08-01',latest_inspection_type:'ROUTINE',confirmed_violation:true,recent_confirmed_violation:true,
    violation_types:['Critical'],signal_types:['CONFIRMED_RECENT_VIOLATION'],primary_signal:'CONFIRMED_RECENT_VIOLATION',evidence_confidence:'CONFIRMED',priority_score:88,score_components:[],
    oath_case_count:2,dob_activity_count:4,dob_recent_activity_count:3,hpd_contact_count:2,acris_recent_document_count:1,latest_acris_recorded_date:'2026-08-20',
    cms_institutional_facility_count:1,cms_institutional_facility_types:['HOSPITAL'],
  }],
}

const procurement = {
  cityRecord:{schema_version:'1.0',generated_at:'2026-08-21T20:00:00Z',source:{},summary:{},source_health:{},notices:[]},
  checkbook:{schema_version:'1.0',generated_at:'2026-08-21T20:00:00Z',source:{},summary:{},source_health:{},contracts:[{schema_version:'1.0',procurement_id:'contract-checkbook-1',source:'NYC_CHECKBOOK_CITYWIDE',source_record_id:'PC1',source_contract_id:'PC1',vendor_raw:'ALPHA WATER SERVICES LLC',vendor_role:'PRIME',buyer_name:'DCAS',agency:'DCAS',title:'Water treatment services',description:'Water treatment services',service_category:'WATER_TREATMENT',service_confidence:'CONFIRMED',classification_terms:['water treatment'],classification_reason:'Explicit water-treatment language',current_amount:250000,original_amount:250000,spend_to_date:100000,start_date:'2026-01-01',end_date:'2027-01-01',status:'REGISTERED',observed_value_evidence:'SOURCE_REPORTED_PUBLIC_CONTRACT',source_url:'https://example.test/checkbook/PC1',retrieved_at:'2026-08-21T20:00:00Z'}]},
  nysAuthorities:null, openBookWater:null, nychaWater:null, sourceErrors:{},
}

vi.mock('../../src/data/api', () => ({
  loadKnownFirms: vi.fn(() => Promise.resolve(knownFirmsPayload)),
  loadKnownFirmDetail: vi.fn(() => Promise.resolve(alphaDetail)),
  loadSystems: vi.fn(() => Promise.resolve(systemsPayload)),
  loadProcurement: vi.fn(() => Promise.resolve(procurement)),
}))

beforeEach(() => {
  window.location.hash = '#/companies'
  vi.clearAllMocks()
})

test('Known Companies is one filterable, sortable and genuinely paginated master table', async () => {
  const user = userEvent.setup()
  render(<CompaniesPage onOpenCompany={vi.fn()} />)

  expect(await screen.findByRole('heading', { name:'Known companies & firms', level:1 })).toBeInTheDocument()
  expect(screen.getByLabelText('Known firm search')).toBeInTheDocument()
  expect(screen.getByLabelText('Known firm role')).toBeInTheDocument()
  expect(screen.getByLabelText('Known firm relationship')).toBeInTheDocument()
  expect(screen.getByLabelText('Known firm activity')).toBeInTheDocument()
  expect(screen.getByLabelText('Known firm identity confidence')).toBeInTheDocument()

  const table = screen.getByRole('table')
  expect(within(table).getAllByRole('row')).toHaveLength(51)
  await user.click(screen.getByRole('button', { name:'Company / firm' }))
  expect(within(table).getAllByRole('row')[1]).toHaveTextContent('ALPHA WATER SERVICES LLC')
  expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name:'Next' }))
  await user.click(screen.getByRole('button', { name:'Next' }))
  expect(screen.getByText(/Page 3 of 3/)).toBeInTheDocument()
  expect(screen.getByText('RMC')).toBeInTheDocument()

  await user.type(screen.getByLabelText('Known firm search'), 'ALPHA')
  expect(screen.getByText('ALPHA WATER SERVICES LLC')).toBeInTheDocument()
  expect(screen.queryByText('RMC')).not.toBeInTheDocument()

  await user.click(screen.getByText('ALPHA WATER SERVICES LLC'))
  expect(window.location.hash).toBe('#/company/observed-company-alpha')
})

test('Known Firm Profile leads with map and Prospect-style site intelligence while retaining complete evidence', async () => {
  render(<CompanyProfilePage companyId="observed-company-alpha" onBack={vi.fn()} onOpenCompany={vi.fn()} />)

  expect(await screen.findByRole('heading', { name:'ALPHA WATER SERVICES LLC', level:1 })).toBeInTheDocument()
  expect(screen.getByRole('button', { name:'Copy firm link' })).toBeInTheDocument()
  expect(screen.getByText('Sites connected to ALPHA WATER SERVICES LLC')).toBeInTheDocument()
  expect(screen.getByRole('region', { name:'Known firm site relationship map' })).toBeInTheDocument()
  expect(screen.getByLabelText('Firm site search')).toBeInTheDocument()
  expect(screen.getByLabelText('Firm site relationship filter')).toBeInTheDocument()
  expect(screen.getByLabelText('Firm site borough filter')).toBeInTheDocument()

  const siteTable = screen.getAllByRole('table')[0]
  const siteRow = within(siteTable).getByText('10 ALPHA ST').closest('tr')
  expect(siteRow).not.toBeNull()
  if (siteRow) {
    expect(within(siteRow).getByText('88')).toBeInTheDocument()
    expect(within(siteRow).getByText('3 active units')).toBeInTheDocument()
    expect(within(siteRow).getByText('✓ 2 HPD contacts')).toBeInTheDocument()
    expect(within(siteRow).getByText('51 days ago')).toBeInTheDocument()
    expect(within(siteRow).getByText('OATH · 2')).toBeInTheDocument()
    expect(within(siteRow).getByText('DOB · 3')).toBeInTheDocument()
    expect(within(siteRow).getByText('ACRIS · 1')).toBeInTheDocument()
  }
  expect(screen.getByRole('link', { name:'Open account SYS-1' })).toHaveAttribute('href', '#/account/SYS-1')

  expect(screen.getByRole('heading', { name:'Everything TowerSignal knows about this firm', level:2 })).toBeInTheDocument()
  expect(screen.getAllByText('$250,000').length).toBeGreaterThanOrEqual(1)
  expect(screen.getByText('Water treatment services')).toBeInTheDocument()
  expect(screen.getByRole('link', { name:'Open source ↗' })).toHaveAttribute('href', 'https://example.test/checkbook/PC1')
  expect(screen.getByText(/Serviced-site counts include only DWT source rows/)).toBeInTheDocument()
  expect(screen.getByText(/not represented as proof that work was completed/)).toBeInTheDocument()
})
