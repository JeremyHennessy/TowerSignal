export type CompanyRelationshipStatus =
  | 'uncontacted'
  | 'researching'
  | 'outreach-planned'
  | 'contacted'
  | 'engaged'
  | 'opportunity'
  | 'customer'
  | 'not-pursuing'

export type CompanyRevenueType = 'reported' | 'estimated' | 'range' | 'unknown'
export type CompanyRevenueConfidence = 'confirmed' | 'strong' | 'verify' | 'unknown'

export interface CompanyAdminProfile {
  company_id: string
  canonical_name: string
  legal_name: string | null
  rollup_name: string | null
  rollup_company_id: string | null
  rollup_source_name: string | null
  rollup_source_url: string | null
  website: string | null
  website_source_name: string | null
  website_source_url: string | null
  identity_source_name: string | null
  identity_source_url: string | null
  headquarters_address: string | null
  headquarters_city: string | null
  headquarters_region: string | null
  headquarters_postal_code: string | null
  headquarters_country: string | null
  headquarters_source_name: string | null
  headquarters_source_url: string | null
  parent_company_id: string | null
  parent_company_name: string | null
  parent_source_name: string | null
  parent_source_url: string | null
  company_type: string | null
  enrichment_checked_at: string | null
  revenue_amount: number | null
  revenue_low: number | null
  revenue_high: number | null
  revenue_currency: string
  revenue_year: number | null
  revenue_type: CompanyRevenueType
  revenue_source_name: string | null
  revenue_source_url: string | null
  revenue_confidence: CompanyRevenueConfidence
  relationship_status: CompanyRelationshipStatus
  last_contacted_at: string | null
  next_action_date: string | null
  account_owner: string | null
  internal_summary: string | null
  created_at?: string
  updated_at?: string
  created_by?: string | null
  updated_by?: string | null
}

export type CompanyAdminProfilePatch = Omit<
  CompanyAdminProfile,
  'company_id' | 'canonical_name' | 'created_at' | 'updated_at' | 'created_by' | 'updated_by'
>

export interface CompanyAdminContact {
  contact_id: string
  company_id: string
  sales_account_id?: string | null
  name: string
  title: string | null
  email: string | null
  phone: string | null
  linkedin_url: string | null
  notes: string | null
  contact_role: 'decision-maker' | 'champion' | 'technical' | 'procurement' | 'finance' | 'executive' | 'other' | null
  primary_contact: boolean
  source_name: string | null
  source_url: string | null
  verified_at: string | null
  active: boolean
  created_at?: string
  updated_at?: string
}

export interface CompanyAdminActivity {
  activity_id: string
  company_id: string
  sales_account_id?: string | null
  activity_type: string
  occurred_at: string
  contact_id: string | null
  subject: string | null
  details: string | null
  outcome: string | null
  next_action_date: string | null
  created_at?: string
  created_by?: string | null
}

export interface CompanyAdminNote {
  note_id: string
  company_id: string
  sales_account_id?: string | null
  note: string
  created_at?: string
  updated_at?: string
  created_by?: string | null
  updated_by?: string | null
}

export interface CompanyAdminSnapshot {
  profile: CompanyAdminProfile | null
  contacts: CompanyAdminContact[]
  activities: CompanyAdminActivity[]
  notes: CompanyAdminNote[]
}


export type CompanyResearchStatus = 'unreviewed' | 'researching' | 'verified' | 'needs-review' | 'complete'

export interface CompanyResearchQueueItem {
  company_id: string
  sales_account_id?: string | null
  priority_score: number
  priority_reason: string
  missing_fields: string[]
  status: CompanyResearchStatus
  research_owner: string | null
  last_researched_at: string | null
  queued_at: string
  updated_at: string
  created_by: string | null
  updated_by: string | null
}

export type CompanyAuditChangeSource = 'manual' | 'import' | 'system' | 'database'

export interface CompanyAuditEntry {
  change_id: number
  company_id: string
  entity_type: string
  entity_id: string
  operation: string
  field_name: string
  old_value: unknown
  new_value: unknown
  change_source: CompanyAuditChangeSource
  import_batch_id: string | null
  changed_at: string
  changed_by: string | null
}


export type CompanyOpportunityStage =
  | 'lead'
  | 'qualified'
  | 'demo-scheduled'
  | 'demo-complete'
  | 'proposal'
  | 'negotiation'
  | 'closed-won'
  | 'closed-lost'
  | 'nurture'

export interface CompanySalesOpportunity {
  opportunity_id: string
  company_id: string
  sales_account_id?: string | null
  name: string
  stage: CompanyOpportunityStage
  product_scope: string[]
  estimated_arr: number | null
  one_time_value: number | null
  probability_percent: number | null
  primary_contact_id: string | null
  lead_source: string | null
  target_close_date: string | null
  next_step: string | null
  next_action_date: string | null
  demo_scheduled_at: string | null
  proposal_sent_at: string | null
  won_at: string | null
  lost_at: string | null
  lost_reason: string | null
  notes: string | null
  created_at?: string
  updated_at?: string
}

export type CompanyTaskType = 'call' | 'email' | 'demo' | 'proposal' | 'research' | 'follow-up' | 'meeting' | 'other'
export type CompanyTaskPriority = 'low' | 'medium' | 'high'
export type CompanyTaskStatus = 'open' | 'completed' | 'cancelled'

export interface CompanySalesTask {
  task_id: string
  company_id: string
  sales_account_id?: string | null
  opportunity_id: string | null
  contact_id: string | null
  title: string
  task_type: CompanyTaskType
  priority: CompanyTaskPriority
  status: CompanyTaskStatus
  due_at: string | null
  completed_at: string | null
  notes: string | null
  created_at?: string
  updated_at?: string
}


export type CompanySalesAccountClassification =
  | 'target'
  | 'active-prospect'
  | 'customer'
  | 'former-customer'
  | 'partner'
  | 'competitor'
  | 'do-not-pursue'

export interface CompanySalesAccount {
  sales_account_id: string
  primary_company_id: string
  display_name: string
  account_classification: CompanySalesAccountClassification
  record_status: 'active' | 'merged'
  merged_into_sales_account_id?: string | null
  parent_name: string | null
  parent_source_url: string | null
  account_owner: string | null
  sales_notes: string | null
  created_at?: string
  updated_at?: string
}

export interface CompanySalesAccountMember {
  sales_account_id: string
  company_id: string
  member_type: 'primary-source' | 'source-identity' | 'brand' | 'subsidiary' | 'legal-entity'
  is_primary: boolean
  relationship_source_name: string | null
  relationship_source_url: string | null
  created_at?: string
}


export type CompanyRollupSuggestionStatus = 'pending' | 'accepted' | 'rejected' | 'not-same' | 'superseded'
export type CompanyRollupSuggestionConfidence = 'high' | 'medium' | 'low'

export interface CompanyRollupSuggestion {
  suggestion_id: string
  candidate_sales_account_id: string
  suggested_sales_account_id: string
  score: number
  confidence: CompanyRollupSuggestionConfidence
  evidence: string[]
  status: CompanyRollupSuggestionStatus
  generated_at: string
  updated_at: string
  reviewed_at: string | null
  reviewed_by: string | null
  review_note: string | null
}
