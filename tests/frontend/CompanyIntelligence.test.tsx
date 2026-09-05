import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import { CompaniesPage } from '../../src/components/CompaniesPage'
import { CompanyProfilePage } from '../../src/components/CompanyProfilePage'

const alphaCompany = {
  schema_version:'1.0', company_id:'observed-company-alpha', canonical_name:'ALPHA WATER SERVICES LLC', company_type:'OBSERVED_PROCUREMENT_VENDOR', status:'UNKNOWN', current_parent_company_id:null, current_sponsor_company_id:null,
  identity_confidence:'STRONG', first_seen:'2026-01-01', last_seen:'2026-08-21', identity_scope:'OBSERVED_PUBLIC_PROCUREMENT_VENDOR_LABEL', identity_basis:'CASE_AND_PUNCTUATION_NORMALIZED_LEGAL_SUFFIX_PRESERVED', strict_vendor_key:'ALPHA WATER SERVICES LLC', normalized_base_name:'ALPHA WATER SERVICES', cross_source_resolution_confidence:'STRONG', cross_source_resolution_method:'EXACT_SOURCE_LABEL_SUFFIX_PRESERVED', candidate_related_company_ids:[],
  aliases:[{company_id:'observed-company-alpha',alias:'ALPHA WATER SERVICES LLC',normalized_alias:'ALPHA WATER SERVICES',source:'NYC_CHECKBOOK_CITYWIDE',confidence:'STRONG',resolution_method:'EXACT_SOURCE_LABEL_SUFFIX_PRESERVED'}], observed_sources:['NYC_CHECKBOOK_CITYWIDE'], observed_buyers:['DCAS'], service_categories:['WATER_TREATMENT'], procurement_ids:['contract-checkbook-1'], procurement_observation_count:1, city_record_observation_count:0, city_record_recent_award_count:0,
  metrics:{observed_contract_count:1,active_contract_count:1,historical_contract_count:0,observed_contract_value:250000,active_observed_contract_value:250000,observed_spend_to_date:100000,observed_customer_count:1,active_customer_count:1,cooling_tower_related_contract_count:0,water_treatment_contract_count:1,legionella_contract_count:0,mechanical_contract_count:0,median_contract_duration:365,average_contract_duration:365,contracts_expiring_12m:1,contracts_expiring_24m:1,contracts_expiring_36m:1,geographic_state_count:0,geographic_market_count:0,largest_observed_customer_value:250000,top_5_customer_value:250000,observed_customer_concentration:1,repeat_customer_count:0,observable_customer_retention:0},
  value_semantics:'Observed source-reported public contract values and spend-to-date; not company revenue, enterprise value, or a complete customer book.',
}

const rmcCompany = {
  ...alphaCompany,
  company_id:'observed-company-rmc', canonical_name:'RMC', identity_confidence:'VERIFY', strict_vendor_key:'RMC', normalized_base_name:'RMC', cross_source_resolution_confidence:'VERIFY', cross_source_resolution_method:'AMBIGUOUS_SHORT_OR_GENERIC_VENDOR_LABEL',
  aliases:[{company_id:'observed-company-rmc',alias:'RMC',normalized_alias:'RMC',source:'NYC_CHECKBOOK_CITYWIDE',confidence:'VERIFY',resolution_method:'AMBIGUOUS_SHORT_OR_GENERIC_VENDOR_LABEL'}], procurement_ids:['contract-rmc-1'],
}

const companiesPayload = {
  schema_version:'1.0', generated_at:'2026-08-21T20:00:00Z',
  summary:{observed_vendor_company_count:2,procurement_observation_count:2,cross_source_exact_label_company_count:0,companies_requiring_resolution_review:1,unresolved_observation_count:1,value_semantics:'Observed source-reported public contract values; not company revenue, enterprise value, or a complete customer book.'},
  companies:[alphaCompany, rmcCompany],
  unresolved_vendor_observations:[{procurement_id:'contract-rmc-1',source:'NYC_CHECKBOOK_CITYWIDE',vendor_raw:'RMC',observed_company_id:'observed-company-rmc',normalized_base_name:'RMC',resolution_confidence:'VERIFY',resolution_method:'AMBIGUOUS_SHORT_OR_GENERIC_VENDOR_LABEL',candidate_company_ids:[]}],
}

const procurement = {
  cityRecord:{schema_version:'1.0',generated_at:'2026-08-21T20:00:00Z',source:{},summary:{},source_health:{},notices:[]},
  checkbook:{schema_version:'1.0',generated_at:'2026-08-21T20:00:00Z',source:{},summary:{},source_health:{},contracts:[{schema_version:'1.0',procurement_id:'contract-checkbook-1',source:'NYC_CHECKBOOK_CITYWIDE',source_record_id:'PC1',source_contract_id:'PC1',vendor_raw:'ALPHA WATER SERVICES LLC',vendor_role:'PRIME',buyer_name:'DCAS',agency:'DCAS',title:'Water treatment services',description:'Water treatment services',service_category:'WATER_TREATMENT',service_confidence:'CONFIRMED',classification_terms:['water treatment'],classification_reason:'Explicit water-treatment language',current_amount:250000,original_amount:250000,spend_to_date:100000,start_date:'2026-01-01',end_date:'2027-01-01',status:'REGISTERED',observed_value_evidence:'SOURCE_REPORTED_PUBLIC_CONTRACT',source_url:'https://example.test/checkbook/PC1',retrieved_at:'2026-08-21T20:00:00Z'}]},
}

vi.mock('../../src/data/api', () => ({
  loadCompanies: vi.fn(() => Promise.resolve(companiesPayload)),
  loadDomesticWaterMarket: vi.fn(() => Promise.resolve(null)),
  loadElapProbe: vi.fn(() => Promise.resolve(null)),
  loadProviderResolution: vi.fn(() => Promise.resolve(null)),
  loadProcurement: vi.fn(() => Promise.resolve(procurement)),
}))

beforeEach(() => vi.clearAllMocks())

test('Companies shows observed value semantics and keeps RMC in VERIFY review', async () => {
  const user = userEvent.setup()
  const openCompany = vi.fn()
  render(<CompaniesPage onOpenCompany={openCompany} />)

  expect(await screen.findByRole('heading', { name:'Companies', level:1 })).toBeInTheDocument()
  expect(screen.getByText('ALPHA WATER SERVICES LLC')).toBeInTheDocument()
  expect(screen.getByText('RMC')).toBeInTheDocument()
  expect(screen.getAllByText('VERIFY').length).toBeGreaterThanOrEqual(1)
  expect(screen.getAllByText('not company revenue').length).toBeGreaterThanOrEqual(1)
  expect(screen.getAllByText('$250,000')).toHaveLength(2)
  expect(screen.queryByText('Invalid Date')).not.toBeInTheDocument()

  await user.click(screen.getAllByRole('button', { name:'Open company →' })[0])
  expect(openCompany).toHaveBeenCalledWith(alphaCompany)
})

test('Company Profile renders shareable source-backed identity, value and procurement evidence', async () => {
  render(<CompanyProfilePage companyId="observed-company-alpha" onBack={vi.fn()} onOpenCompany={vi.fn()} />)

  expect(await screen.findByRole('heading', { name:'ALPHA WATER SERVICES LLC', level:1 })).toBeInTheDocument()
  expect(screen.getByRole('button', { name:'Copy company link' })).toBeInTheDocument()
  expect(screen.getByText('STRONG · exact source label suffix preserved')).toBeInTheDocument()
  expect(screen.getAllByText('$250,000').length).toBeGreaterThanOrEqual(1)
  expect(screen.getByText('Public source value · not revenue')).toBeInTheDocument()
  expect(screen.getByText('Water treatment services')).toBeInTheDocument()
  expect(screen.getByRole('link', { name:'Open source ↗' })).toHaveAttribute('href', 'https://example.test/checkbook/PC1')
  expect(screen.getByText(/No parent, sponsor, acquisition or private-company financial claims/)).toBeInTheDocument()
})
