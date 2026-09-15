export interface LegionellaSummary {
  legionella_event_ids?: string[]
  legionella_named_event_ids?: string[]
  legionella_area_only_event_ids?: string[]
}
export interface LegionellaObservation {
  observation_id: string
  result: string
  remediation: string
  source_url: string
  source_date: string | null
  source_locator: string
  source_note: string | null
  retrieved_at: string
  content_sha256: string
}
export interface LegionellaBuilding {
  published_address: string
  resolution: {
    status: string
    reason: string
    bin?: string
    entity_level?: 'BUILDING'
    system_specific?: false
    systems: Array<{ system_id: string; address: string; bin: string; bbl: string; zip: string; active_equipment: number }>
  }
  observations: LegionellaObservation[]
}
export interface LegionellaIncident {
  event_id: string
  name: string
  borough: string
  zip_codes: string[]
  status: string
  status_source_url: string
  status_observed_at: string
  named_building_count: number
  published_building_count: number
  named_system_count: number
  area_only_system_count: number
  unresolved_building_count: number
  buildings: LegionellaBuilding[]
  related_articles: Array<{ item_id: string; title: string | null; url: string; published_date: string | null }>
}
export interface LegionellaTowerLinks {
  domain: 'LEGIONELLA_TOWER_LINKS'
  generated_at: string
  events: LegionellaIncident[]
  system_links: Record<string, Array<{ event_id: string; relationship: 'NAMED_BUILDING' | 'AREA_CONTEXT'; shares_published_zip: boolean; system_specific: false }>>
  source_documents: Array<{ source_url: string; title: string; source_date: string | null; content_sha256: string }>
  coverage: { alert_items_considered: number; related_article_count: number; scope: string }
  evidence_boundary: string
}
