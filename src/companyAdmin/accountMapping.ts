import type { CompanyAdminProfile, CompanySalesAccount, CompanySalesAccountMember } from '../types/companyAdmin'

export function belongsToSalesAccount(row:{sales_account_id?:string|null;company_id:string},accountId:string,memberIds:ReadonlySet<string>):boolean {
  return row.sales_account_id ? row.sales_account_id===accountId : memberIds.has(row.company_id)
}

export function validateAccountMappings(profiles:CompanyAdminProfile[],accounts:CompanySalesAccount[],members:CompanySalesAccountMember[]):void {
  const profileIds=new Set(profiles.map(p=>p.company_id))
  const accountIds=new Set(accounts.map(a=>a.sales_account_id))
  const byCompany=new Map(members.map(m=>[m.company_id,m]))
  if(byCompany.size!==members.length || profiles.some(p=>!byCompany.has(p.company_id)) ||
    members.some(m=>!profileIds.has(m.company_id)||!accountIds.has(m.sales_account_id)) ||
    accounts.some(a=>!profileIds.has(a.primary_company_id)||!members.some(m=>m.sales_account_id===a.sales_account_id&&m.company_id===a.primary_company_id&&m.is_primary))) {
    throw new Error('Company mappings could not be loaded completely. Refresh to retry; no records have been changed.')
  }
}
