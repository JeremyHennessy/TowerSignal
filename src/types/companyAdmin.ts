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
  name: string
  title: string | null
  email: string | null
  phone: string | null
  linkedin_url: string | null
  notes: string | null
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
