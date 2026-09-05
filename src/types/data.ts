export type EvidenceConfidence = 'CONFIRMED' | 'STRONG_SIGNAL' | 'VERIFY'
export type FactClass = 'CONFIRMED_FACT' | 'DERIVED_FACT' | 'COMMERCIAL_SIGNAL'
export type CoordinateStatus = 'VALID' | 'MISSING' | 'INVALID_SOURCE'
export type SourceHealthStatus = 'HEALTHY' | 'WARNING' | 'FAILED'
export type DobCommercialRelevance = 'COOLING_TOWER_EXPLICIT' | 'MECHANICAL_OR_BOILER' | 'PROPERTY_PROJECT'

export interface SourceMetadata {
  dataset_id: string
  name: string
  retrieved_at: string
  source_record_count: number
  source_last_updated_at: string | null
  url: string
  matched_record_count?: number
  source_query_scope?: string
}

export interface SourceHealthEntry {
  source_key: string
  dataset_id: string
  name: string
  entity_unit: string
  retrieved_record_count: number
  requested_entity_count: number
  normalized_entity_count: number
  matched_entity_count: number
  attached_entity_count: number
  displayed_entity_count: number
  coverage_percentage: number | null
  previous_coverage_percentage: number | null
  coverage_change_percentage_points: number | null
  coverage_note: string
  status: SourceHealthStatus
  status_reasons: string[]
}

export interface Metadata {
  generated_at: string
  snapshot_date: string
  sources: SourceMetadata[]
  source_health?: SourceHealthEntry[]
  normalized_system_count: number
  source_duplicate_registration_rows: number
  source_missing_registration_system_id_rows: number
  invalid_coordinate_system_count: number
  oath_requested_ticket_count?: number
  oath_matched_ticket_count?: number
  oath_unmatched_ticket_count?: number
  oath_match_basis?: 'SUMMONS_NUMBER_EXACT'
  pluto_requested_bbl_count?: number
  pluto_matched_bbl_count?: number
  dob_requested_bbl_count?: number
  dob_matched_bbl_count?: number
  dob_matched_filing_count?: number
  dob_explicit_cooling_tower_filing_count?: number
  dob_mechanical_or_boiler_filing_count?: number
  hpd_requested_bbl_count?: number
  hpd_matched_registration_bbl_count?: number
  hpd_matched_contact_bbl_count?: number
  planimetric_requested_bin_count?: number
  planimetric_matched_bin_count?: number
  planimetric_matched_feature_count?: number
  planimetric_match_basis?: 'BIN_EXACT'
  planimetric_feature_identity_basis?: 'GLOBALID'
  planimetric_imagery_year?: number
  building_footprint_requested_bin_count?: number
  building_footprint_matched_bin_count?: number
  building_footprint_matched_feature_count?: number
  building_footprint_match_basis?: 'BIN_EXACT'
  nyc_water_signal_cache_available?: boolean
  nyc_water_signal_match_basis?: 'EXACT_SOURCE_BBL_OR_BIN'
  nyc_water_signal_source_record_count?: number
  nyc_water_signal_systems_attached?: number
  nyc_water_signal_attached_record_count?: number
  nyc_lead_service_line_cache_available?: boolean
  nyc_lead_service_line_dataset_id?: 'jqfp-uff7'
  nyc_lead_service_line_source_record_count?: number
  nyc_lead_service_line_requested_bbl_count?: number
  nyc_lead_service_line_matched_bbl_count?: number
  nyc_lead_service_line_matched_record_count?: number
  nyc_lead_service_line_match_basis?: 'BBL_EXACT'
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
  registration_date?: string | null
  sample_count?: number
  inspection_count?: number
  violation_citation_count?: number
  latest_violation_date?: string | null
  oath_balance_due_total?: number
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
  pluto_match?: boolean
  pluto_owner_name?: string | null
  pluto_building_area_sqft?: number | null
  dob_activity_count?: number
  dob_recent_activity_count?: number
  dob_explicit_cooling_tower_count?: number
  dob_mechanical_or_boiler_count?: number
  latest_dob_activity_date?: string | null
  hpd_contact_count?: number
  planimetric_bin_match?: boolean
  planimetric_building_tower_count?: number
  building_footprint_bin_match?: boolean
  building_footprint_count?: number
  nyc_building_water_signal_count?: number
  nyc_building_water_signal_types?: string[]
  nyc_lead_service_line_record_count?: number
  nyc_lead_service_line_materials?: string[]
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
    systems_with_pluto_context?: number
    systems_with_dob_activity?: number
    systems_with_recent_dob_activity?: number
    systems_with_explicit_cooling_tower_dob_activity?: number
    systems_with_hpd_registration?: number
    systems_with_hpd_contacts?: number
    systems_with_planimetric_bin_match?: number
    systems_with_building_footprint_match?: number
    systems_with_nyc_building_water_signals?: number
    systems_with_nyc_lead_service_line_records?: number
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

export interface BuildingContext {
  bbl: string | null
  owner_name: string | null
  land_use: string | null
  building_class: string | null
  lot_area_sqft: number | null
  building_area_sqft: number | null
  floors: number | null
  residential_units: number | null
  total_units: number | null
  year_built: number | null
  year_altered_1: number | null
  year_altered_2: number | null
  source: 'NYC_DCP_PLUTO'
}

export interface DobActivity {
  job_filing_number: string | null
  bbl: string | null
  filing_status: string | null
  job_type: string | null
  job_description: string | null
  initial_cost: number | null
  filing_date: string | null
  current_status_date: string | null
  first_permit_date: string | null
  approved_date: string | null
  signoff_date: string | null
  activity_date: string | null
  mechanical_systems: boolean
  boiler_equipment: boolean
  explicit_cooling_tower_mention: boolean
  commercial_relevance: DobCommercialRelevance
  owner_business_name: string | null
  applicant_business_name: string | null
  source: 'NYC_DOB_NOW_JOB_APPLICATION_FILINGS'
  match_basis: 'BBL_EXACT'
}

export interface HpdContact {
  registration_contact_id: string | null
  type: string | null
  description: string | null
  corporation_name: string | null
  person_name: string | null
  title: string | null
  business_address: string | null
  source: 'NYC_HPD_REGISTRATION_CONTACTS'
}

export interface HpdRegistrationContext {
  registration_id: string | null
  building_id: string | null
  last_registration_date: string | null
  contacts: HpdContact[]
  source: 'NYC_HPD_MULTIPLE_DWELLING_REGISTRATION'
}

export type PlanimetricGeometry =
  | { type: 'Polygon'; coordinates: number[][][] }
  | { type: 'MultiPolygon'; coordinates: number[][][][] }

export interface PlanimetricBuildingTowerFeature {
  source_id: string | null
  global_id: string
  bin: string
  feature_code: string | null
  sub_feature_code: string | null
  status: string | null
  geometry: PlanimetricGeometry
  source: 'NYC_OTI_PLANIMETRICS_COOLING_TOWERS'
  match_basis: 'BIN_EXACT'
  feature_identity_basis: 'GLOBALID'
  imagery_year: 2022
}

export interface BuildingFootprintFeature {
  bin: string
  name: string | null
  doitt_id: string | null
  object_id: string | null
  shape_area: number | null
  base_bbl: string | null
  mappluto_bbl: string | null
  construction_year: number | null
  feature_code: string | null
  geometry_source: string | null
  ground_elevation_ft: number | null
  height_roof_ft: number | null
  last_edited_date: string | null
  last_status_type: string | null
  geometry: PlanimetricGeometry
  source: 'NYC_OTI_BUILDING_FOOTPRINTS'
  match_basis: 'BIN_EXACT'
  feature_identity_basis: 'DOITT_ID' | 'OBJECTID'
}

export interface NycLeadServiceLineRecord {
  record_id: string | null
  bbl: string | null
  address: string | null
  material: string | null
  record_type: string | null
  city_owned: string | null
  source_dataset_id: 'jqfp-uff7'
}

export interface NycLeadServiceLineContext {
  summary: {
    record_count: number
    material_counts: Record<string, number>
    record_type_counts: Record<string, number>
    city_owned_counts: Record<string, number>
  }
  records: NycLeadServiceLineRecord[]
  evidence_boundaries: {
    property_link: string
    material: string
  }
  source: {
    dataset_id: 'jqfp-uff7'
    name: string
    url: string
    source_record_count: number
    source_last_updated_at: string | null
    generated_at: string
  }
}

export interface NycBuildingWaterSignalsContext {
  summary: {
    record_count: number
    water_311_building_signal_count: number
    hpd_open_water_violation_count: number
    dob_water_job_filing_count: number
    dob_water_permit_count: number
    ll84_water_benchmark_count: number
    dob_applicant_business_count: number
    category_counts: Record<string, number>
    latest_observation_date: string | null
  }
  water_311_requests: Array<Record<string, unknown>>
  hpd_open_water_violations: Array<Record<string, unknown>>
  dob_water_job_filings: Array<Record<string, unknown>>
  dob_water_permits: Array<Record<string, unknown>>
  ll84_water_benchmarks: Array<Record<string, unknown>>
  evidence_boundaries: {
    property_link: string
    roles: string
    ll84: string
  }
  source: {
    dataset_ids: string[]
    source_record_count: number
    generated_at: string
    query_boundaries: Record<string, unknown>
  }
}

export interface HistoricalProfile {
  registration_date: string | null
  registration_age_days: number | null
  first_public_evidence_date: string | null
  sample: {
    first_reported_date: string | null
    latest_reported_date: string | null
    reported_sample_count: number
    average_interval_days: number | null
    longest_interval_days: number | null
  }
  inspection: {
    first_inspection_date: string | null
    latest_inspection_date: string | null
    inspection_count: number
    inspections_with_violations: number
    violation_citation_count: number
    first_violation_date: string | null
    latest_violation_date: string | null
  }
  oath: {
    case_count: number
    penalty_imposed_total: number
    paid_amount_total: number
    balance_due_total: number
  }
}

export interface SystemDetail {
  schema_version: string
  metadata: Metadata
  identity: Pick<SystemSummary, 'system_id' | 'bin' | 'bbl' | 'address' | 'borough' | 'zip' | 'active_equipment' | 'latitude' | 'longitude' | 'coordinate_status'> & {
    source_latitude_raw: string | null
    source_longitude_raw: string | null
  }
  historical_profile?: HistoricalProfile
  building_context?: BuildingContext | null
  dob_activity_history?: DobActivity[]
  hpd_registration?: HpdRegistrationContext | null
  planimetric_building_tower_features?: PlanimetricBuildingTowerFeature[]
  building_footprints?: BuildingFootprintFeature[]
  nyc_building_water_signals?: NycBuildingWaterSignalsContext | null
  nyc_lead_service_lines?: NycLeadServiceLineContext | null
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
