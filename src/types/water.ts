import type { ProcurementConfidence } from './procurement'

export interface DomesticWaterMarketProvider {
  provider_id: string
  provider_key: string
  aliases: Array<{ name: string; inspection_count: number }>
  inspection_count: number
  observed_building_count: number
  observed_tank_count: number
  reporting_years: string[]
  first_observed_date: string | null
  latest_observed_date: string | null
  relationship_basis: string
  market_share_semantics: string
}

export interface DomesticWaterMarketLaboratory {
  lab_id: string
  lab_key: string
  aliases: Array<{ name: string; inspection_count: number }>
  inspection_count: number
  observed_building_count: number
}

export interface Dec7gBusiness {
  qualification_id: string
  provider_key: string
  provider_name: string | null
  registration_number: string | null
  city: string | null
  state: string | null
  registration_expiration_date: string | null
  relationship_evidence: 'QUALIFIED_PROVIDER'
  qualification_scope: string
}

export interface DomesticWaterMarketPayload {
  schema_version: string
  generated_at: string
  domain: 'NY_DOMESTIC_WATER_PROVIDER_INTELLIGENCE'
  evidence_semantics: Record<string, string>
  summary: {
    tank_inspection_count: number
    tank_compliance_activity_count: number
    observed_provider_count: number
    observed_laboratory_count: number
    observed_property_count: number
    dec_7g_business_registration_count: number
    dec_7g_applicator_certification_count: number
    violation_activity_count: number
    inspection_rows_with_provider: number
    inspection_rows_with_lab: number
  }
  providers: DomesticWaterMarketProvider[]
  laboratories: DomesticWaterMarketLaboratory[]
  dec_7g_businesses: Dec7gBusiness[]
}

export interface ProviderResolutionPayload {
  schema_version: string
  generated_at: string
  domain: 'PROVIDER_IDENTITY_REVIEW'
  summary: {
    provider_count: number
    alias_review_candidate_count: number
    high_priority_alias_candidate_count: number
    dec_name_match_count: number
    providers_with_dec_name_match: number
    merge_applied_count: 0
  }
  alias_review_candidates: Array<{
    candidate_id: string
    left_provider_key: string
    right_provider_key: string
    candidate_type: string
    review_priority: string
    reason: string
    identity_confidence: 'VERIFY'
    merge_applied: false
  }>
  dec_name_matches: Array<{
    match_id: string
    provider_id: string
    provider_key: string
    dec_provider_name: string | null
    dec_registration_number: string | null
    match_method: string
    identity_confidence: 'VERIFY'
    relationship_evidence: 'CROSS_SOURCE_NAME_MATCH_ONLY'
    qualification_scope: string | null
  }>
}

export interface NysPublicWaterProfile {
  pws_id: string
  pws_name: string | null
  system_type?: string | null
  lead_service_line_inventory_principal_county?: string | null
  system_types?: string[]
  observed_system_type_variants?: Array<{ value: string; count: number }>
  contact_count: number
  contacts?: Array<Record<string, unknown>>
  total_population: number | null
  lead_service_line_inventory_required?: boolean
  lead_service_line_inventory_detail_url?: string | null
  violation_count_2025?: number
  violation_status_counts_2025?: Record<string, number>
  violation_type_counts_2025?: Record<string, number>
}

export interface NysPublicWaterPayload {
  schema_version: string
  generated_at: string
  domain: 'NYS_PUBLIC_WATER_SYSTEMS'
  summary: Record<string, number>
  evidence_semantics: Record<string, string>
  source_health: Array<Record<string, unknown>>
  pws_systems: NysPublicWaterProfile[]
  pws_contacts: Array<Record<string, unknown>>
  certified_operators: Array<Record<string, unknown>>
  lsli_index: Array<Record<string, unknown>>
  violations_2025: Array<Record<string, unknown>>
}

export interface LsliDetailRecord {
  pws_id: string
  pws_name: string | null
  source_url: string
  owner_or_operator_form_contact?: {
    name: string | null
    phone: string | null
    email: string | null
    relationship_role: string | null
  }
  inventory?: {
    total_service_lines: number | null
    identified_service_lines: number | null
    lead_service_lines: number | null
    gslrr_service_lines: number | null
    non_lead_service_lines: number | null
    unknown_service_lines: number | null
  }
  source_reported_inventory?: Record<string, number | null>
  inventory_evidence?: Record<string, string>
  inventory_reconciliation?: {
    identified_matches_components: boolean
    identified_expected_from_components: number
    identified_component_delta: number
    total_matches_identified_plus_unknown: boolean
    total_expected_from_identified_plus_unknown: number
    total_identified_unknown_delta: number
  }
  identification_methods?: Array<Record<string, unknown>>
  inventory_availability?: Record<string, unknown>
  public_availability?: Record<string, unknown>
  detail_status?: string
}

export interface NysLsliDetailPayload {
  schema_version: string
  generated_at: string
  domain: 'NYS_LEAD_SERVICE_LINE_INVENTORY_DETAILS'
  source: Record<string, unknown>
  evidence_semantics: Record<string, string>
  summary: Record<string, number>
  details: LsliDetailRecord[]
  unavailable_details: Array<Record<string, unknown>>
}

export interface NysServiceLineInventorySummaryPayload {
  schema_version: string
  generated_at: string
  domain: 'NYS_ADDRESS_LEVEL_SERVICE_LINE_INVENTORY'
  source: Record<string, unknown>
  summary: {
    row_count: number
    raw_locality_counts: Record<string, number>
    normalized_category_counts: Record<string, number>
    normalized_public_material_counts: Record<string, number>
    normalized_customer_material_counts: Record<string, number>
    normalized_public_method_counts?: Record<string, number>
    normalized_customer_method_counts?: Record<string, number>
    nyc_borough_row_counts: Record<string, number>
    building_type_counts?: Record<string, number>
    pou_poe_raw_counts?: Record<string, number>
    pou_poe_yes_count?: number
    missing_service_address_id_count?: number
    rows_with_valid_nys_location: number
    rows_with_note: number
  }
  identity_semantics: Record<string, string>
  normalization_semantics: Record<string, string>
  data_file: string
}

export interface NycDistributionWaterPayload {
  schema_version: string
  generated_at: string
  domain: 'NYC_DISTRIBUTION_DRINKING_WATER_QUALITY'
  summary: {
    sample_count: number
    sample_site_count: number
    sample_class_counts: Record<string, number>
  } & Record<string, unknown>
  evidence_semantics: Record<string, string>
  sites: Array<{
    sample_site: string | null
    sample_count: number
    sample_class_counts: Record<string, number>
    first_sample_date: string | null
    latest_sample_date: string | null
    latest_measurements: Record<string, { raw: string | null; numeric: number | null; qualifier: string }> | null
    property_link_confidence: 'UNLINKED_SAMPLE_SITE'
  }>
  samples: Array<Record<string, unknown>>
}

export interface NycWaterSignalsPayload {
  schema_version: string
  generated_at: string
  domain: 'NYC_BUILDING_WATER_SIGNALS'
  summary: Record<string, number>
}

export interface ElapProbePayload {
  search_url: string
  lab_selector: {
    option_count: number
    populated_option_count: number
    exact_name_value_option_count: number
  }
  detail_resolution_probe: {
    detail_resolution_status: string
    test_lab_name: string
  }
}

export interface ProviderCompanyObservation {
  id: string
  label: string
  type: 'DWT_PROVIDER' | 'DWT_LAB' | 'DEC_7G'
  observedBuildings: number | null
  observationCount: number | null
  confidence: ProcurementConfidence | 'VERIFY'
  evidence: string
}
