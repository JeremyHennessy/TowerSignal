import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { CompaniesPage } from '../../src/components/CompaniesPage'
import { CompanyProfilePage } from '../../src/components/CompanyProfilePage'

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
  tower_account_count:0, mapped_site_count:0, observed_contract_value:0, detail_path:'firm-details/ob/observed-company-rmc.json',
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
  aliases:[{name:'ALPHA WATER SERVICES LLC',source_class:'NYC_CHECKBOOK_CITYWIDE',role:'PROCUREMENT_VENDOR',observation_count:1},{name:'Alpha Water Services LLC',source_class:'NYC_DWT_TANK_INSPECTIONS',role:'DWT_INSPECTION_PROVIDER',observation_count:4}],
  site_relationships:[], qualifications:[],
  procurement:{company_id:'observed-company-alpha',canonical_name:'ALPHA WATER SERVICES LLC',observed_sources:['NYC_CHECKBOOK_CITYWIDE'],observed_buyers:['DCAS'],service_categories:['WATER_TREATMENT'],procurement_ids:['contract-checkbook-1'],metrics:{observed_contract_count:1,active_contract_count:1,observed_contract_value:250000,observed_customer_count:1,repeat_buyer_count:0},value_semantics:'Observed public procurement values; not company revenue.'},
  evidence_boundaries:{identity:'Firm identities normalize source-reported names conservatively. Legal suffixes are preserved.',serviced_site:'Serviced-site counts include only DWT source rows that explicitly name an inspection firm or laboratory at a building/tank.',contracted_site:'A confirmed public contract relationship is not represented as proof that work was completed.',project_roles:'DOB applicant/owner business names are project roles, not incumbent provider claims.',qualification:'DEC Category 7G registration supports qualification only.'},
}

const procurement = {
  cityRecord:{schema_version:'1.0',generated_at:'2026-08-21T20:00:00Z',source:{},summary:{},source_health:{},notices:[]},
  checkbook:{schema_version:'1.0',generated_at:'2026-08-21T20:00:00Z',source:{},summary:{},source_health:{},contracts:[{schema_version:'1.0',procurement_id:'contract-checkbook-1',source:'NYC_CHECKBOOK_CITYWIDE',source_record_id:'PC1',source_contract_id:'PC1',vendor_raw:'ALPHA WATER SERVICES LLC',vendor_role:'PRIME',buyer_name:'DCAS',agency:'DCAS',title:'Water treatment services',description:'Water treatment services',service_category:'WATER_TREATMENT',service_confidence:'CONFIRMED',classification_terms:['water treatment'],classification_reason:'Explicit water-treatment language',current_amount:250000,original_amount:250000,spend_to_date:100000,start_date:'2026-01-01',end_date:'2027-01-01',status:'REGISTERED',observed_value_evidence:'SOURCE_REPORTED_PUBLIC_CONTRACT',source_url:'https://example.test/checkbook/PC1',retrieved_at:'2026-08-21T20:00:00Z'}]},
  nysAuthorities:null, openBookWater:null, nychaWater:null, sourceErrors:{},
}

vi.mock('../../src/data/api', () => ({
  loadKnownFirms: vi.fn(() => Promise.resolve(knownFirmsPayload)),
  loadKnownFirmDetail: vi.fn(() => Promise.resolve(alphaDetail)),
  loadProcurement: vi.fn(() => Promise.resolve(procurement)),
}))

beforeEach(() => {
  window.location.hash = '#/companies'
  vi.clearAllMocks()
})

test('Known Firms is filterable, sortable and genuinely paginated while preserving source semantics', async () => {
  const user = userEvent.setup()
  render(<CompaniesPage onOpenCompany={vi.fn()} />)

  expect(await screen.findByRole('heading', { name:'Known firms', level:1 })).toBeInTheDocument()
  expect(screen.getByLabelText('Known firm search')).toBeInTheDocument()
  expect(screen.getByLabelText('Known firm role')).toBeInTheDocument()
  expect(screen.getByLabelText('Known firm relationship')).toBeInTheDocument()
  expect(screen.getByLabelText('Known firm activity')).toBeInTheDocument()
  expect(screen.getByLabelText('Known firm identity confidence')).toBeInTheDocument()
  expect(screen.getAllByText('public values · not revenue').length).toBeGreaterThanOrEqual(1)
  expect(screen.getByText('$250,000')).toBeInTheDocument()
  expect(screen.queryByText('Invalid Date')).not.toBeInTheDocument()

  const table = screen.getByRole('table')
  expect(within(table).getAllByRole('row')).toHaveLength(101)
  await user.click(screen.getByRole('button', { name:'Firm' }))
  expect(within(table).getAllByRole('row')[1]).toHaveTextContent('ALPHA WATER SERVICES LLC')

  expect(screen.getByText('Page 1 of 2')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name:'Next →' }))
  expect(screen.getByText('Page 2 of 2')).toBeInTheDocument()
  expect(screen.getByText('RMC')).toBeInTheDocument()

  await user.type(screen.getByLabelText('Known firm search'), 'ALPHA')
  expect(screen.getByText('ALPHA WATER SERVICES LLC')).toBeInTheDocument()
  expect(screen.queryByText('RMC')).not.toBeInTheDocument()
  expect(screen.getAllByText('VERIFY').length).toBeGreaterThanOrEqual(0)

  await user.click(screen.getByRole('button', { name:'Open firm →' }))
  expect(window.location.hash).toBe('#/company/observed-company-alpha')
})

test('Known Firm Profile renders source-backed identity, value, procurement and service boundaries', async () => {
  render(<CompanyProfilePage companyId="observed-company-alpha" onBack={vi.fn()} onOpenCompany={vi.fn()} />)

  expect(await screen.findByRole('heading', { name:'ALPHA WATER SERVICES LLC', level:1 })).toBeInTheDocument()
  expect(screen.getByRole('button', { name:'Copy firm link' })).toBeInTheDocument()
  expect(screen.getByText('STRONG')).toBeInTheDocument()
  expect(screen.getByText('Exact Source Label Suffix Preserved')).toBeInTheDocument()
  expect(screen.getAllByText('$250,000').length).toBeGreaterThanOrEqual(1)
  expect(screen.getByText('Water treatment services')).toBeInTheDocument()
  expect(screen.getByRole('link', { name:'Open source ↗' })).toHaveAttribute('href', 'https://example.test/checkbook/PC1')
  expect(screen.getByText(/Serviced-site counts include only DWT source rows/)).toBeInTheDocument()
  expect(screen.getByText(/not represented as proof that work was completed/)).toBeInTheDocument()
})
