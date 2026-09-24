export type ServiceClientStatus = 'active' | 'inactive' | 'prospect'
export type ServiceSiteStatus = 'active' | 'inactive' | 'prospect'
export type ServiceAgreementStatus = 'draft' | 'active' | 'expired' | 'cancelled'
export type ServiceVisitStatus = 'scheduled' | 'in-progress' | 'completed' | 'cancelled'
export type ServiceReportStatus = 'draft' | 'ready' | 'finalized'
export type ServiceActionStatus = 'open' | 'in-progress' | 'completed' | 'dismissed'
export type ServiceActionSeverity = 'low' | 'medium' | 'high' | 'critical'
export type ServiceMeasurementStatus = 'normal' | 'attention' | 'action'
export type ServiceDocumentType =
  | 'visit-report' | 'photo' | 'lab-result' | 'water-management-plan'
  | 'contract' | 'schematic' | 'sds' | 'invoice' | 'other'
export type ServiceExtractionStatus = 'not-requested' | 'pending' | 'complete' | 'failed'

export interface ServiceClient {
  client_id: string
  name: string
  linked_company_id: string | null
  billing_name: string | null
  status: ServiceClientStatus
  account_owner: string | null
  notes: string | null
  created_at: string
  updated_at: string
}

export interface ServicePortfolio {
  portfolio_id: string
  client_id: string
  name: string
  description: string | null
  status: 'active' | 'inactive'
  created_at: string
  updated_at: string
}

export interface ServiceSite {
  service_site_id: string
  system_id: string
  client_id: string | null
  portfolio_id: string | null
  display_name: string | null
  address: string | null
  status: ServiceSiteStatus
  access_notes: string | null
  service_notes: string | null
  created_at: string
  updated_at: string
}

export interface ServiceAsset {
  asset_id: string
  service_site_id: string
  asset_type: 'cooling_tower' | 'controller' | 'pump' | 'chemical_feed' | 'heat_exchanger' | 'domestic_water_tank' | 'sensor' | 'other'
  asset_label: string
  manufacturer: string | null
  model: string | null
  serial_number: string | null
  public_equipment_id: string | null
  location: string | null
  active: boolean
  notes: string | null
  created_at: string
  updated_at: string
}

export interface ServiceAgreement {
  agreement_id: string
  service_site_id: string
  provider_company_id: string | null
  agreement_name: string
  status: ServiceAgreementStatus
  start_date: string | null
  end_date: string | null
  service_interval_days: number | null
  scope: Record<string, unknown>
  notes: string | null
  created_at: string
  updated_at: string
}

export interface ServiceVisit {
  visit_id: string
  service_site_id: string
  agreement_id: string | null
  status: ServiceVisitStatus
  visit_type: string
  scheduled_for: string | null
  started_at: string | null
  completed_at: string | null
  technician_name: string | null
  summary: string | null
  next_visit_date: string | null
  report_status: ServiceReportStatus
  created_at: string
  updated_at: string
}

export interface ServiceMeasurement {
  measurement_id: string
  service_site_id: string
  visit_id: string
  asset_id: string | null
  parameter: string
  value_numeric: number | null
  value_text: string | null
  unit: string | null
  target_min: number | null
  target_max: number | null
  result_status: ServiceMeasurementStatus
  notes: string | null
  measured_at: string
  created_at: string
}

export interface ServiceAction {
  action_id: string
  service_site_id: string
  visit_id: string | null
  asset_id: string | null
  title: string
  severity: ServiceActionSeverity
  status: ServiceActionStatus
  due_date: string | null
  completed_at: string | null
  owner: string | null
  details: string | null
  created_at: string
  updated_at: string
}

export interface ServiceReport {
  report_id: string
  service_site_id: string
  visit_id: string
  report_number: string | null
  title: string
  status: ServiceReportStatus
  executive_summary: string | null
  recommendations: string | null
  generated_at: string | null
  finalized_at: string | null
  client_visible: boolean
  created_at: string
  updated_at: string
}

export interface ServiceDocument {
  document_id: string
  service_site_id: string
  visit_id: string | null
  report_id: string | null
  asset_id: string | null
  document_type: ServiceDocumentType
  file_name: string
  mime_type: string | null
  storage_url: string | null
  sha256: string | null
  captured_at: string | null
  notes: string | null
  extraction_status: ServiceExtractionStatus
  extracted_text: string | null
  created_at: string
  updated_at: string
}

export interface ServiceWorkspace {
  site: ServiceSite | null
  clients: ServiceClient[]
  portfolios: ServicePortfolio[]
  assets: ServiceAsset[]
  agreements: ServiceAgreement[]
  visits: ServiceVisit[]
  measurements: ServiceMeasurement[]
  actions: ServiceAction[]
  reports: ServiceReport[]
  documents: ServiceDocument[]
}


export interface ServiceOperationsOverview {
  clients: ServiceClient[]
  portfolios: ServicePortfolio[]
  sites: ServiceSite[]
  assets: ServiceAsset[]
  agreements: ServiceAgreement[]
  visits: ServiceVisit[]
  measurements: ServiceMeasurement[]
  actions: ServiceAction[]
  reports: ServiceReport[]
  documents: ServiceDocument[]
}
