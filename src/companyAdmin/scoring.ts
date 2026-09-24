import type { CompanyAdminContact, CompanyAdminProfile } from '../types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../types/firm'

export interface CompanySalesScores {
  fitScore:number
  readinessScore:number
  fitReasons:string[]
  readinessReasons:string[]
}

const rolePoints:Record<string,number>={
  DWT_INSPECTION_PROVIDER:30,
  DWT_LABORATORY:25,
  DEC_7G_REGISTERED_BUSINESS:22,
  PROCUREMENT_VENDOR:8,
  DOB_NOW_APPLICANT_BUSINESS:3,
  DOB_NOW_OWNER_BUSINESS:1,
  LEGACY_DOB_OWNER_BUSINESS:1,
}

function cappedLog(value:number,cap:number,points:number):number{
  if(value<=0) return 0
  return Math.round(points*Math.min(1,Math.log1p(value)/Math.log1p(cap)))
}

function hasRevenue(profile:CompanyAdminProfile):boolean{
  return profile.revenue_amount!=null||profile.revenue_low!=null||profile.revenue_high!=null
}

function ownershipKnown(profile:CompanyAdminProfile):boolean{
  return Boolean(
    profile.parent_company_id||
    profile.parent_company_name||
    /independent(ly)? owned|independent company|privately held/i.test(profile.internal_summary??'')
  )
}

export function scoreCompanySalesAccount({
  publicFirms,
  masterProfile,
  contacts,
}:{
  publicFirms:KnownFirmSummaryRecord[]
  masterProfile:CompanyAdminProfile
  contacts:CompanyAdminContact[]
}):CompanySalesScores{
  const fitReasons:string[]=[]
  const readinessReasons:string[]=[]

  const roles=new Set(publicFirms.flatMap(firm=>firm.roles))
  const ownerRoles=new Set(['DOB_NOW_OWNER_BUSINESS','LEGACY_DOB_OWNER_BUSINESS'])
  const commercialCorroborationRoles=new Set(['DWT_LABORATORY','DEC_7G_REGISTERED_BUSINESS','PROCUREMENT_VENDOR'])
  const suppressInspectionProvider=
    roles.has('DWT_INSPECTION_PROVIDER') &&
    [...ownerRoles].some(role=>roles.has(role)) &&
    ![...commercialCorroborationRoles].some(role=>roles.has(role))
  const scoredRoles=[...roles].filter(role=>!(suppressInspectionProvider&&role==='DWT_INSPECTION_PROVIDER'))
  const roleScore=Math.min(42,scoredRoles.reduce((sum,role)=>sum+(rolePoints[role]??0),0))
  let fit=roleScore
  if(roleScore){
    const named=scoredRoles.filter(role=>rolePoints[role]).map(role=>role.replaceAll('_',' ').toLowerCase())
    fitReasons.push(`Relevant public roles: ${named.join(', ')} (+${roleScore})`)
  }
  if(suppressInspectionProvider){
    fitReasons.push('Owner/self-inspection pattern: DWT inspection activity is not treated as third-party provider evidence (+0)')
  }

  const categories=new Set(publicFirms.flatMap(firm=>firm.service_categories).map(value=>value.toLowerCase()))
  const categoryText=[...categories].join(' ')
  if(/water treatment|cooling tower|legionella|water management|water quality/.test(categoryText)){
    fit+=8
    fitReasons.push('Relevant water/cooling-tower service category (+8)')
  }

  const serviceRoles=new Set(['DWT_INSPECTION_PROVIDER','DWT_LABORATORY','DEC_7G_REGISTERED_BUSINESS'])
  const countsAsServiceRole=(role:string)=>serviceRoles.has(role)&&!(suppressInspectionProvider&&role==='DWT_INSPECTION_PROVIDER')
  const serviceFirms=publicFirms.filter(firm=>firm.roles.some(countsAsServiceRole))
  const procurementFirms=publicFirms.filter(firm=>firm.roles.includes('PROCUREMENT_VENDOR'))

  const serviced=serviceFirms.reduce((sum,firm)=>sum+firm.serviced_site_count,0)
  const servicedPoints=cappedLog(serviced,250,15)
  fit+=servicedPoints
  if(servicedPoints) fitReasons.push(`${serviced.toLocaleString()} service-provider site relationships (+${servicedPoints})`)

  const towerAccounts=serviceFirms.reduce((sum,firm)=>sum+firm.tower_account_count,0)
  const towerPoints=cappedLog(towerAccounts,150,12)
  fit+=towerPoints
  if(towerPoints) fitReasons.push(`${towerAccounts.toLocaleString()} service-provider tower-account links (+${towerPoints})`)

  const contracts=procurementFirms.reduce((sum,firm)=>sum+firm.observed_contract_count,0)
  const contractPoints=cappedLog(contracts,25,7)
  fit+=contractPoints
  if(contractPoints) fitReasons.push(`${contracts.toLocaleString()} observed public vendor contracts (+${contractPoints})`)

  const customers=procurementFirms.reduce((sum,firm)=>sum+firm.observed_customer_count,0)
  const customerPoints=Math.min(5,customers)
  fit+=customerPoints
  if(customerPoints) fitReasons.push(`${customers.toLocaleString()} observed public buyers (+${customerPoints})`)

  const commercialFirms=publicFirms.filter(firm=>firm.roles.some(role=>countsAsServiceRole(role)||role==='PROCUREMENT_VENDOR'))
  if(commercialFirms.some(firm=>firm.active_last_12m)){
    fit+=5
    fitReasons.push('Recent provider/lab/vendor activity in the last 12 months (+5)')
  }

  const observations=commercialFirms.reduce((sum,firm)=>sum+firm.observation_count,0)
  const observationPoints=cappedLog(observations,500,6)
  fit+=observationPoints
  if(observationPoints) fitReasons.push(`${observations.toLocaleString()} relevant commercial observations (+${observationPoints})`)

  fit=Math.min(100,fit)

  let readiness=0
  if(masterProfile.website){readiness+=12;readinessReasons.push('Official website recorded (+12)')}
  if(masterProfile.headquarters_address||masterProfile.headquarters_city){readiness+=10;readinessReasons.push('Headquarters recorded (+10)')}
  if(masterProfile.company_type){readiness+=8;readinessReasons.push('Company type recorded (+8)')}
  if(ownershipKnown(masterProfile)){readiness+=8;readinessReasons.push('Ownership/parent status reviewed (+8)')}
  if(masterProfile.identity_source_url){readiness+=7;readinessReasons.push('Identity provenance recorded (+7)')}
  if(hasRevenue(masterProfile)){readiness+=5;readinessReasons.push('Revenue context recorded (+5)')}
  if(masterProfile.enrichment_checked_at){readiness+=5;readinessReasons.push('Enrichment review timestamp recorded (+5)')}

  const activeContacts=contacts.filter(contact=>contact.active)
  if(activeContacts.length){
    readiness+=10
    readinessReasons.push(`${activeContacts.length} active contact${activeContacts.length===1?'':'s'} (+10)`)
  }
  if(activeContacts.some(contact=>contact.primary_contact)){
    readiness+=10
    readinessReasons.push('Primary contact identified (+10)')
  }
  if(activeContacts.some(contact=>['decision-maker','executive','champion'].includes(contact.contact_role??''))){
    readiness+=15
    readinessReasons.push('Decision-maker / executive / champion identified (+15)')
  }
  if(activeContacts.some(contact=>contact.email)){
    readiness+=5
    readinessReasons.push('Contact email available (+5)')
  }
  if(activeContacts.some(contact=>contact.phone)){
    readiness+=3
    readinessReasons.push('Contact phone available (+3)')
  }
  if(activeContacts.some(contact=>contact.linkedin_url)){
    readiness+=2
    readinessReasons.push('Contact LinkedIn available (+2)')
  }

  readiness=Math.min(100,readiness)
  return {fitScore:fit,readinessScore:readiness,fitReasons,readinessReasons}
}
