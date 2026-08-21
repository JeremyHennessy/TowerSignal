export type EvidenceConfidence = 'CONFIRMED' | 'STRONG_SIGNAL' | 'VERIFY'
export type FactClass = 'CONFIRMED_FACT' | 'DERIVED_FACT' | 'COMMERCIAL_SIGNAL'

export interface SourceMetadata {
  dataset_id: string
  name: string
  retrieved_at: string
  source_record_count: number
  source_last_updated_at: string | null
  url: string
}

export interface Metadata {
  generated_at: string
  snapshot_date: string
  sources: SourceMetadata[]
  normalized_system_count: number
  source_duplicate_registration_rows: number
  source_missing_registration_system_id_rows: number
  rules_version: string
  priority_model_version: string
}

export interface ScoreComponent { points: number; reason: string }

export interface SystemSummary {
  system_id: string
  bin: string | null
  bbl: string | null
  address: string | null
  borough: string | null
  zip: string | null
  active_equipment: number
  latitude: number | null
  longitude: number | null
  latest_sample_date: string | null
  days_since_latest_sample: number | null
  latest_inspection_date: string | null
  latest_inspection_type: string | null
  confirmed_violation: boolean
  recent_confirmed_violation: boolean
  violation_types: string[]
  signal_types: string[]
  primary_signal: string
  evidence_confidence: EvidenceConfidence
  priority_score: number
  score_components: ScoreComponent[]
}

export interface SystemsPayload {
  schema_version: string
  metadata: Metadata
  summary: {
    registered_systems: number
    active_equipment: number
    potential_sampling_gaps: number
    recent_confirmed_violations: number
  }
  systems: SystemSummary[]
}

export interface SignalDetail {
  type: string
  title: string
  evidence_confidence: EvidenceConfidence
  fact_class: FactClass
  date: string | null
  reason: string
  violation_types?: string[]
  inspection_type?: string | null
}

export interface Violation {
  violation_code: string | null
  law_section: string | null
  violation_text: string | null
  violation_type: string | null
  citation_text: string | null
  summons_number: string | null
}

export interface Inspection {
  system_id: string
  inspection_date: string | null
  inspection_type: string
  status: string | null
  active_equipment_at_publication: number
  violation_count: number
  violations: Violation[]
}

export interface SystemDetail {
  schema_version: string
  metadata: Metadata
  identity: Pick<SystemSummary, 'system_id' | 'bin' | 'bbl' | 'address' | 'borough' | 'zip' | 'active_equipment' | 'latitude' | 'longitude'>
  sample_history: {
    source_raw: string
    dates: string[]
    malformed_values: string[]
    latest_sample_date: string | null
    previous_sample_date: string | null
    latest_sample_interval_days: number | null
    intervals_days: number[]
    sample_count: number
  }
  signals: SignalDetail[]
  inspection_history: Inspection[]
  scoring: { score: number; components: ScoreComponent[]; priority_model_version: string }
}
