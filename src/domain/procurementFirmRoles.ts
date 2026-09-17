import type { ProcurementRecord } from '../types/procurement'

export type ProcurementFirmRoleEvidence = {
  key: string
  name: string
  role: 'Awarded / contracted vendor' | 'Procurement vendor'
  relationship: 'CONTRACT_AWARD_EVIDENCE'
  factClass: 'CONFIRMED_FACT'
  confidence: 'CONFIRMED' | 'STRONG_SIGNAL'
  sourceName: string
  datasetId: string
  matchBasis: 'SYSTEM_ID_EXPLICIT'
  observedDate: string | null
  observedYear: null
  sourceReference: string
  serviceAssignmentBoundary: string
  sourceUrls: string[]
  companyIdentity: string | null
}

function text(value: unknown): string | null {
  if (typeof value !== 'string') return value == null ? null : String(value)
  const normalized = value.trim().replace(/\s+/g, ' ')
  return normalized || null
}

function urls(record: ProcurementRecord): string[] {
  const candidates = record.source_urls?.length ? record.source_urls : record.source_url ? [record.source_url] : []
  return [...new Set(candidates.filter(value => typeof value === 'string' && /^https:\/\//i.test(value)))]
}

export function collectProcurementFirmRoleEvidence(records: ProcurementRecord[]): ProcurementFirmRoleEvidence[] {
  const rows: ProcurementFirmRoleEvidence[] = []
  for (const record of records) {
    const name = text(record.vendor_raw)
    if (!name) continue
    if (record.tower_link_confidence !== 'CONFIRMED' && record.tower_link_confidence !== 'STRONG') continue
    const date = record.award_date ?? record.start_date ?? record.due_date ?? record.notice_start_date ?? null
    const awarded = record.status === 'AWARDED' || Boolean(record.award_date) || Boolean(record.source_contract_id)
    rows.push({
      key: `procurement::${record.procurement_id || `${record.source}:${record.source_record_id}`}`,
      name,
      role: awarded ? 'Awarded / contracted vendor' : 'Procurement vendor',
      relationship: 'CONTRACT_AWARD_EVIDENCE',
      factClass: 'CONFIRMED_FACT',
      confidence: record.tower_link_confidence === 'CONFIRMED' ? 'CONFIRMED' : 'STRONG_SIGNAL',
      sourceName: record.source,
      datasetId: record.source_dataset_id ?? record.source,
      matchBasis: 'SYSTEM_ID_EXPLICIT',
      observedDate: date,
      observedYear: null,
      sourceReference: `${record.procurement_id || record.source_record_id} · explicit tower_account_system_ids link${record.company_id ? ` · company ${record.company_id}` : ''}`,
      serviceAssignmentBoundary: 'Public procurement/vendor evidence explicitly linked to this TowerSignal account. Vendor identity is retained from the source/resolution record; no relationship is created from name or mailing-address similarity, and the record does not prove current incumbency outside its published contract/award scope.',
      sourceUrls: urls(record),
      companyIdentity: record.company_id ?? null,
    })
  }
  return rows.sort((left, right) => (right.observedDate ?? '').localeCompare(left.observedDate ?? '') || left.name.localeCompare(right.name) || left.key.localeCompare(right.key))
}
