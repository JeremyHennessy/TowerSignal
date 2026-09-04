export type TorontoHistoryEvent = {
  event_id: string
  event_type: string
  property_id: string
  address_point_id?: string | null
  address?: string | null
  detected_at: string
  source_observation_date?: string | null
  source_key?: string | null
  source_record_id?: string | null
  record_title?: string | null
  record_status?: string | null
  evidence_basis: string
  previous_value: unknown
  new_value: unknown
  tower_evidence_status?: string | null
}

export type TorontoHistoryPayload = {
  schema_version: 'toronto-history-1.0'
  history_started_at: string
  observed_at: string
  previous_release_sha: string
  current_release_sha: string
  previous_generated_at?: string | null
  current_generated_at?: string | null
  event_count: number
  properties_with_changes: number
  event_type_counts: Record<string, number>
  source_counts: Record<string, number>
  contract: {
    identity: string
    semantics: string
    baseline: string
  }
  events: TorontoHistoryEvent[]
}
