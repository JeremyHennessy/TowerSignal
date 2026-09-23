import { expect, test } from 'vitest'
import { buildCompanyResearchCandidates, companyResearchPriority } from '../../src/companyAdmin/priority'
import type { CompanyAdminProfile } from '../../src/types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../../src/types/firm'

function firm(id: string, name: string, values: Partial<KnownFirmSummaryRecord> = {}): KnownFirmSummaryRecord {
  return {
    firm_id:id,
    canonical_name:name,
    strict_name:name,
    normalized_name:name,
    identity_confidence:'CONFIRMED',
    resolution_method:'fixture',
    candidate_related_company_ids:[],
    roles:['DWT_INSPECTION_PROVIDER'],
    primary_role:'DWT_INSPECTION_PROVIDER',
    role_counts:{},
    source_classes:[],
    observation_count:10,
    observed_site_count:10,
    serviced_site_count:10,
    contracted_site_count:0,
    project_site_count:0,
    tower_account_count:5,
    mapped_site_count:5,
    active_last_12m:true,
    qualification_count:0,
    active_qualification_count:0,
    observed_contract_count:0,
    active_contract_count:0,
    observed_customer_count:0,
    repeat_buyer_count:0,
    observed_contract_value:0,
    service_categories:[],
    detail_path:'',
    ...values,
  }
}

test('research priority increases with commercial footprint', () => {
  const small = firm('a','A')
  const large = firm('b','B',{ serviced_site_count:500, tower_account_count:250, observed_contract_count:50, observed_customer_count:5 })
  expect(companyResearchPriority(large)).toBeGreaterThan(companyResearchPriority(small))
})

test('reviewed private rollups collapse aliases into one research candidate', () => {
  const profiles = [
    { company_id:'master', canonical_name:'MASTER' },
    { company_id:'alias', canonical_name:'ALIAS', rollup_company_id:'master' },
  ] as CompanyAdminProfile[]
  const candidates = buildCompanyResearchCandidates([
    firm('master','MASTER',{ serviced_site_count:50 }),
    firm('alias','ALIAS',{ serviced_site_count:100 }),
  ], profiles, 100)
  expect(candidates).toHaveLength(1)
  expect(candidates[0].company_id).toBe('master')
  expect(candidates[0].member_ids).toEqual(['alias','master'])
})
