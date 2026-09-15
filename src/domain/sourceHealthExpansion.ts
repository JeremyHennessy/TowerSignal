import type { SourceMetadata, SystemsPayload } from '../types/data'
import type { PropertyEnforcementSummaryFields } from '../types/enforcement'

export const enforcementSources = [
  { id: 'wvxf-dwi5', name: 'HPD Housing Maintenance Code violations', field: 'hpd_violation_count', identity: 'bbl', unit: 'BBLs', note: 'Exact canonical BBL. Open status is the published violationstatus, not a free-text inference.' },
  { id: 'eabe-havv', name: 'DOB stop-work-order disposition evidence', field: 'stop_work_order_event_count', identity: 'bin', unit: 'BINs', note: 'Exact BIN, restricted to documented SWO-related complaint disposition codes. Not a complete or current active-SWO ledger.' },
  { id: 'xubg-57si', name: 'DOB NOW facades / FISP / Local Law 11', field: 'facade_compliance_filing_count', identity: 'bin', unit: 'BINs', note: 'Exact BIN. Published facade filing statuses are retained. This is Local Law 11 / FISP, not a generic Labor Law filing feed.' },
] as const

export const requiredLegionellaChannels = [
  ['NYC_DOH_LEGIONNAIRES_TOPIC', 'NYC Health: Legionnaires topic'],
  ['NYC_DOH_PROVIDER_LEGIONELLOSIS', 'NYC Health: provider guidance'],
  ['NYC_DOH_HEALTH_ALERT_NETWORK', 'NYC Health Alert Network'],
  ['NYC_DOH_PRESS_RELEASES', 'NYC Health: press releases'],
  ['NYC_DOH_COOLING_TOWER_REQUIREMENTS', 'NYC Health: cooling-tower requirements'],
  ['NYC_MAYOR_NEWS', 'NYC Mayor: news'],
  ['NYC_NOTIFY_NYC', 'Notify NYC'],
  ['NYC_311_LEGIONNAIRES', 'NYC311: Legionnaires information'],
  ['NYC_311_COOLING_TOWER', 'NYC311: cooling-tower information'],
  ['NYSDOH_LEGIONNAIRES_TOPIC', 'NYSDOH: Legionnaires topic'],
  ['NYSDOH_LEGIONELLA_REGULATION', 'NYSDOH: cooling-tower requirements'],
  ['NYSDOH_PROTECTION_AGAINST_LEGIONELLA', 'NYSDOH: Legionella regulatory hub'],
] as const

export function countOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : null
}

export function safeSourceUrl(value: unknown): string | null {
  if (typeof value !== 'string') return null
  try {
    const url = new URL(value)
    return url.protocol === 'https:' ? url.href : null
  } catch { return null }
}

export function timestampOrNull(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 && Number.isFinite(Date.parse(value)) ? value : null
}

export function enforcementCoverage(payload: SystemsPayload) {
  const systems = payload.systems as Array<SystemsPayload['systems'][number] & PropertyEnforcementSummaryFields>
  return enforcementSources.map(definition => {
    const source: SourceMetadata | undefined = payload.metadata.sources?.find(item => item.dataset_id === definition.id)
    const validIdentity = (value: string | null) => typeof value === 'string' && (definition.identity === 'bbl' ? /^\d{10}$/.test(value) : /^\d{7}$/.test(value))
    const requested = new Set(systems.map(row => row[definition.identity]).filter(validIdentity)).size
    const measurementsPresent = Boolean(source) && systems.length > 0 && systems.every(row => countOrNull(row[definition.field]) !== null)
    const attachedRows = systems.filter(row => (row[definition.field] ?? 0) > 0)
    const identitiesValid = attachedRows.every(row => validIdentity(row[definition.identity]))
    const measured = measurementsPresent && identitiesValid
    const attached = measured ? attachedRows.length : null
    const matched = measured ? new Set(attachedRows.map(row => row[definition.identity])).size : null
    const records = countOrNull(source?.matched_record_count)
    const retrievedAt = timestampOrNull(source?.retrieved_at)
    return {
      ...definition, source, requested, attached, matched, records, retrievedAt,
      sourceRecords: countOrNull(source?.source_record_count),
      totalSystems: systems.length,
      coverage: attached !== null && systems.length > 0 ? 100 * attached / systems.length : null,
      available: Boolean(source && retrievedAt && records !== null && measured),
    }
  })
}

export interface LegionellaChannelSnapshot {
  channel_key: string
  agency?: string
  title?: string | null
  channel_kind?: string
  url?: string
  retrieved_at?: string
  content_sha256?: string
}

export interface LegionellaHealthPayload {
  generated_at: string
  source_channels: LegionellaChannelSnapshot[]
  items: Array<{ item_id: string; retrieved_at?: string }>
  errors: Array<{ url?: string; error?: string }>
  history_merge?: {
    retained_prior_item_count?: number
    current_collection_item_count?: number
    merged_item_count?: number
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export function parseLegionellaHealth(value: unknown): LegionellaHealthPayload {
  if (!isRecord(value) || value.domain !== 'LEGIONELLA_PUBLIC_HEALTH_ALERTS'
    || !timestampOrNull(value.generated_at) || !Array.isArray(value.source_channels)
    || !Array.isArray(value.items) || !Array.isArray(value.errors)
    || !value.source_channels.every(row => isRecord(row) && typeof row.channel_key === 'string')
    || !value.items.every(row => isRecord(row) && typeof row.item_id === 'string')
    || !value.errors.every(isRecord)) {
    throw new Error('Legionnaires source-health payload is malformed; no healthy or empty state is inferred.')
  }
  const channels = value.source_channels as LegionellaChannelSnapshot[]
  const items = value.items as LegionellaHealthPayload['items']
  if (new Set(channels.map(row => row.channel_key)).size !== channels.length
    || new Set(items.map(row => row.item_id)).size !== items.length) {
    throw new Error('Legionnaires source-health identities are duplicated.')
  }
  if (isRecord(value.summary) && (
    value.summary.source_channel_count !== channels.length
    || value.summary.discovered_relevant_item_count !== items.length
    || value.summary.retrieval_error_count !== value.errors.length)) {
    throw new Error('Legionnaires source-health counts disagree with the published records.')
  }
  return value as unknown as LegionellaHealthPayload
}

export function legionellaChannelRows(payload: LegionellaHealthPayload) {
  const expected = new Map<string, string>(requiredLegionellaChannels)
  for (const snapshot of payload.source_channels) {
    if (!expected.has(snapshot.channel_key)) expected.set(snapshot.channel_key, snapshot.title || snapshot.channel_key)
  }
  return [...expected].map(([key, name]) => {
    const snapshot = payload.source_channels.find(row => row.channel_key === key)
    const retrievedAt = timestampOrNull(snapshot?.retrieved_at)
    const retrieved = Boolean(snapshot && retrievedAt && /^[a-f0-9]{64}$/i.test(snapshot.content_sha256 ?? '') && safeSourceUrl(snapshot.url))
    return { key, name, snapshot, retrievedAt, retrieved }
  })
}
