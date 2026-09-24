import type {
  CompanyAdminContact,
  CompanyAdminProfile,
  CompanyRollupSuggestion,
  CompanySalesAccount,
  CompanySalesAccountMember,
} from '../types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../types/firm'

const legalSuffixes=new Set(['INC','INCORPORATED','LLC','LTD','LIMITED','LLP','LP','CORP','CORPORATION','CO','COMPANY','PLC','PC'])
const publicMailDomains=new Set(['gmail.com','outlook.com','hotmail.com','yahoo.com','icloud.com','aol.com'])

function normalizeName(value:string|null|undefined):string{
  const tokens=(value??'').toUpperCase().replaceAll('&',' AND ').replace(/[^A-Z0-9]+/g,' ').trim().split(/\s+/).filter(Boolean)
  while(tokens.length && legalSuffixes.has(tokens[tokens.length-1])) tokens.pop()
  return tokens.join(' ')
}

function normalizedAddress(profile:CompanyAdminProfile):string{
  return [
    profile.headquarters_address,
    profile.headquarters_city,
    profile.headquarters_region,
    profile.headquarters_postal_code,
  ].filter(Boolean).join(' ').toUpperCase().replace(/[^A-Z0-9]+/g,' ').trim()
}

function domain(value:string|null|undefined):string|null{
  if(!value) return null
  try{return new URL(value).hostname.toLowerCase().replace(/^www\./,'')}
  catch{return null}
}

function emailDomain(value:string|null|undefined):string|null{
  if(!value) return null
  const at=value.lastIndexOf('@')
  if(at<0) return null
  const result=value.slice(at+1).trim().toLowerCase()
  return result && !publicMailDomains.has(result) ? result : null
}

function tokenSimilarity(left:string,right:string):number{
  const a=new Set(normalizeName(left).split(' ').filter(Boolean))
  const b=new Set(normalizeName(right).split(' ').filter(Boolean))
  if(!a.size||!b.size) return 0
  const intersection=[...a].filter(token=>b.has(token)).length
  const union=new Set([...a,...b]).size
  return union?intersection/union:0
}

function completeness(profile:CompanyAdminProfile|undefined):number{
  if(!profile) return 0
  return [
    profile.legal_name,
    profile.website,
    profile.headquarters_address||profile.headquarters_city,
    profile.company_type,
    profile.parent_company_name,
    profile.identity_source_url,
  ].filter(Boolean).length
}

type AccountContext={
  account:CompanySalesAccount
  members:CompanyAdminProfile[]
  names:string[]
  websiteDomains:Set<string>
  emailDomains:Set<string>
  addresses:Set<string>
  observations:number
  contacts:number
  strength:number
}

function accountContext(
  account:CompanySalesAccount,
  members:CompanySalesAccountMember[],
  profiles:Map<string,CompanyAdminProfile>,
  contacts:CompanyAdminContact[],
  firms:Map<string,KnownFirmSummaryRecord>,
):AccountContext{
  const links=members.filter(member=>member.sales_account_id===account.sales_account_id)
  const rows=links.map(link=>profiles.get(link.company_id)).filter((row):row is CompanyAdminProfile=>Boolean(row))
  const names=new Set<string>([account.display_name])
  const websiteDomains=new Set<string>()
  const addresses=new Set<string>()
  rows.forEach(profile=>{
    ;[profile.canonical_name,profile.legal_name,profile.rollup_name].filter(Boolean).forEach(value=>names.add(String(value)))
    const host=domain(profile.website)
    if(host) websiteDomains.add(host)
    const address=normalizedAddress(profile)
    if(address) addresses.add(address)
  })
  const memberIds=new Set(links.map(link=>link.company_id))
  const contactRows=contacts.filter(contact=>memberIds.has(contact.company_id)&&contact.active)
  const emailDomains=new Set(contactRows.map(contact=>emailDomain(contact.email)).filter((value):value is string=>Boolean(value)))
  const observations=links.reduce((sum,link)=>sum+(firms.get(link.company_id)?.observation_count??0),0)
  const primary=profiles.get(account.primary_company_id)
  const strength=links.length*4+Math.min(30,Math.log1p(observations)*5)+completeness(primary)*5+Math.min(15,contactRows.length*5)
  return {account,members:rows,names:[...names],websiteDomains,emailDomains,addresses,observations,contacts:contactRows.length,strength}
}

export function generateCompanyRollupSuggestions({
  accounts,
  members,
  profiles,
  contacts,
  firms,
}:{
  accounts:CompanySalesAccount[]
  members:CompanySalesAccountMember[]
  profiles:CompanyAdminProfile[]
  contacts:CompanyAdminContact[]
  firms:KnownFirmSummaryRecord[]
}):Array<Pick<CompanyRollupSuggestion,'suggestion_id'|'candidate_sales_account_id'|'suggested_sales_account_id'|'score'|'confidence'|'evidence'>>{
  const profileById=new Map(profiles.map(profile=>[profile.company_id,profile]))
  const firmById=new Map(firms.map(firm=>[firm.firm_id,firm]))
  const contexts=accounts.filter(account=>account.record_status==='active').map(account=>accountContext(account,members,profileById,contacts,firmById))
  const suggestions:Array<Pick<CompanyRollupSuggestion,'suggestion_id'|'candidate_sales_account_id'|'suggested_sales_account_id'|'score'|'confidence'|'evidence'>>=[]

  for(let i=0;i<contexts.length;i++){
    for(let j=i+1;j<contexts.length;j++){
      const left=contexts[i],right=contexts[j]
      const leftNorm=normalizeName(left.account.display_name)
      const rightNorm=normalizeName(right.account.display_name)

      // An explicit parent/subsidiary relationship is evidence against treating two accounts as aliases.
      if(normalizeName(left.account.parent_name)===rightNorm || normalizeName(right.account.parent_name)===leftNorm) continue

      let score=0
      const evidence:string[]=[]

      const exactName=left.names.some(a=>right.names.some(b=>normalizeName(a)&&normalizeName(a)===normalizeName(b)))
      if(exactName){score+=55;evidence.push('Exact normalized company-name match')}

      let bestSimilarity=0
      for(const a of left.names) for(const b of right.names) bestSimilarity=Math.max(bestSimilarity,tokenSimilarity(a,b))
      if(!exactName){
        if(bestSimilarity>=0.85){score+=30;evidence.push(`Very strong name-token similarity (${Math.round(bestSimilarity*100)}%)`)}
        else if(bestSimilarity>=0.70){score+=20;evidence.push(`Strong name-token similarity (${Math.round(bestSimilarity*100)}%)`)}
        else if(bestSimilarity>=0.60){score+=10;evidence.push(`Moderate name-token similarity (${Math.round(bestSimilarity*100)}%)`)}
      }

      const sharedWebsite=[...left.websiteDomains].find(value=>right.websiteDomains.has(value))
      if(sharedWebsite){score+=35;evidence.push(`Same website domain: ${sharedWebsite}`)}

      const sharedEmail=[...left.emailDomains].find(value=>right.emailDomains.has(value))
      if(sharedEmail){score+=30;evidence.push(`Same non-public email domain: ${sharedEmail}`)}

      const sharedAddress=[...left.addresses].find(value=>right.addresses.has(value))
      if(sharedAddress){score+=20;evidence.push('Same recorded headquarters address')}

      if(score<55) continue
      score=Math.min(100,score)
      const confidence=score>=80?'high':score>=65?'medium':'low'
      const target=left.strength>=right.strength?left:right
      const candidate=target===left?right:left
      const suggestion_id=`rollup::${candidate.account.sales_account_id}::${target.account.sales_account_id}`
      suggestions.push({
        suggestion_id,
        candidate_sales_account_id:candidate.account.sales_account_id,
        suggested_sales_account_id:target.account.sales_account_id,
        score,
        confidence,
        evidence,
      })
    }
  }

  return suggestions.sort((a,b)=>b.score-a.score || a.suggestion_id.localeCompare(b.suggestion_id))
}
