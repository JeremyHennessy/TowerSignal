export type EvidenceConfidence = 'CONFIRMED' | 'STRONG_SIGNAL' | 'VERIFY'
export type FactClass = 'CONFIRMED_FACT' | 'DERIVED_FACT' | 'COMMERCIAL_SIGNAL'
export type CoordinateStatus = 'VALID' | 'MISSING' | 'INVALID_SOURCE'

export interface SourceMetadata {
  dataset_id: string
  name: string
  retrieved_at: string
  source_record_count: number
  source_last_updated_at: string | null
  url: string
  matched_record_count?: number
}

export interface Metadata {
  generated_at: string
  snapshot_date: string
  sources: SourceMetadata[]
  normalized_system_count: number
  source_duplicate_registration_rows: number
  source_missing_registration_system_id_rows: number
  invalid_coordinate_system_count: number
  oath_requested_ticket_count?: number
  oath_matched_ticket_count?: number
  oath_unmatched_ticket_count?: number
  oath_match_basis?: 'SUMMONS_NUMBER_EXACT'
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
  coordinate_status: CoordinateStatus
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
  oath_case_count?: number
}

export interface SystemsPayload {
  schema_version: string
  metadata: Metadata
  summary: {
    registered_systems: number
    active_equipment: number
    potential_sampling_gaps: number
    recent_confirmed_violations: number
    systems_with_oath_cases?: number
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

export interface OathCharge {
  code: string | null
  code_section: string | null
  description: string | null
  infraction_amount: number | null
}

export interface OathCase {
  ticket_number: string
  ticket_number_source_raw: string | null
  match_basis: 'SUMMONS_NUMBER_EXACT'
  issuing_agency: string | null
  violation_date: string | null
  violation_location: {
    borough: string | null
    block: string | null
    lot: string | null
    house: string | null
    street_name: string | null
    zip: string | null
  }
  hearing_status: string | null
  hearing_result: string | null
  hearing_date: string | null
  decision_date: string | null
  compliance_status: string | null
  violation_description: string | null
  penalty_imposed: number | null
  paid_amount: number | null
  additional_penalties_or_late_fees: number | null
  balance_due: number | null
  total_violation_amount: number | null
  date_judgment_docketed: string | null
  charges: OathCharge[]
}

export interface SystemDetail {
  schema_version: string
  metadata: Metadata
  identity: Pick<SystemSummary, 'system_id' | 'bin' | 'bbl' | 'address' | 'borough' | 'zip' | 'active_equipment' | 'latitude' | 'longitude' | 'coordinate_status'> & {
    source_latitude_raw: string | null
    source_longitude_raw: string | null
  }
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
  oath_case_history?: OathCase[]
  scoring: { score: number; components: ScoreComponent[]; priority_model_version: string }
}
