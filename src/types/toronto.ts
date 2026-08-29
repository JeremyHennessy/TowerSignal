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
    relationship_edges: number
  }
  true_market_coverage: {
    status: 'UNKNOWN_DENOMINATOR'
    coverage_percent: null
  }
  source_coverage: Record<string, Record<string, unknown>>
  limitations: string[]
  unresolved_poc: TorontoUnresolvedPocProperty[]
  properties: TorontoProperty[]
}
