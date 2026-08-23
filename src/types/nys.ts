import type { CoordinateStatus, SourceHealthEntry } from './data'

export interface NysSystem {
  system_id: string
  source_equipment_id: string
  jurisdiction: 'NEW_YORK_STATE_EXCLUDING_NYC'
  source_regime: 'NYS_COOLING_TOWER_REGISTRY_WEEKLY_EXTRACT'
  address: string | null
  city: string | null
  zip: string | null
  source_county: string | null
  property_key: string | null
  property_equipment_count: number
  regulation_compliance: string | null
  ct_status: string | null
  last_update_days: number | null
  last_sampled_days: number | null
  latest_sample_date: string | null
  latest_sample_result: string | null
  operation_duration: string | null
  latitude: number | null
  longitude: number | null
  coordinate_status: CoordinateStatus
  source_latitude_raw: string | null
  source_longitude_raw: string | null
}

export interface NysMetadata {
  schema_version: string
  generated_at: string
  jurisdiction: string
  source_regime: string
  source: {
    dataset_id: string
    name: string
    retrieved_at: string
    source_record_count: number
    source_last_updated_at: string | null
    url: string
    scope_note: string
  }
  normalized_equipment_count: number
  source_duplicate_equipment_rows: number
  source_missing_equipment_id_rows: number
  invalid_coordinate_equipment_count: number
  missing_coordinate_equipment_count: number
  unique_property_count: number
  multi_equipment_property_count: number
  equipment_at_multi_equipment_properties: number
  max_equipment_per_property: number
  source_health?: SourceHealthEntry[]
}

export interface NysSystemsPayload {
  schema_version: string
  metadata: NysMetadata
  summary: {
    registered_equipment: number
    mapped_equipment: number
    non_compliant: number
    compliant: number
    sample_required: number
    update_required: number
    missing_legionella_result: number
    disinfection_required: number
    decommissioned: number
    out_of_service: number
    multi_equipment_properties: number
    equipment_at_multi_equipment_properties: number
    max_equipment_per_property: number
    published_county_counts: Record<string, number>
    status_counts: Record<string, number>
    compliance_counts: Record<string, number>
    sample_result_counts: Record<string, number>
    operation_duration_counts: Record<string, number>
  }
  systems: NysSystem[]
}

export type NysChangeEventType =
  | 'NYS_EQUIPMENT_FIRST_SEEN'
  | 'NYS_EQUIPMENT_NO_LONGER_PRESENT'
  | 'NYS_REG_COMPLIANCE_CHANGED'
  | 'NYS_CT_STATUS_CHANGED'
  | 'NYS_SAMPLE_DATE_CHANGED'
  | 'NYS_SAMPLE_RESULT_CHANGED'
  | 'NYS_OPERATION_DURATION_CHANGED'

export interface NysChangeEvent {
  event_type: NysChangeEventType
  system_id: string
  source_equipment_id: string | null
  address: string | null
  city: string | null
  zip: string | null
  source_county: string | null
  detected_at: string
  source_observation_date: string | null
  previous_value: unknown
  new_value: unknown
  source: string
  evidence_basis: string
}

export interface NysChangesPayload {
  history_schema_version: string
  history_started_at: string
  observed_at: string
  baseline_initialized: boolean
  new_event_count: number
  events: NysChangeEvent[]
}