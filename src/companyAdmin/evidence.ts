export interface ParentEntity { parent_entity_id:string; display_name:string; website:string|null }
export interface ParentRelationship {
  relationship_id:string; sales_account_id:string; parent_entity_id:string
  relationship_type:'parent'|'ultimate-parent'; evidence_url:string; evidence_note:string
  observed_on:string; valid_from:string|null; valid_to:string|null
  status:'proposed'|'confirmed'|'disputed'|'historical'
}
export interface EnrichmentSource {
  source_id:string; sales_account_id:string; source_url:string; expected_name:string; enabled:boolean
  last_attempt_at:string|null; last_success_at:string|null; last_outcome:string|null; last_error:string|null
}
export interface EnrichmentRun {
  run_id:string; started_at:string; finished_at:string|null; status:string; checked_count:number
  observed_count:number; unresolved_count:number; failed_count:number; candidate_count:number
}
export interface EnrichmentCandidate {
  candidate_id:string; sales_account_id:string; source_id:string; field_name:string; proposed_value:unknown
  source_url:string; evidence_excerpt:string; last_observed_at:string; status:'pending'|'reviewed'|'rejected'
}
export interface CompanyEvidence {
  parents:ParentEntity[]; relationships:ParentRelationship[]; sources:EnrichmentSource[]
  runs:EnrichmentRun[]; candidates:EnrichmentCandidate[]
}
export function httpsUrl(value:string):boolean {
  try { const url=new URL(value);return url.protocol==='https:'&&!url.username&&!url.password&&!url.hash&&(!url.port||url.port==='443') }
  catch {return false}
}
export function validObservationDate(value:string):boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || value.startsWith('0000')) return false
  const date=new Date(`${value}T00:00:00Z`)
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0,10)===value
}
export function observationText(value:unknown):string {
  if(typeof value==='string')return value
  if(value&&typeof value==='object')return Object.values(value).filter(v=>typeof v==='string'&&v.trim()).join(', ')
  return 'No readable value recorded'
}
