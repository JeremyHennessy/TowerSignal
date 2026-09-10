export type KnownFirmIdentityConfidence = 'CONFIRMED' | 'STRONG' | 'VERIFY' | 'UNRESOLVED' | string

export type KnownFirmRole =
  | 'DWT_INSPECTION_PROVIDER'
  | 'DWT_LABORATORY'
  | 'PROCUREMENT_VENDOR'
  | 'DEC_7G_REGISTERED_BUSINESS'
  | 'DOB_NOW_APPLICANT_BUSINESS'
  | 'DOB_NOW_OWNER_BUSINESS'
  | 'LEGACY_DOB_OWNER_BUSINESS'
  | string

export interface KnownFirmSummaryRecord {
  firm_id: string
  canonical_name: string
  strict_name: string
  normalized_name: string
  identity_confidence: KnownFirmIdentityConfidence
  resolution_method: string
  candidate_related_company_ids: string[]
  procurement_company_id?: string | null
  roles: KnownFirmRole[]
  primary_role: KnownFirmRole
  role_counts: Record<string, number>
  source_classes: string[]
  observation_count: number
  observed_site_count: number
  serviced_site_count: number
  contracted_site_count: number
  project_site_count: number
  tower_account_count: number
  mapped_site_count: number
  first_observed_date?: string | null
  latest_observed_date?: string | null
  active_last_12m: boolean
  qualification_count: number
  active_qualification_count: number
  observed_contract_count: number
  active_contract_count: number
  observed_customer_count: number
  repeat_buyer_count: number
  observed_contract_value: number
  service_categories: string[]
  detail_path: string
}

export interface KnownFirmPayload {
  schema_version: '1.0'
  generated_at: string
  domain: 'TOWERSIGNAL_KNOWN_FIRMS'
  summary: {
    known_firm_count: number
    firms_with_site_relationships: number
    firms_with_serviced_sites: number
    firms_with_contracted_sites: number
    firms_with_procurement_evidence: number
    firms_with_dwt_service_evidence: number
    unique_related_site_count: number
    unique_serviced_site_count: number
    unique_contracted_site_count: number
    firm_site_relationship_count: number
    firm_serviced_site_relationship_count: number
    mapped_firm_site_relationship_count: number
    role_firm_counts: Record<string, number>
  }
  evidence_semantics: Record<string, string>
  firms: KnownFirmSummaryRecord[]
}

export interface KnownFirmAlias {
  name: string
  source_class: string
  role: KnownFirmRole
  observation_count: number
}

export interface KnownFirmSiteRelationship {
  site_id: string
  bin?: string | null
  bbl?: string | null
  address?: string | null
  borough?: string | null
  zip?: string | null
  latitude?: number | null
  longitude?: number | null
  system_ids: string[]
  roles: KnownFirmRole[]
  relationship_classes: string[]
  evidence_classes: string[]
  source_record_ids: string[]
  observation_count: number
  first_observed_date?: string | null
  last_observed_date?: string | null
  serviced: boolean
  contracted: boolean
  project_role: boolean
  tower_account_count: number
  mapped: boolean
}

export interface KnownFirmQualification {
  qualification_id?: string | null
  registration_number?: string | null
  city?: string | null
  state?: string | null
  registration_effective_date?: string | null
  registration_expiration_date?: string | null
  qualification_scope?: string | null
  relationship_evidence?: string | null
  active_as_of_generation: boolean
}

export interface KnownFirmDetailPayload {
  schema_version: '1.0'
  generated_at: string
  domain: 'TOWERSIGNAL_KNOWN_FIRM_DETAIL'
  firm: KnownFirmSummaryRecord
  aliases: KnownFirmAlias[]
  site_relationships: KnownFirmSiteRelationship[]
  qualifications: KnownFirmQualification[]
  procurement: null | {
    company_id?: string | null
    canonical_name?: string | null
    observed_sources: string[]
    observed_buyers: string[]
    service_categories: string[]
    procurement_ids: string[]
    metrics: Record<string, unknown>
    value_semantics?: string | null
  }
  evidence_boundaries: Record<string, string>
}
