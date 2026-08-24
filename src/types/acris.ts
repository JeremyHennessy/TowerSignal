export interface AcrisSummaryFields {
  acris_recent_document_count?: number
  latest_acris_recorded_date?: string | null
  acris_deed_count?: number
  acris_mortgage_count?: number
  acris_lease_count?: number
  acris_recorded_party_count?: number
}

export interface AcrisMetadataFields {
  acris_cache_available?: boolean
  acris_cache_generated_at?: string | null
  acris_cache_cutoff?: string | null
  acris_cache_lookback_days?: number | null
  acris_requested_bbl_count?: number
  acris_matched_bbl_count?: number
  acris_matched_document_count?: number
  acris_cache_universe_aligned?: boolean
}

export interface AcrisPayloadSummaryFields {
  systems_with_recent_acris_activity?: number
}

export interface AcrisParty {
  party_type: string | null
  name: string | null
  address_1: string | null
  address_2: string | null
  country: string | null
  city: string | null
  state: string | null
  zip: string | null
}

export interface AcrisLegalContext {
  property_type: string | null
  street_number: string | null
  street_name: string | null
  unit: string | null
}

export interface AcrisDocument {
  document_id: string
  bbl: string
  record_type: string | null
  crfn: string | null
  recorded_borough: string | null
  doc_type: string | null
  document_date: string | null
  recorded_date: string | null
  modified_date: string | null
  document_amount: number | null
  percent_transferred: number | null
  legal_context: AcrisLegalContext[]
  parties: AcrisParty[]
  source: 'NYC_ACRIS_REAL_PROPERTY'
  match_basis: 'BBL_EXACT_DOCUMENT_ID_EXACT'
}

export interface AcrisPropertyActivity {
  recent_document_count: number
  latest_recorded_date: string | null
  deed_count: number
  mortgage_count: number
  lease_count: number
  assignment_count: number
  satisfaction_count: number
  recorded_party_count: number
  displayed_document_count: number
  documents: AcrisDocument[]
}
