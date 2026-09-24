import { expect, test } from 'vitest'
import { scoreCompanySalesAccount } from '../../src/companyAdmin/scoring'
import type { CompanyAdminContact, CompanyAdminProfile } from '../../src/types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../../src/types/firm'

const profile=(overrides:Partial<CompanyAdminProfile>={}):CompanyAdminProfile=>({
  company_id:'c1',canonical_name:'ALPHA WATER',legal_name:'Alpha Water LLC',rollup_name:null,rollup_company_id:null,
  rollup_source_name:null,rollup_source_url:null,website:null,website_source_name:null,website_source_url:null,
  identity_source_name:null,identity_source_url:null,headquarters_address:null,headquarters_city:null,headquarters_region:null,
  headquarters_postal_code:null,headquarters_country:null,headquarters_source_name:null,headquarters_source_url:null,
  parent_company_id:null,parent_company_name:null,parent_source_name:null,parent_source_url:null,company_type:null,enrichment_checked_at:null,
  revenue_amount:null,revenue_low:null,revenue_high:null,revenue_currency:'USD',revenue_year:null,revenue_type:'unknown',
  revenue_source_name:null,revenue_source_url:null,revenue_confidence:'unknown',relationship_status:'uncontacted',
  last_contacted_at:null,next_action_date:null,account_owner:null,internal_summary:null,...overrides,
})

const firm=(overrides:Partial<KnownFirmSummaryRecord>={}):KnownFirmSummaryRecord=>({
  firm_id:'c1',canonical_name:'ALPHA WATER',strict_name:'ALPHA WATER',normalized_name:'ALPHA WATER',
  identity_confidence:'CONFIRMED',resolution_method:'fixture',candidate_related_company_ids:[],roles:[],
  primary_role:'PROCUREMENT_VENDOR',role_counts:{},source_classes:[],observation_count:0,observed_site_count:0,
  serviced_site_count:0,contracted_site_count:0,project_site_count:0,tower_account_count:0,mapped_site_count:0,
  active_last_12m:false,qualification_count:0,active_qualification_count:0,observed_contract_count:0,
  active_contract_count:0,observed_customer_count:0,repeat_buyer_count:0,observed_contract_value:0,
  service_categories:[],detail_path:'x',...overrides,
})

const contact=(overrides:Partial<CompanyAdminContact>={}):CompanyAdminContact=>({
  contact_id:'p1',company_id:'c1',sales_account_id:'a1',name:'Alex Buyer',title:'VP Sales',email:null,phone:null,
  linkedin_url:null,notes:null,contact_role:null,primary_contact:false,source_name:null,source_url:null,
  verified_at:null,active:true,...overrides,
})

test('water-treatment service evidence produces high TowerSignal fit',()=>{
  const score=scoreCompanySalesAccount({
    masterProfile:profile(),
    contacts:[],
    publicFirms:[firm({
      roles:['DWT_INSPECTION_PROVIDER','DEC_7G_REGISTERED_BUSINESS','PROCUREMENT_VENDOR'],
      service_categories:['water treatment','cooling tower'],
      serviced_site_count:120,tower_account_count:80,observed_contract_count:10,observed_customer_count:4,
      observation_count:250,active_last_12m:true,
    })],
  })
  expect(score.fitScore).toBeGreaterThanOrEqual(70)
  expect(score.readinessScore).toBeLessThan(30)
})

test('sourced buying contacts and enrichment increase readiness independently of fit',()=>{
  const score=scoreCompanySalesAccount({
    masterProfile:profile({
      website:'https://alpha.example',headquarters_address:'1 Main St',company_type:'Water treatment',
      parent_company_name:'Alpha Holdings',identity_source_url:'https://alpha.example/about',
      revenue_amount:10000000,revenue_type:'reported',enrichment_checked_at:'2026-09-24T00:00:00Z',
    }),
    contacts:[contact({
      email:'alex@alpha.example',phone:'212-555-0100',linkedin_url:'https://linkedin.com/in/alex',
      contact_role:'decision-maker',primary_contact:true,
    })],
    publicFirms:[firm()],
  })
  expect(score.readinessScore).toBeGreaterThanOrEqual(90)
  expect(score.fitScore).toBeLessThan(30)
})


test('owner-only tower volume does not masquerade as TowerSignal customer fit',()=>{
  const score=scoreCompanySalesAccount({
    masterProfile:profile(),
    contacts:[],
    publicFirms:[firm({
      roles:['DOB_NOW_OWNER_BUSINESS','LEGACY_DOB_OWNER_BUSINESS'],
      serviced_site_count:0,
      tower_account_count:1000,
      observed_site_count:1000,
      observation_count:5000,
      active_last_12m:true,
    })],
  })
  expect(score.fitScore).toBeLessThan(20)
})


test('owner self-inspection does not masquerade as a third-party TowerSignal provider',()=>{
  const score=scoreCompanySalesAccount({
    masterProfile:profile(),
    contacts:[],
    publicFirms:[firm({
      roles:['DWT_INSPECTION_PROVIDER','DOB_NOW_APPLICANT_BUSINESS','DOB_NOW_OWNER_BUSINESS','LEGACY_DOB_OWNER_BUSINESS'],
      serviced_site_count:21,
      tower_account_count:47,
      observation_count:789,
      active_last_12m:true,
    })],
  })
  expect(score.fitScore).toBeLessThan(20)
  expect(score.fitReasons.join(' ')).toContain('Owner/self-inspection pattern')
})
