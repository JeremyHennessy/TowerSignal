import type { CompanyAdminProfile, CompanySalesAccount, CompanySalesAccountMember } from '../types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../types/firm'
import type { CompanyEvidence } from './evidence'

export interface DirectoryIdentity { id:string; name:string; normalized:string|null; firm?:KnownFirmSummaryRecord }
export interface DirectoryCompany {
  id:string; name:string; account:CompanySalesAccount|null; identities:DirectoryIdentity[]
  parents:{name:string; source:string|null; status:string}[]; observations:number
}

// Only durable, reviewed memberships collapse source identities. Name normalization is display/search data.
export function buildCompanyDirectory(firms:KnownFirmSummaryRecord[],profiles:CompanyAdminProfile[],accounts:CompanySalesAccount[],members:CompanySalesAccountMember[],evidence:CompanyEvidence|null):DirectoryCompany[] {
  const identities=new Map<string,DirectoryIdentity>(firms.map(firm=>[firm.firm_id,{id:firm.firm_id,name:firm.canonical_name,normalized:firm.normalized_name||null,firm}]))
  const profileById=new Map(profiles.map(profile=>[profile.company_id,profile]))
  profiles.forEach(profile=>{if(!identities.has(profile.company_id))identities.set(profile.company_id,{id:profile.company_id,name:profile.canonical_name,normalized:null})})
  const rows=new Map<string,DirectoryCompany>(accounts.filter(account=>account.record_status==='active').map(account=>{
    const profile=profileById.get(account.primary_company_id)
    const confirmed=(evidence?.relationships??[]).filter(link=>link.sales_account_id===account.sales_account_id&&link.status==='confirmed'&&!link.valid_to)
    const parents:DirectoryCompany['parents']=confirmed.flatMap(link=>{
      const parent=evidence?.parents.find(parent=>parent.parent_entity_id===link.parent_entity_id)
      return parent?[{name:parent.display_name,source:link.evidence_url,status:link.relationship_type==='ultimate-parent'?'Confirmed ultimate parent':'Confirmed parent'}]:[]
    })
    const legacyName=account.parent_name||profile?.parent_company_name
    if(!parents.length&&legacyName)parents.push({name:legacyName,source:account.parent_source_url||profile?.parent_source_url||null,status:'Recorded parent'})
    return [account.sales_account_id,{id:account.sales_account_id,name:account.display_name,account,identities:[],parents,observations:0}]
  }))
  const assigned=new Set<string>()
  members.forEach(member=>{
    const row=rows.get(member.sales_account_id),identity=identities.get(member.company_id)
    if(row&&identity&&!assigned.has(identity.id)){row.identities.push(identity);row.observations+=identity.firm?.observation_count??0;assigned.add(identity.id)}
  })
  identities.forEach(identity=>{if(!assigned.has(identity.id))rows.set(identity.id,{id:identity.id,name:identity.name,account:null,identities:[identity],parents:[],observations:identity.firm?.observation_count??0})})
  return [...rows.values()].sort((a,b)=>b.observations-a.observations||a.name.localeCompare(b.name))
}
