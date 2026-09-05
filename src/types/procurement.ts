export type ProcurementConfidence = 'CONFIRMED' | 'STRONG' | 'VERIFY' | 'UNRESOLVED'
export type FacilityLinkConfidence = 'CONFIRMED' | 'STRONG' | 'CONTEXT' | 'UNLINKED'

export interface ProcurementSourceHealth {
  source: string
  status: string
  last_success?: string | null
  last_attempt?: string | null
  record_count: number
  relevant_record_count: number
  normalized_contract_count: number
  normalized_notice_count: number
  resolved_company_count: number
  unresolved_vendor_count: number
  facility_link_count: number
  exact_tower_link_count: number
  pagination_complete: boolean
  schema_valid: boolean
  freshness?: string | null
  status_reasons?: string[]
  fiscal_years?: number[]
  subvendor_record_count?: number
  subvendor_pagination_complete?: boolean
}

export interface ProcurementRecord {
  schema_version: string
  procurement_id: string
  source: string
  source_record_id: string
  source_contract_id?: string | null
  notice_id?: string | null
  vendor_raw?: string | null
  vendor_address?: string | null
  vendor_role?: string | null
  company_id?: string | null
  company_match_confidence?: ProcurementConfidence | null
  company_resolution_method?: string | null
  buyer_name?: string | null
  agency?: string | null
  title?: string | null
  description?: string | null
  procurement_text?: string | null
  service_category: string
  service_confidence: ProcurementConfidence
  classification_terms?: string[]
  classification_reason?: string | null
  original_amount?: number | null
  current_amount?: number | null
  spend_to_date?: number | null
  amount?: number | null
  amount_evidence?: string | null
  observed_value_evidence?: string | null
  start_date?: string | null
  end_date?: string | null
  award_date?: string | null
  due_date?: string | null
  notice_start_date?: string | null
  notice_end_date?: string | null
  status?: string | null
  notice_type?: string | null
  procurement_category?: string | null
  selection_method?: string | null
  pin?: string | null
  scope?: string | null
  source_url?: string | null
  retrieved_at: string
  source_updated_at?: string | null
  facility_id?: string | null
  facility_match_confidence?: FacilityLinkConfidence | null
  tower_account_system_ids?: string[]
  tower_link_confidence?: FacilityLinkConfidence | null
  entity_contract_number?: string | null
  commodity_line?: string | null
  source_dataset_id?: string | null
  source_fiscal_year_end?: string | null
}

export interface CityRecordProcurementPayload {
  schema_version: string
  generated_at: string
  source: { dataset_id: string; name: string; dataset_page?: string; retrieved_at: string; as_of_date: string; award_lookback_days: number }
  summary: { scoped_record_count: number; relevant_record_count: number; open_relevant_opportunities: number; recent_relevant_awards: number; unresolved_vendor_count: number; classification_counts: Record<string, number> }
  source_health: ProcurementSourceHealth
  notices: ProcurementRecord[]
}

export interface CheckbookProcurementPayload {
  schema_version: string
  generated_at: string
  source: { name: string; api_url: string; documentation_url: string; retrieved_at: string }
  summary: { citywide_source_transaction_count: number; citywide_subvendor_source_transaction_count: number; citywide_unique_prime_contract_count: number; citywide_relevant_contract_count: number; edc_source_transaction_count: number; edc_unique_prime_contract_count: number; edc_unique_contract_line_count?: number; edc_relevant_contract_count: number; relevant_contract_count: number; unresolved_vendor_count: number; classification_counts: Record<string, number>; value_semantics: string }
  source_health: Record<string, ProcurementSourceHealth>
  contracts: ProcurementRecord[]
}

export interface NysAuthoritySourceHealth {
  source: string
  dataset_id: string
  dataset_name: string
  status: string
  record_count: number
  retrieved_candidate_count: number
  relevant_record_count: number
  vendor_record_count: number
  pagination_complete: boolean
  schema_valid: boolean
  retrieved_at: string
  coverage_note: string
}

export interface NysAuthorityProcurementPayload {
  schema_version: string
  generated_at: string
  source: { name: string; api_root: string; dataset_ids: string[]; coverage: string; value_semantics: string }
  summary: { source_dataset_count: number; source_record_count: number; retrieved_candidate_count: number; relevant_contract_count: number; vendor_record_count: number; classification_counts: Record<string, number>; value_semantics: string }
  source_health: NysAuthoritySourceHealth[]
  contracts: ProcurementRecord[]
}

export interface OpenBookWaterPayload {
  schema_version: string
  generated_at: string
  as_of_date: string
  domain: 'NYS_OPEN_BOOK_WATER_CONTRACT_TRANSACTIONS'
  source: Record<string, unknown>
  evidence_semantics: Record<string, string>
  summary: {
    source_transaction_count: number
    source_contract_count: number
    relevant_contract_count: number
    relevant_transaction_count: number
    relevant_vendor_count: number
    classification_counts: Record<string, number>
  }
  contracts: ProcurementRecord[]
}

export interface NychaWaterPayload {
  schema_version: string
  generated_at: string
  as_of_date: string
  domain: 'NYCHA_WATER_CONTRACT_RELEASE_LINES'
  source: Record<string, unknown>
  evidence_semantics: Record<string, string>
  summary: {
    fiscal_year_count: number
    source_record_count: number
    relevant_release_line_count: number
    relevant_contract_count: number
    relevant_vendor_count: number
    relevant_location_count: number
    classification_counts: Record<string, number>
  }
  source_health: Array<Record<string, unknown>>
  records: ProcurementRecord[]
}

export interface ProcurementBundle {
  cityRecord: CityRecordProcurementPayload
  checkbook: CheckbookProcurementPayload
  nysAuthorities: NysAuthorityProcurementPayload | null
  openBookWater: OpenBookWaterPayload | null
  nychaWater: NychaWaterPayload | null
  sourceErrors: {
    nysAuthorities?: string
    openBookWater?: string
    nychaWater?: string
  }
}
