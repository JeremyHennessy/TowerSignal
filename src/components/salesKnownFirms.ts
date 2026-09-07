import type { SystemDetailWithDomesticWater } from './DomesticWaterSection'

export type SalesKnownFirm = {
  key: string
  name: string
  roles: string[]
  latestObservedDate: string | null
  latestObservedYear: string | null
  evidence: string[]
  relationship: 'OBSERVED_SERVICE' | 'RECORDED_ROLE'
}

type FirmObservation = {
  name: string
  role: string
  date?: string | null
  year?: string | null
  evidence: string
  relationship: SalesKnownFirm['relationship']
}

type DomesticFirmRecord = {
  inspection_by_firm?: string | null
  lab_name?: string | null
  inspection_date?: string | null
  reporting_year?: string | null
}

type FirmAccumulator = {
  key: string
  name: string
  roles: Set<string>
  latestObservedDate: string | null
  latestObservedYear: string | null
  latestSortKey: string
  evidence: Set<string>
  relationship: SalesKnownFirm['relationship']
}

function cleanText(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const text = value.trim().replace(/\s+/g, ' ')
  return text || null
}

function firmKey(value: string): string {
  return value.toUpperCase()
}

function looksLikeFirm(value: string | null): value is string {
  if (!value) return false
  const normalized = value.trim().toUpperCase()
  if (['N/A', 'NA', 'NONE', 'UNKNOWN', 'NOT PROVIDED', 'NOT PUBLISHED'].includes(normalized)) return false
  return /[A-Z].*[A-Z]/i.test(value)
}

function sourceDate(row: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = cleanText(row[key])
    if (value) return value
  }
  return null
}

function sourceText(row: Record<string, unknown>, key: string): string | null {
  return cleanText(row[key])
}

function humanize(value: string | null): string | null {
  if (!value) return null
  return value.replaceAll('_', ' ').toLowerCase().replace(/^./, letter => letter.toUpperCase())
}

function observationSortKey(observation: FirmObservation): string {
  if (observation.date) return observation.date
  if (observation.year) return `${observation.year}-00-00`
  return ''
}

function addObservation(map: Map<string, FirmAccumulator>, observation: FirmObservation) {
  const name = cleanText(observation.name)
  if (!looksLikeFirm(name)) return
  const key = firmKey(name)
  const nextSortKey = observationSortKey(observation)
  const existing = map.get(key)
  if (!existing) {
    map.set(key, {
      key,
      name,
      roles: new Set([observation.role]),
      latestObservedDate: observation.date ?? null,
      latestObservedYear: observation.year ?? null,
      latestSortKey: nextSortKey,
      evidence: new Set([observation.evidence]),
      relationship: observation.relationship,
    })
    return
  }

  existing.roles.add(observation.role)
  existing.evidence.add(observation.evidence)
  if (observation.relationship === 'OBSERVED_SERVICE') existing.relationship = 'OBSERVED_SERVICE'
  if (nextSortKey > existing.latestSortKey) {
    existing.name = name
    existing.latestObservedDate = observation.date ?? null
    existing.latestObservedYear = observation.year ?? null
    existing.latestSortKey = nextSortKey
  }
}

export function collectKnownAccountFirms(detail: SystemDetailWithDomesticWater): SalesKnownFirm[] {
  const firms = new Map<string, FirmAccumulator>()

  for (const raw of detail.domestic_water?.self_report_history ?? []) {
    const row = raw as DomesticFirmRecord
    const date = cleanText(row.inspection_date)
    const year = cleanText(row.reporting_year)
    const inspectionFirm = cleanText(row.inspection_by_firm)
    if (inspectionFirm) {
      addObservation(firms, {
        name: inspectionFirm,
        role: 'Drinking-water tank inspection firm',
        date,
        year,
        evidence: 'NYC DOHMH self-reported drinking-water tank inspection · exact BIN asset link.',
        relationship: 'OBSERVED_SERVICE',
      })
    }
    const lab = cleanText(row.lab_name)
    if (lab) {
      addObservation(firms, {
        name: lab,
        role: 'Drinking-water testing laboratory',
        date,
        year,
        evidence: 'NYC DOHMH self-reported drinking-water tank inspection names the laboratory · exact BIN asset link.',
        relationship: 'OBSERVED_SERVICE',
      })
    }
  }

  const waterSignals = detail.nyc_building_water_signals
  for (const row of [...(waterSignals?.dob_water_job_filings ?? []), ...(waterSignals?.dob_water_permits ?? [])]) {
    const name = sourceText(row, 'applicant_business_raw')
    if (!name) continue
    const category = humanize(sourceText(row, 'category'))
    const relationshipEvidence = humanize(sourceText(row, 'relationship_evidence'))
    const serviceAssignment = humanize(sourceText(row, 'service_assignment_confidence'))
    addObservation(firms, {
      name,
      role: category ? `DOB ${category} applicant business` : 'DOB water-work applicant business',
      date: sourceDate(row, 'issued_date', 'approved_date', 'filing_date'),
      evidence: `NYC DOB water-work record · exact BBL${relationshipEvidence ? ` · ${relationshipEvidence}` : ''}${serviceAssignment ? ` · ${serviceAssignment}` : ' · not proof of service assignment'}.`,
      relationship: 'RECORDED_ROLE',
    })
  }

  for (const job of detail.dob_activity_history ?? []) {
    const name = cleanText(job.applicant_business_name)
    if (!name || (!job.explicit_cooling_tower_mention && !job.mechanical_systems && !job.boiler_equipment)) continue
    const role = job.explicit_cooling_tower_mention
      ? 'Cooling-tower filing applicant business'
      : 'Mechanical / boiler filing applicant business'
    addObservation(firms, {
      name,
      role,
      date: job.activity_date ?? job.first_permit_date ?? job.approved_date ?? job.filing_date,
      evidence: 'NYC DOB NOW job filing · exact BBL · recorded applicant business · not proof of current service responsibility or contract.',
      relationship: 'RECORDED_ROLE',
    })
  }

  return [...firms.values()]
    .sort((left, right) => right.latestSortKey.localeCompare(left.latestSortKey) || left.name.localeCompare(right.name))
    .map(firm => ({
      key: firm.key,
      name: firm.name,
      roles: [...firm.roles].sort(),
      latestObservedDate: firm.latestObservedDate,
      latestObservedYear: firm.latestObservedYear,
      evidence: [...firm.evidence].sort(),
      relationship: firm.relationship,
    }))
}
