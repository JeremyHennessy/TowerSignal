import { createClient } from '@neondatabase/neon-js'
import type {
  ServiceAction,
  ServiceActionSeverity,
  ServiceAgreement,
  ServiceAsset,
  ServiceClient,
  ServiceDocument,
  ServiceDocumentType,
  ServiceMeasurement,
  ServiceMeasurementStatus,
  ServicePortfolio,
  ServiceReport,
  ServiceSite,
  ServiceVisit,
  ServiceWorkspace,
} from '../types/serviceReporting'

const DEFAULT_AUTH_URL = 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech/neondb/auth'
const DEFAULT_DATA_API_URL = 'https://ep-silent-moon-au2icaki.apirest.c-10.us-east-1.aws.neon.tech/neondb/rest/v1'

const client = createClient({
  auth: { url: import.meta.env.VITE_NEON_AUTH_URL || DEFAULT_AUTH_URL },
  dataApi: { url: import.meta.env.VITE_NEON_DATA_API_URL || DEFAULT_DATA_API_URL },
})

function message(error: unknown): string {
  if (error && typeof error === 'object' && 'message' in error) return String((error as { message?: unknown }).message ?? 'Unknown service-reporting error')
  return String(error || 'Unknown service-reporting error')
}

function throwIfError(context: string, error: unknown): void {
  if (error) throw new Error(`${context}: ${message(error)}`)
}

function rows<T>(data: unknown): T[] {
  return (data ?? []) as T[]
}

export async function loadServiceReportingAccess(): Promise<boolean> {
  const result = await client.from('company_admin_access').select('is_admin').limit(1)
  throwIfError('Unable to verify service-reporting access', result.error)
  const row = rows<{ is_admin?: boolean }>(result.data)[0]
  return row?.is_admin === true
}

export async function loadServiceWorkspace(systemId: string): Promise<ServiceWorkspace> {
  const [siteResult, clientsResult, portfoliosResult] = await Promise.all([
    client.from('service_sites').select('*').eq('system_id', systemId).limit(1),
    client.from('service_clients').select('*').order('name', { ascending: true }),
    client.from('service_portfolios').select('*').order('name', { ascending: true }),
  ])
  throwIfError('Unable to load service site', siteResult.error)
  throwIfError('Unable to load service clients', clientsResult.error)
  throwIfError('Unable to load service portfolios', portfoliosResult.error)

  const site = rows<ServiceSite>(siteResult.data)[0] ?? null
  const base = {
    site,
    clients: rows<ServiceClient>(clientsResult.data),
    portfolios: rows<ServicePortfolio>(portfoliosResult.data),
  }
  if (!site) return { ...base, assets:[], agreements:[], visits:[], measurements:[], actions:[], reports:[], documents:[] }

  const [assets, agreements, visits, measurements, actions, reports, documents] = await Promise.all([
    client.from('service_assets').select('*').eq('service_site_id', site.service_site_id).order('asset_label', { ascending:true }),
    client.from('service_agreements').select('*').eq('service_site_id', site.service_site_id).order('updated_at', { ascending:false }),
    client.from('service_visits').select('*').eq('service_site_id', site.service_site_id).order('scheduled_for', { ascending:false }),
    client.from('service_measurements').select('*').eq('service_site_id', site.service_site_id).order('measured_at', { ascending:false }),
    client.from('service_actions').select('*').eq('service_site_id', site.service_site_id).order('created_at', { ascending:false }),
    client.from('service_reports').select('*').eq('service_site_id', site.service_site_id).order('created_at', { ascending:false }),
    client.from('service_documents').select('*').eq('service_site_id', site.service_site_id).order('created_at', { ascending:false }),
  ])
  for (const [label, result] of [
    ['assets',assets],['agreements',agreements],['visits',visits],['measurements',measurements],
    ['actions',actions],['reports',reports],['documents',documents],
  ] as const) throwIfError(`Unable to load service ${label}`, result.error)

  return {
    ...base,
    assets:rows<ServiceAsset>(assets.data),
    agreements:rows<ServiceAgreement>(agreements.data),
    visits:rows<ServiceVisit>(visits.data),
    measurements:rows<ServiceMeasurement>(measurements.data),
    actions:rows<ServiceAction>(actions.data),
    reports:rows<ServiceReport>(reports.data),
    documents:rows<ServiceDocument>(documents.data),
  }
}

export async function ensureServiceSite(systemId: string, address?: string | null): Promise<ServiceSite> {
  const existing = await client.from('service_sites').select('*').eq('system_id', systemId).limit(1)
  throwIfError('Unable to check service site', existing.error)
  const found = rows<ServiceSite>(existing.data)[0]
  if (found) return found
  const result = await client.from('service_sites').insert({
    service_site_id: crypto.randomUUID(),
    system_id: systemId,
    display_name: address || systemId,
    address: address || null,
    status: 'active',
  }).select('*')
  throwIfError('Unable to enable service tracking', result.error)
  const created = rows<ServiceSite>(result.data)[0]
  if (!created) throw new Error('Unable to enable service tracking: row was not returned')
  return created
}

export async function createServiceClient(name: string): Promise<ServiceClient> {
  const result = await client.from('service_clients').insert({
    client_id: crypto.randomUUID(),
    name,
    status:'active',
  }).select('*')
  throwIfError('Unable to create service client', result.error)
  const created = rows<ServiceClient>(result.data)[0]
  if (!created) throw new Error('Unable to create service client: row was not returned')
  return created
}

export async function createServicePortfolio(clientId: string, name: string): Promise<ServicePortfolio> {
  const result = await client.from('service_portfolios').insert({
    portfolio_id: crypto.randomUUID(),
    client_id: clientId,
    name,
    status:'active',
  }).select('*')
  throwIfError('Unable to create service portfolio', result.error)
  const created = rows<ServicePortfolio>(result.data)[0]
  if (!created) throw new Error('Unable to create service portfolio: row was not returned')
  return created
}

export async function updateServiceSiteOrganization(
  serviceSiteId: string,
  clientId: string | null,
  portfolioId: string | null,
): Promise<ServiceSite> {
  const result = await client.from('service_sites')
    .update({ client_id:clientId, portfolio_id:portfolioId, updated_at:new Date().toISOString() })
    .eq('service_site_id', serviceSiteId).select('*')
  throwIfError('Unable to update service-site organization', result.error)
  const updated = rows<ServiceSite>(result.data)[0]
  if (!updated) throw new Error('Unable to update service-site organization: row was not returned')
  return updated
}

export async function addServiceAsset(
  serviceSiteId: string,
  assetType: ServiceAsset['asset_type'],
  assetLabel: string,
): Promise<ServiceAsset> {
  const result = await client.from('service_assets').insert({
    asset_id:crypto.randomUUID(), service_site_id:serviceSiteId, asset_type:assetType, asset_label:assetLabel, active:true,
  }).select('*')
  throwIfError('Unable to add service asset', result.error)
  const created = rows<ServiceAsset>(result.data)[0]
  if (!created) throw new Error('Unable to add service asset: row was not returned')
  return created
}

export async function addServiceAgreement(
  serviceSiteId: string,
  agreementName: string,
  intervalDays: number | null,
): Promise<ServiceAgreement> {
  const result = await client.from('service_agreements').insert({
    agreement_id:crypto.randomUUID(), service_site_id:serviceSiteId,
    agreement_name:agreementName, status:'draft', service_interval_days:intervalDays,
  }).select('*')
  throwIfError('Unable to add service agreement', result.error)
  const created = rows<ServiceAgreement>(result.data)[0]
  if (!created) throw new Error('Unable to add service agreement: row was not returned')
  return created
}

export async function addServiceVisit(
  serviceSiteId: string,
  scheduledFor: string,
  technicianName: string | null,
  visitType = 'routine',
): Promise<ServiceVisit> {
  const result = await client.from('service_visits').insert({
    visit_id:crypto.randomUUID(), service_site_id:serviceSiteId, status:'scheduled',
    visit_type:visitType, scheduled_for:scheduledFor, technician_name:technicianName,
  }).select('*')
  throwIfError('Unable to schedule service visit', result.error)
  const created = rows<ServiceVisit>(result.data)[0]
  if (!created) throw new Error('Unable to schedule service visit: row was not returned')
  return created
}

export async function updateServiceVisit(
  visitId: string,
  patch: Partial<Pick<ServiceVisit,'status'|'started_at'|'completed_at'|'technician_name'|'summary'|'next_visit_date'|'report_status'>>,
): Promise<ServiceVisit> {
  const result = await client.from('service_visits').update({ ...patch, updated_at:new Date().toISOString() }).eq('visit_id', visitId).select('*')
  throwIfError('Unable to update service visit', result.error)
  const updated = rows<ServiceVisit>(result.data)[0]
  if (!updated) throw new Error('Unable to update service visit: row was not returned')
  return updated
}

export async function addServiceMeasurement(
  serviceSiteId: string,
  visitId: string,
  parameter: string,
  value: string,
  unit: string | null,
  resultStatus: ServiceMeasurementStatus,
): Promise<ServiceMeasurement> {
  const numeric = Number(value)
  const isNumeric = value.trim() !== '' && Number.isFinite(numeric)
  const result = await client.from('service_measurements').insert({
    measurement_id:crypto.randomUUID(), service_site_id:serviceSiteId, visit_id:visitId,
    parameter, value_numeric:isNumeric ? numeric : null, value_text:isNumeric ? null : value,
    unit, result_status:resultStatus,
  }).select('*')
  throwIfError('Unable to add service measurement', result.error)
  const created = rows<ServiceMeasurement>(result.data)[0]
  if (!created) throw new Error('Unable to add service measurement: row was not returned')
  return created
}

export async function addServiceAction(
  serviceSiteId: string,
  visitId: string | null,
  title: string,
  severity: ServiceActionSeverity,
  dueDate: string | null,
): Promise<ServiceAction> {
  const result = await client.from('service_actions').insert({
    action_id:crypto.randomUUID(), service_site_id:serviceSiteId, visit_id:visitId,
    title, severity, status:'open', due_date:dueDate,
  }).select('*')
  throwIfError('Unable to add corrective action', result.error)
  const created = rows<ServiceAction>(result.data)[0]
  if (!created) throw new Error('Unable to add corrective action: row was not returned')
  return created
}

export async function addServiceDocument(
  serviceSiteId: string,
  visitId: string | null,
  fileName: string,
  documentType: ServiceDocumentType,
  storageUrl: string | null,
): Promise<ServiceDocument> {
  const result = await client.from('service_documents').insert({
    document_id:crypto.randomUUID(), service_site_id:serviceSiteId, visit_id:visitId,
    document_type:documentType, file_name:fileName, storage_url:storageUrl,
    extraction_status:'not-requested',
  }).select('*')
  throwIfError('Unable to register service document', result.error)
  const created = rows<ServiceDocument>(result.data)[0]
  if (!created) throw new Error('Unable to register service document: row was not returned')
  return created
}

export async function ensureServiceReport(serviceSiteId: string, visitId: string, title: string): Promise<ServiceReport> {
  const existing = await client.from('service_reports').select('*').eq('visit_id', visitId).limit(1)
  throwIfError('Unable to check service report', existing.error)
  const found = rows<ServiceReport>(existing.data)[0]
  if (found) return found
  const result = await client.from('service_reports').insert({
    report_id:crypto.randomUUID(), service_site_id:serviceSiteId, visit_id:visitId, title, status:'draft',
  }).select('*')
  throwIfError('Unable to create service report', result.error)
  const created = rows<ServiceReport>(result.data)[0]
  if (!created) throw new Error('Unable to create service report: row was not returned')
  return created
}
