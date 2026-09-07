export interface CoverageAuditIdentifierBorough {
  systems: number
  with_bbl: number
  with_bin: number
}

export interface CoverageAuditSource {
  source_key: string
  name: string
  integration_status: string
  identity_key: string
  scope_classification: string
  decisions_supported: string[]
  requested_entity_count?: number
  retrieved_record_count?: number
  normalized_entity_count?: number
  matched_entity_count?: number
  attached_entity_count?: number
  coverage_percentage?: number | null
  borough_breakdown?: Record<string, number> | null
}

export interface CoverageAuditArtifact {
  source_key: string
  artifact: string
  integration_status: string
  authoritative_contract: string
  decisions_supported: string[]
  exists: boolean
  artifact_bytes: number
  schema_version?: string | null
  generated_at?: string | null
  summary_metrics?: Record<string, string | number | boolean | null>
  metadata_metrics?: Record<string, string | number | boolean | null>
}

export interface CoverageAuditGap {
  gap_key: string
  classification: string
  observed: Record<string, unknown>
  interpretation: string
  next_action: string
}

export interface CoverageAuditPayload {
  schema_version: string
  generated_at: string
  audit_scope: string
  nyc: {
    system_count: number
    identifier_coverage: {
      systems: number
      with_bbl: number
      missing_bbl: number
      unique_bbl: number
      with_bin: number
      missing_bin: number
      unique_bin: number
      by_borough: Record<string, CoverageAuditIdentifierBorough>
    }
    metadata_metrics: Record<string, unknown>
  }
  nys: {
    system_count: number
    identity_regime: string
    metadata_metrics: Record<string, unknown>
  }
  standardized_coverage_sources: CoverageAuditSource[]
  source_artifacts: CoverageAuditArtifact[]
  gap_analysis: CoverageAuditGap[]
  history_depth: Record<string, {
    artifact?: string
    exists?: boolean
    bytes?: number
    event_count?: number | null
    history_started_at?: string | null
    generated_at?: string | null
  }>
  storage_footprint: {
    public_data_total_bytes?: number
    top_level_artifact_bytes?: number
    detail_artifact_bytes?: number
    history_artifact_bytes?: number
    systems_json_bytes?: number
    source_health_json_bytes?: number
    file_count?: number
    detail_file_count?: number
  }
  governance: {
    priority_score_1_0_changed: boolean
    opportunity_score_authorized: boolean
    fuzzy_matching_used: boolean
    new_source_ingestion_performed: boolean
    ui_redesign_performed: boolean
    follow_on_rule: string
  }
}
