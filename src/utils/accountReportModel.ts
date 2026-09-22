import type { Metadata, SystemDetail, SystemSummary, Violation, PlanimetricGeometry } from '../types/data'

// Presentation only. Never recalculate the priority model or interpret missing records as zero.
export const reportDate = (value: string | null | undefined, month: 'short' | 'long' = 'short') => {
  if (!value || !/^\d{4}-\d{2}-\d{2}/.test(value)) return 'Not shown'
  const date = new Date(`${value.slice(0, 10)}T12:00:00Z`)
  return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month, year: 'numeric', timeZone: 'UTC' }).format(date).replace(/\bSept\b/, 'Sep') : 'Not shown'
}
export const reportNumber = (value: number | null | undefined) => value == null || !Number.isFinite(value) ? 'Not shown' : value.toLocaleString('en-US', { maximumFractionDigits: 1 })
export const reportMoney = (value: number | null | undefined) => value == null || !Number.isFinite(value) ? 'Not shown' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
const words = (n: number) => ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'][n] ?? String(n)
const initial = (s: string) => s.replace(/^./, c => c.toUpperCase())
export const reportName = (value: string | null | undefined) => {
  if (!value || /^(unavailable(?: owner)?|unknown|n\/?a)$/i.test(value.trim())) return 'Not shown'
  return value.replace(/\b[A-Z]{2,}\b/g, word => /^(LLC|LLP|LP|NYC|NYCHA|USA)$/.test(word) ? word : word[0] + word.slice(1).toLowerCase())
}
const monthName = (value?: string | null) => value && reportDate(value) !== 'Not shown' ? new Intl.DateTimeFormat('en-GB', { month: 'long', timeZone: 'UTC' }).format(new Date(`${value.slice(0, 10)}T12:00:00Z`)) : ''
const days = (a: string | null, b: string | null) => {
  if (!a || !b) return null
  const d = (Date.parse(b.slice(0, 10)) - Date.parse(a.slice(0, 10))) / 86400000
  return Number.isFinite(d) && d >= 0 ? Math.round(d) : null
}
const citationDates = (text: string) => [...text.matchAll(/\b(\d{1,2})\/(\d{1,2})\/(\d{4})\b/g)].map(m => `${m[3]}-${m[1].padStart(2, '0')}-${m[2].padStart(2, '0')}`)
const shorten = (s: string, max: number) => s.length <= max ? s : `${s.slice(0, max - 26).replace(/\s+\S*$/, '')}… Full text in account.`

export function reportCitation(v: Violation) {
  const text = v.citation_text || v.violation_text || 'No inspection notes are included in the supplied record.'
  const dates = citationDates(text)
  if (v.violation_code === 'AH8S' && /gap greater than 90 days/i.test(text) && dates.length >= 2) {
    return { title: 'A gap in Legionella sample records', text: `The notes describe a gap longer than 90 days, from ${reportDate(dates[0])} to ${reportDate(dates[1])}.` }
  }
  if (v.violation_code === 'AHK0' && /within 5 days/i.test(text) && dates.length) {
    return { title: 'Late reporting of a sample date', text: `The ${reportDate(dates.at(-1))} sample date was cited as not reported within five days.` }
  }
  if (v.violation_code === 'AHK2' && dates.length && new Set(dates.map(x => x.slice(0, 4))).size === 1) {
    const months = [...new Set(dates.map(x => monthName(x)))]
    return { title: 'Missing reports for earlier sample dates', text: `The inspector cited unreported dates due in ${months.length > 1 ? `${months.slice(0, -1).join(', ')} and ${months.at(-1)}` : months[0]} ${dates[0].slice(0, 4)}.` }
  }
  return { title: shorten(v.violation_text || 'Published inspection finding', 58), text: shorten(text, 150) }
}

export function reportModel(row: SystemSummary, detail: SystemDetail, metadata: Metadata) {
  if (row.system_id !== detail.identity.system_id) throw new Error('Account report identity mismatch')
  const snapshot = detail.metadata.snapshot_date || metadata.snapshot_date
  const dates = [...new Set(detail.sample_history.dates)].filter(d => reportDate(d) !== 'Not shown').sort()
  const latest = detail.sample_history.latest_sample_date || dates.at(-1) || null
  const previous = detail.sample_history.previous_sample_date || dates.at(-2) || null
  const age = days(latest, snapshot)
  const inspection = [...detail.inspection_history].sort((a, b) => (b.inspection_date || '').localeCompare(a.inspection_date || ''))[0]
  const allCases = [...(detail.oath_case_history || [])].filter(c => c.match_basis === 'SUMMONS_NUMBER_EXACT').sort((a, b) => (b.decision_date || b.hearing_date || '').localeCompare(a.decision_date || a.hearing_date || ''))
  const cases = (inspection?.violations || []).map(v => {
    const outcome = v.summons_number ? allCases.find(c => c.ticket_number === v.summons_number) : undefined
    return { ...reportCitation(v), violation: v, outcome, dismissed: outcome?.hearing_result?.trim().toUpperCase() === 'DISMISSED' }
  })
  const uniqueOutcomes = [...new Map(cases.flatMap(c => c.outcome ? [[c.outcome.ticket_number, c.outcome] as const] : [])).values()]
  const knownBalances = uniqueOutcomes.map(c => c.balance_due).filter((n): n is number => n != null && Number.isFinite(n))
  const balance = knownBalances.length ? knownBalances.reduce((a, b) => a + b, 0) : null
  const balanceComplete = cases.length > 0 && cases.every(c => c.outcome?.balance_due != null)
  const dismissed = cases.filter(c => c.dismissed).length
  const unpaid = uniqueOutcomes.filter(c => c.hearing_result !== 'DISMISSED' && (c.balance_due ?? 0) > 0)
  const month = monthName(inspection?.inspection_date)
  const penaltyLine = unpaid.length === 1 && balanceComplete ? `Check the one remaining ${month ? month + ' ' : ''}penalty.` : unpaid.length > 1 ? 'Check the recorded case balances.' : 'Confirm the latest inspection and case records.'
  const dismissalExcluded = detail.scoring?.priority_model_version === '1.1' && ((detail.scoring as typeof detail.scoring & { notes?: string[] }).notes || []).some(n => /excluded after an exact-ticket published dismissal/i.test(n))
  const decisionTitle = dismissed > 0 && cases.length > 0 ? `${initial(words(dismissed))} of the ${words(cases.length)} ${month ? month + ' ' : ''}cases were dismissed.` : cases.length ? `${initial(words(cases.length))} finding${cases.length === 1 ? '' : 's'} appear${cases.length === 1 ? 's' : ''} in the latest inspection.` : 'No findings are shown in the latest joined inspection.'
  const decisionText = unpaid.length === 1 && dismissed > 0 && dismissed === cases.length - 1 ? `One case shows “${reportName(unpaid[0].hearing_result)}” and a ${reportMoney(unpaid[0].balance_due)} balance. The other ${words(dismissed)} were dismissed. The case-by-case details are on page 2.` : cases.length ? `The table on page 2 separates each recorded finding from its exact-ticket case outcome. ${cases.filter(c => !c.outcome).length ? 'Some case outcomes are not shown; do not assume they were dismissed or resolved.' : 'A case decision does not establish current water quality or completed repairs.'}` : inspection ? 'This describes the latest inspection included here, not the full history or current conditions. Review earlier records in the account.' : 'No inspection is included in this snapshot. This does not show whether an inspection took place.'
  const ownerContact = detail.hpd_registration?.contacts.find(c => c.type === 'CorporateOwner' || c.type === 'IndividualOwner')
  const agentContact = detail.hpd_registration?.contacts.find(c => c.type === 'Agent')
  const plutoOwner = reportName(detail.building_context?.owner_name)
  const owner = reportName(ownerContact?.corporation_name || ownerContact?.person_name || detail.building_context?.owner_name)
  const agent = reportName(agentContact?.corporation_name || agentContact?.person_name)
  const findings = (detail.scoring?.components || []).filter(c => /NYC Health findings/i.test(c.reason)).reduce((a, c) => a + c.points, 0)
  const sampling = (detail.scoring?.components || []).filter(c => /sampling follow-up|public sample/i.test(c.reason)).reduce((a, c) => a + c.points, 0)
  const scoreCopy = findings + sampling === row.priority_score ? `This snapshot uses ${findings} points for findings and ${sampling} for sampling follow-up.` : `The published score is ${row.priority_score}/100. See the account for its source-backed breakdown.`
  return { address: reportName(row.address || detail.identity.address).replace(/\bAve\.?$/i, 'Avenue').replace(/\bSt\.?$/i, 'Street'), snapshot, dates, latest, previous, age, interval: days(previous, latest), inspection, cases, balance, balanceComplete, dismissed, unpaid, month, penaltyLine, decisionTitle, decisionText, owner, agent, ownerFromHpd: !!ownerContact, plutoOwner, scoreCopy, dismissalExcluded }
}

export function reportGeometry(detail: SystemDetail) {
  const outlines = (detail.building_footprints || []).filter(f => f.bin === detail.identity.bin && f.match_basis === 'BIN_EXACT')
  const towers = (detail.planimetric_building_tower_features || []).filter(f => f.bin === detail.identity.bin && f.match_basis === 'BIN_EXACT')
  const rings = (g: PlanimetricGeometry) => (g.type === 'Polygon' ? [g.coordinates] : g.coordinates).flat()
  const buildings = outlines.flatMap(f => rings(f.geometry))
  const features = towers.flatMap(f => rings(f.geometry))
  const points = buildings.concat(features).flat().filter(p => p.length >= 2 && p.every(Number.isFinite))
  if (!points.length) return null
  const cosine = Math.cos(points.reduce((a, p) => a + p[1], 0) / points.length * Math.PI / 180)
  const xs = points.map(p => p[0] * cosine), ys = points.map(p => -p[1])
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys)
  if (maxX === minX || maxY === minY) return null
  const scale = Math.min(165 / (maxX - minX), 175 / (maxY - minY))
  const dx = 130 - (maxX - minX) * scale / 2, dy = 27
  const point = (p: number[]) => [(p[0] * cosine - minX) * scale + dx, (-p[1] - minY) * scale + dy]
  const path = (polygons: number[][][]) => polygons.filter(r => r.length >= 3 && r.every(p => p.length >= 2 && p.every(Number.isFinite))).map(r => r.map((p, i) => `${i ? 'L' : 'M'}${point(p).map(n => n.toFixed(3)).join(',')}`).join(' ') + 'Z').join(' ')
  const first = features[0]?.slice(0, -1).map(point)
  const marker = first?.length ? [first.reduce((a, p) => a + p[0], 0) / first.length, first.reduce((a, p) => a + p[1], 0) / first.length] : null
  return { buildingPath: path(buildings), towerPath: path(features), marker, towerCount: towers.length, imageryYear: towers[0]?.imagery_year ?? null }
}
