import { expect, test } from 'vitest'
import { generateCompanyRollupSuggestions } from '../../src/companyAdmin/rollupSuggestions'
import type { CompanyAdminContact, CompanyAdminProfile, CompanySalesAccount, CompanySalesAccountMember } from '../../src/types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../../src/types/firm'

const profile=(id:string,name:string,website:string|null,address:string|null,parent:string|null=null):CompanyAdminProfile=>({
  company_id:id,canonical_name:name,legal_name:name,rollup_name:null,rollup_company_id:null,
  rollup_source_name:null,rollup_source_url:null,website,website_source_name:null,website_source_url:null,
  identity_source_name:null,identity_source_url:null,headquarters_address:address,headquarters_city:'New York',
  headquarters_region:'NY',headquarters_postal_code:'10001',headquarters_country:'US',
  headquarters_source_name:null,headquarters_source_url:null,parent_company_id:null,parent_company_name:parent,
  parent_source_name:null,parent_source_url:null,company_type:'Water treatment',enrichment_checked_at:null,
  revenue_amount:null,revenue_low:null,revenue_high:null,revenue_currency:'USD',revenue_year:null,revenue_type:'unknown',
  revenue_source_name:null,revenue_source_url:null,revenue_confidence:'unknown',relationship_status:'uncontacted',
  last_contacted_at:null,next_action_date:null,account_owner:null,internal_summary:null,
})

const account=(id:string,primary:string,name:string,parent:string|null=null):CompanySalesAccount=>({
  sales_account_id:id,primary_company_id:primary,display_name:name,account_classification:'target',record_status:'active',
  merged_into_sales_account_id:null,parent_name:parent,parent_source_url:null,account_owner:null,sales_notes:null,
})

const member=(accountId:string,companyId:string):CompanySalesAccountMember=>({
  sales_account_id:accountId,company_id:companyId,member_type:'primary-source',is_primary:true,
  relationship_source_name:null,relationship_source_url:null,
})

test('roll-up generator surfaces evidence-backed aliases and not parent/subsidiary relationships',()=>{
  const profiles=[
    profile('p1','Tower Water LLC','https://towerwater.com','5 Shirley Avenue'),
    profile('p2','Tower Water Management, Inc.','https://www.towerwater.com','5 Shirley Avenue'),
    profile('p3','Barclay Water Management LLC','https://barclaywater.com','10 Main Street','Ecolab'),
    profile('p4','Ecolab Inc','https://ecolab.com','1 Ecolab Place'),
  ]
  const accounts=[
    account('a1','p1','Tower Water'),
    account('a2','p2','Tower Water Management'),
    account('a3','p3','Barclay Water Management','Ecolab'),
    account('a4','p4','Ecolab'),
  ]
  const members=accounts.map((row,index)=>member(row.sales_account_id,profiles[index].company_id))
  const contacts=[] as CompanyAdminContact[]
  const firms=[] as KnownFirmSummaryRecord[]
  const suggestions=generateCompanyRollupSuggestions({accounts,members,profiles,contacts,firms})
  const tower=suggestions.find(row=>new Set([row.candidate_sales_account_id,row.suggested_sales_account_id]).has('a1')&&new Set([row.candidate_sales_account_id,row.suggested_sales_account_id]).has('a2'))
  expect(tower).toBeTruthy()
  expect(tower?.score).toBeGreaterThanOrEqual(80)
  expect(tower?.evidence).toContain('Same website domain: towerwater.com')
  expect(suggestions.some(row=>new Set([row.candidate_sales_account_id,row.suggested_sales_account_id]).has('a3')&&new Set([row.candidate_sales_account_id,row.suggested_sales_account_id]).has('a4'))).toBe(false)
})
