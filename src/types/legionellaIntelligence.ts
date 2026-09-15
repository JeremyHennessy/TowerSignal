export interface NamedBuildingObservation {
  observation_id: string
  cluster_id: string
  cluster_status: string
  borough: string
  address: string
  bin: string
  result: string
  action: string
  completion: string
  document_date: string
  event_date: string | null
  source_url: string
  related_article_urls: string[]
  retrieved_at: string
  content_sha256: string
  match_basis: string
  match_scope: string
  system_ids: string[]
}

export interface LegionellaPropertyMatches {
  domain: 'LEGIONELLA_PROPERTY_MATCHES'
  generated_at: string
  registry_generated_at: string
  evidence_boundary: string
  matched_observations: NamedBuildingObservation[]
  unresolved: Array<Omit<NamedBuildingObservation, 'bin' | 'system_ids' | 'match_basis' | 'match_scope'> & { match_status: string }>
  sources: Array<{ url: string; content_sha256: string; retrieved_at: string }>
  summary: {
    named_buildings_matched: number
    systems_with_named_building_evidence: number
    matched_observation_count: number
    unresolved_observation_count: number
    systems_with_area_context: number
  }
}
