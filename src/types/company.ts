export interface CompanyAlias {
  company_id: string
  alias: string
  normalized_alias: string
  source: string
  source_vendor_id?: string | null
  address?: string | null
  normalized_address?: string | null
  confidence: string
  resolution_method: string
}

export interface CompanyMetrics {
  observed_contract_count: number
  active_contract_count: number
  historical_contract_count: number
  observed_contract_value: number
  active_observed_contract_value: number
  observed_spend_to_date: number
  observed_customer_count: number
  active_customer_count: number
  cooling_tower_related_contract_count: number
  water_treatment_contract_count: number
  legionella_contract_count: number
  mechanical_contract_count: number
  median_contract_duration?: number | null
  average_contract_duration?: number | null
  contracts_expiring_12m: number
  contracts_expiring_24m: number
  contracts_expiring_36m: number
  geographic_state_count: number
  geographic_market_count: number
  largest_observed_customer_value: number
  top_5_customer_value: number
  observed_customer_concentration?: number | null
  repeat_customer_count: number
  observable_customer_retention?: number | null
}

export interface CompanyIntelligenceRecord {
  schema_version: string
  company_id: string
  canonical_name: string
  company_type: string
  website?: string | null
  headquarters?: string | null
  status: string
  current_parent_company_id?: string | null
  current_sponsor_company_id?: string | null
  identity_confidence: string
  first_seen?: string | null
  last_seen?: string | null
  identity_scope: string
  identity_basis: string
  strict_vendor_key: string
  normalized_base_name: string
  cross_source_resolution_confidence: string
  cross_source_resolution_method: string
  candidate_related_company_ids: string[]
  aliases: CompanyAlias[]
  observed_sources: string[]
  observed_buyers: string[]
  service_categories: string[]
  procurement_ids: string[]
  procurement_observation_count: number
  city_record_observation_count: number
  city_record_recent_award_count: number
  metrics: CompanyMetrics
  value_semantics: string
}

export interface CompanyIntelligencePayload {
  schema_version: string
  generated_at: string
  summary: {
    observed_vendor_company_count: number
    procurement_observation_count: number
    cross_source_exact_label_company_count: number
    companies_requiring_resolution_review: number
    unresolved_observation_count: number
    value_semantics: string
  }
  companies: CompanyIntelligenceRecord[]
  unresolved_vendor_observations: Array<{
    procurement_id?: string | null
    source?: string | null
    vendor_raw?: string | null
    observed_company_id: string
    normalized_base_name: string
    resolution_confidence: string
    resolution_method: string
    candidate_company_ids: string[]
  }>
}
