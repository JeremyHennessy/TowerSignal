export interface PropertyEnforcementSummaryFields {
  hpd_violation_count?: number
  hpd_open_violation_count?: number
  hpd_open_class_c_count?: number
  latest_hpd_violation_inspection_date?: string | null
  stop_work_order_event_count?: number
  latest_stop_work_order_event_date?: string | null
  facade_compliance_filing_count?: number
  facade_latest_status?: string | null
  facade_latest_cycle?: string | null
  facade_latest_submitted_on?: string | null
}

export interface HpdViolationRecord {
  violation_id: string
  building_id: string | null
  registration_id: string | null
  bbl: string
  bin: string | null
  borough: string | null
  block: string | null
  lot: string | null
  class: string | null
  inspection_date: string | null
  approved_date: string | null
  nov_issued_date: string | null
  description: string | null
  current_status_id: string | null
  current_status: string | null
  current_status_date: string | null
  violation_status: string | null
  is_open: boolean
  rent_impairing: boolean
  source: 'NYC_HPD_HOUSING_MAINTENANCE_CODE_VIOLATIONS'
  match_basis: 'BBL_EXACT'
}

export interface StopWorkOrderEvidenceRecord {
  complaint_number: string
  bin: string
  complaint_status: string | null
  date_entered: string | null
  inspection_date: string | null
  disposition_date: string | null
  disposition_code: string
  disposition_text: string
  event_type: string
  complaint_category: string | null
  unit: string | null
  address: string | null
  zip: string | null
  source_refresh_date: string | null
  source: 'NYC_DOB_COMPLAINTS_STOP_WORK_ORDER_DISPOSITIONS'
  match_basis: 'BIN_EXACT'
}

export interface FacadeComplianceRecord {
  control_no: string
  tr6_no: string | null
  bin: string
  filing_type: string | null
  cycle: string | null
  sequence_no: string | null
  submitted_on: string | null
  current_status: string | null
  qewi_name: string | null
  qewi_business_name: string | null
  address: string | null
  borough: string | null
  block: string | null
  lot: string | null
  source: 'NYC_DOB_NOW_SAFETY_FACADES_COMPLIANCE_FILINGS'
  match_basis: 'BIN_EXACT'
}

export interface PropertyEnforcementContext {
  hpd_violations: {
    summary: {
      record_count: number
      open_count: number
      open_class_a_count: number
      open_class_b_count: number
      open_class_c_count: number
      latest_inspection_date: string | null
    }
    hpd_violations: HpdViolationRecord[]
  } | null
  stop_work_orders: {
    summary: {
      record_count: number
      issue_event_count: number
      rescission_event_count: number
      latest_event_date: string | null
    }
    records: StopWorkOrderEvidenceRecord[]
  } | null
  facade_compliance: {
    summary: {
      record_count: number
      latest_status: string | null
      latest_cycle: string | null
      latest_submitted_on: string | null
      unsafe_count: number
      swarmp_count: number
      no_report_filed_count: number
    }
    records: FacadeComplianceRecord[]
  } | null
  evidence_boundaries: Record<string, string>
  generated_at: string
}

export interface LegionellaAlertItem {
  item_id: string
  url: string
  title: string | null
  agency: string
  channel_key: string
  channel_kind: string
  document_type: string
  published_date: string | null
  discovered_from: string | null
  content_sha256: string
  content_bytes: number
  retrieved_at: string
  source_timestamp?: string
  match_terms: {
    legionella: boolean
    cooling_tower: boolean
  }
}

export interface LegionellaAlertPayload {
  domain: 'LEGIONELLA_PUBLIC_HEALTH_ALERTS'
  generated_at: string
  source_channels: Array<Record<string, string>>
  source_snapshots: Array<Record<string, unknown>>
  items: LegionellaAlertItem[]
  errors: Array<Record<string, unknown>>
  summary: {
    source_channel_count: number
    discovered_relevant_item_count: number
    retrieval_error_count: number
    nyc_health_item_count: number
    nyc_emergency_management_item_count: number
    nyc_311_item_count: number
    nys_health_item_count: number
    mayor_office_item_count: number
  }
  history_merge: {
    previous_cache_available: boolean
    previous_cache_generated_at: string | null
    previous_item_count: number
    current_collection_item_count: number
    retained_prior_item_count: number
    refreshed_existing_item_count: number
    new_item_count: number
    merged_item_count: number
    identity_basis: 'item_id'
    retention_rule: string
  }
}
