export type TorontoTowerEvidenceStatus =
  | 'CONFIRMED_DOCUMENTARY_TOWER'
  | 'STRONG_DOCUMENTARY_CANDIDATE'
  | 'AIC_DOCUMENT_CANDIDATE'
  | 'AERIAL_REVIEW_CANDIDATE'
  | 'NO_TOWER_ASSERTION'

export interface TorontoSourceLink {
  source_key: string
  source_record_id: string
  match_basis: string
  source_address: string | null
  record_url: string | null
  record_link_label: string | null
  record_title: string | null
  record_date: string | null
  record_status: string | null
  record_details: { label: string; value: string }[]
}

export interface TorontoSourceCatalogItem {
  dataset_url: string
  dataset_link_label: string
  link_level: 'RECORD_AND_DATASET' | 'DATASET_FALLBACK'
}

export interface TorontoRelationship {
  relationship: string
  organization: string
  source_key: string
  confidence: string
  basis: string
}

export interface TorontoProperty {
  property_id: string
  address_point_id: string
  display_address: string
  municipality: string
  longitude: number
  latitude: number
  identity_basis: string
  identity_confidence: string
  is_original_poc_property: boolean
  tower_evidence_status: TorontoTowerEvidenceStatus
  source_keys: string[]
  source_links: TorontoSourceLink[]
  relationships: TorontoRelationship[]
  aerial_review_rank: number | null
  aerial_visual_similarity_score: number | null
}

export interface TorontoUnresolvedPocProperty {
  property_key: string
  input_address: string | null
  resolution_status: string
  candidate_address_point_ids: string[]
}

export interface TorontoSourceCoverageSummary {
  status?: string
  source_records?: number
  records_with_property_address?: number
  matched_records?: number
  matched_canonical_properties?: number
  unmatched_source_records?: number
  identity_limitation?: string | null
  scope_limitation?: string | null
}

export interface TorontoMarketPayload {
  schema_version: string
  generated_at: string
  feature_status: 'ISOLATED_BETA'
  counts: {
    canonical_properties: number
    original_poc_properties: number
    original_poc_resolved: number
    original_poc_unresolved: number
    documentary_confirmed_properties: number
    strong_documentary_candidates: number
    aic_document_candidates: number | null
    aerial_review_candidates: number
    source_links: number
    record_level_source_links: number
    official_source_families: number
    relationship_edges: number
  }
  true_market_coverage: {
    status: 'UNKNOWN_DENOMINATOR'
    coverage_percent: null
  }
  source_coverage: Record<string, TorontoSourceCoverageSummary>
  source_catalog: Record<string, TorontoSourceCatalogItem>
  limitations: string[]
  unresolved_poc: TorontoUnresolvedPocProperty[]
  properties: TorontoProperty[]
}
