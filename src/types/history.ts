import type { EvidenceConfidence } from './data'

export type ChangeEventType =
  | 'SYSTEM_FIRST_SEEN'
  | 'SYSTEM_NO_LONGER_PRESENT'
  | 'ACTIVE_EQUIPMENT_CHANGED'
  | 'SAMPLE_REPORTED'
  | 'LATEST_SAMPLE_CHANGED'
  | 'SAMPLING_GAP_ENTERED'
  | 'SAMPLING_GAP_RESOLVED'
  | 'INSPECTION_ADDED'
  | 'VIOLATION_ADDED'
  | 'VIOLATION_STATUS_CHANGED'
  | 'OATH_CASE_ADDED'
  | 'OATH_STATUS_CHANGED'
  | 'OATH_DECISION_CHANGED'
  | 'OATH_PENALTY_CHANGED'
  | 'OATH_BALANCE_CHANGED'
  | 'PLUTO_OWNER_CHANGED'
  | 'HPD_REGISTRATION_CHANGED'
  | 'HPD_CONTACT_ADDED'
  | 'HPD_CONTACT_REMOVED'
  | 'HPD_MANAGING_AGENT_CHANGED'

export interface ChangeEvent {
  event_type: ChangeEventType
  system_id: string
  bbl: string | null
  bin: string | null
  address: string | null
  borough: string | null
  detected_at: string
  source_observation_date: string | null
  previous_value: unknown
  new_value: unknown
  source: string
  evidence_basis: string
  priority_score: number | null
  evidence_confidence: EvidenceConfidence | null
  contact_available: boolean
}

export interface ChangesPayload {
  history_schema_version: string
  history_started_at: string
  observed_at: string
  baseline_initialized: boolean
  new_event_count: number
  events: ChangeEvent[]
}
