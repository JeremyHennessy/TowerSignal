import { expect,test } from 'vitest'
import { belongsToSalesAccount,validateAccountMappings } from '../../src/companyAdmin/accountMapping'
import type { CompanyAdminProfile,CompanySalesAccount,CompanySalesAccountMember } from '../../src/types/companyAdmin'

test('master account assignment wins over an old source identity after a roll-up',()=>{
  const ids=new Set(['source-a'])
  expect(belongsToSalesAccount({company_id:'old-source',sales_account_id:'account-a'},'account-a',ids)).toBe(true)
  expect(belongsToSalesAccount({company_id:'source-a',sales_account_id:'account-b'},'account-a',ids)).toBe(false)
  expect(belongsToSalesAccount({company_id:'source-a',sales_account_id:null},'account-a',ids)).toBe(true)
})
test('incomplete loaded mappings cannot be reported as empty coverage',()=>{
  const profiles=[{company_id:'source-a'}] as CompanyAdminProfile[]
  const accounts=[{sales_account_id:'account-a',primary_company_id:'source-a'}] as CompanySalesAccount[]
  const members=[{sales_account_id:'account-a',company_id:'source-a',is_primary:true}] as CompanySalesAccountMember[]
  expect(()=>validateAccountMappings(profiles,accounts,members)).not.toThrow()
  expect(()=>validateAccountMappings(profiles,accounts,[])).toThrow('could not be loaded completely')
  expect(()=>validateAccountMappings(profiles,[],members)).toThrow()
  expect(()=>validateAccountMappings(profiles,accounts,[...members,...members])).toThrow()
  expect(()=>validateAccountMappings([],[],[])).not.toThrow()
})
