import type { ProcurementBundle, ProcurementRecord } from '../types/procurement'
import type { SystemDetailWithDomesticWater } from '../components/DomesticWaterSection'
import { collectKnownAccountFirms, knownFirmKey } from '../components/salesKnownFirms'

export type AccountFirmRoleEvidence = {
  key: string
  firmKey: string
  name: string
  role: string
  relationship: 'OBSERVED_SERVICE' | 'RECORDED_ROLE'
  factClass: 'CONFIRMED_FACT'
  confidence: 'CONFIRMED'
  sourceName: string
  datasetId: string
  matchBasis: 'BIN_EXACT' | 'BBL_EXACT'
  observedDate: string | null
  observedYear: string | null
  sourceReference: string
  serviceAssignmentBoundary: string
}

function text(value: unknown): string | null {
  if (typeof value !== 'string') return value == null ? null : String(value)
  const normalized = value.trim().replace(/\s+/g, ' ')
  return normalized || null
}

function humanize(value: unknown): string | null {
  const normalized = text(value)
  if (!normalized) return null
  return normalized.replaceAll('_', ' ').toLowerCase().replace(/^./, letter => letter.toUpperCase())
}

function observationDate(row: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = text(row[key])
    if (value) return value
  }
  return null
}

export function explicitAccountProcurementRecords(bundle: ProcurementBundle, systemId: string): ProcurementRecord[] {
  const records: ProcurementRecord[] = [
    ...bundle.cityRecord.notices,
    ...bundle.checkbook.contracts,
    ...(bundle.nysAuthorities?.contracts ?? []),
    ...(bundle.openBookWater?.contracts ?? []),
    ...(bundle.nychaWater?.records ?? []),
  ]
  const byId = new Map<string, ProcurementRecord>()
  for (const record of records) {
    if (!record.tower_account_system_ids?.includes(systemId)) continue
    if (record.tower_link_confidence !== 'CONFIRMED' && record.tower_link_confidence !== 'STRONG') continue
    const key = record.procurement_id || `${record.source}:${record.source_record_id}`
    if (!byId.has(key)) byId.set(key, record)
  }
  return [...byId.values()].sort((left, right) => {
    const leftDate = left.due_date ?? left.award_date ?? left.start_date ?? left.notice_start_date ?? ''
    const rightDate = right.due_date ?? right.award_date ?? right.start_date ?? right.notice_start_date ?? ''
    return rightDate.localeCompare(leftDate) || left.procurement_id.localeCompare(right.procurement_id)
  })
}

// Sort source-native ISO and US dates by calendar value, while retaining the
// original date string on every evidence row. Unknown dates stay undated.
function observedSortKey(date: string | null, year: string | null): string {
  const iso = date && /^(\d{4})-(\d{2})-(\d{2})/.exec(date)
  const us = date && /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(date)
  const parts = iso ? [iso[1], iso[2], iso[3]] : us ? [us[3], us[1], us[2]] : null
  if (parts) {
    const [y, m, d] = parts.map(Number)
    const parsed = new Date(Date.UTC(y, m - 1, d))
    if (parsed.getUTCFullYear() === y && parsed.getUTCMonth() === m - 1 && parsed.getUTCDate() === d) {
      return `${parts[0]}-${parts[1].padStart(2, '0')}-${parts[2].padStart(2, '0')}`
    }
  }
  return year && /^\d{4}$/.test(year) ? `${year}-00-00` : ''
}

export function collectAccountFirmRoleEvidence(detail: SystemDetailWithDomesticWater): AccountFirmRoleEvidence[] {
  const canonical = new Map(collectKnownAccountFirms(detail).map(firm => [firm.key, firm.name]))
  const rows: AccountFirmRoleEvidence[] = []

  const add = (input: Omit<AccountFirmRoleEvidence, 'key' | 'firmKey' | 'name' | 'factClass' | 'confidence'> & { name: string }) => {
    const firmKey = knownFirmKey(input.name)
    const canonicalName = canonical.get(firmKey)
    if (!canonicalName) return
    const key = [firmKey, input.role, input.datasetId, input.sourceReference].join('::')
    if (rows.some(row => row.key === key)) return
    rows.push({ ...input, key, firmKey, name: canonicalName, factClass: 'CONFIRMED_FACT', confidence: 'CONFIRMED' })
  }

  for (const raw of detail.domestic_water?.self_report_history ?? []) {
    const row = raw as unknown as Record<string, unknown>
    const date = text(row.inspection_date)
    const year = text(row.reporting_year)
    const bin = text(row.bin) ?? text(detail.identity.bin) ?? 'BIN not published'
    const tank = text(row.tank_num) ?? 'tank number not published'
    const firm = text(row.inspection_by_firm)
    if (firm) add({
      name: firm,
      role: 'Drinking-water tank inspection firm',
      relationship: 'OBSERVED_SERVICE',
      sourceName: 'NYC DOHMH Self-Reported Drinking Water Tank Inspection Results',
      datasetId: 'gjm4-k24g',
      matchBasis: 'BIN_EXACT',
      observedDate: date,
      observedYear: year,
      sourceReference: `BIN ${bin} · ${tank}${date ? ` · inspection ${date}` : year ? ` · reporting year ${year}` : ''}`,
      serviceAssignmentBoundary: 'Source-observed drinking-water tank inspection service at this exact BIN; not proof of current cooling-tower incumbency or a current contract.',
    })
    const lab = text(row.lab_name)
    if (lab) add({
      name: lab,
      role: 'Drinking-water testing laboratory',
      relationship: 'OBSERVED_SERVICE',
      sourceName: 'NYC DOHMH Self-Reported Drinking Water Tank Inspection Results',
      datasetId: 'gjm4-k24g',
      matchBasis: 'BIN_EXACT',
      observedDate: date,
      observedYear: year,
      sourceReference: `BIN ${bin} · ${tank}${date ? ` · inspection ${date}` : year ? ` · reporting year ${year}` : ''}`,
      serviceAssignmentBoundary: 'Source-named laboratory on a drinking-water tank inspection at this exact BIN; not proof of current cooling-tower testing responsibility.',
    })
  }

  const waterSignals = detail.nyc_building_water_signals
  const addDobWaterRole = (raw: Record<string, unknown>, datasetId: string, sourceName: string) => {
    const name = text(raw.applicant_business_raw)
    if (!name) return
    const category = humanize(raw.category)
    const record = text(raw.source_record_id) ?? text(raw.job_filing_number) ?? text(raw.activity_id) ?? 'record id not published'
    add({
      name,
      role: category ? `DOB ${category} applicant business` : 'DOB water-work applicant business',
      relationship: 'RECORDED_ROLE',
      sourceName,
      datasetId,
      matchBasis: 'BBL_EXACT',
      observedDate: observationDate(raw, 'issued_date', 'approved_date', 'filing_date'),
      observedYear: null,
      sourceReference: `Record ${record} · exact BBL${humanize(raw.relationship_evidence) ? ` · ${humanize(raw.relationship_evidence)}` : ''}`,
      serviceAssignmentBoundary: `${humanize(raw.service_assignment_confidence) ?? 'Not proof of service assignment'}. Recorded DOB applicant role only; not a current service-provider or contract claim.`,
    })
  }
  for (const raw of waterSignals?.dob_water_job_filings ?? []) addDobWaterRole(raw, 'w9ak-ipjd', 'NYC DOB NOW Job Application Filings')
  for (const raw of waterSignals?.dob_water_permits ?? []) addDobWaterRole(raw, 'rbx6-tga4', 'NYC DOB NOW Approved Permits')

  for (const job of detail.dob_activity_history ?? []) {
    const name = text(job.applicant_business_name)
    if (!name || (!job.explicit_cooling_tower_mention && !job.mechanical_systems && !job.boiler_equipment)) continue
    const role = job.explicit_cooling_tower_mention ? 'Cooling-tower filing applicant business' : 'Mechanical / boiler filing applicant business'
    add({
      name,
      role,
      relationship: 'RECORDED_ROLE',
      sourceName: 'NYC DOB NOW Job Application Filings',
      datasetId: 'w9ak-ipjd',
      matchBasis: 'BBL_EXACT',
      observedDate: job.activity_date ?? job.first_permit_date ?? job.approved_date ?? job.filing_date,
      observedYear: null,
      sourceReference: `Job ${job.job_filing_number ?? 'number not published'} · exact BBL`,
      serviceAssignmentBoundary: 'Recorded applicant business on a DOB project filing; not proof of current service responsibility, incumbency or contract.',
    })
  }

  return rows.sort((left, right) => {
    const leftDate = observedSortKey(left.observedDate, left.observedYear)
    const rightDate = observedSortKey(right.observedDate, right.observedYear)
    return rightDate.localeCompare(leftDate) || left.name.localeCompare(right.name) || left.role.localeCompare(right.role)
  })
}
