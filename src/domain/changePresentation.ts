import type { ChangeEvent } from '../types/history'

export function recordValue(value: unknown): Record<string, unknown> {
  if (value && typeof value === 'object' && !Array.isArray(value)) return value as Record<string, unknown>
  if (typeof value === 'string' && value.trim().startsWith('{')) {
    try { return recordValue(JSON.parse(value)) } catch { return {} }
  }
  return {}
}

// Source calendar dates must not shift with the browser's timezone. Never
// substitute detected_at: it is an observation timestamp, not an event date.
function calendarDate(value: unknown): string | null {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}(?:$|T| )/.test(value)) return null
  const day = value.slice(0, 10)
  const time = Date.parse(`${day}T00:00:00Z`)
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === day ? day : null
}

type SourceDate = { value: string | null; label: string; note?: string }
export function eventDate(event: ChangeEvent): SourceDate {
  const record = recordValue(event.new_value)
  const dated = (field: string, label: string): SourceDate | null => {
    const value = calendarDate(record[field])
    return value ? { value, label } : null
  }
  const source = calendarDate(event.source_observation_date)
  const type = event.event_type
  if (type === 'VIOLATION_ADDED' || type === 'VIOLATION_STATUS_CHANGED') {
    return dated('violation_date', 'Violation date') ?? dated('inspection_date', 'Inspection date') ?? {
      value: source, label: source ? 'Inspection date' : 'Date not published',
      note: 'This cooling-tower source reports the inspection date associated with the violation, not when TowerSignal collected it.',
    }
  }
  if (type === 'INSPECTION_ADDED') return dated('inspection_date', 'Inspection date') ?? { value: source, label: 'Inspection date' }
  if (type === 'SAMPLE_REPORTED' || type === 'LATEST_SAMPLE_CHANGED') return { value: calendarDate(event.new_value) ?? source, label: 'Sample date' }
  if (type.startsWith('SAMPLING_GAP_')) return {
    value: source, label: 'Sample reference date',
    note: 'The source date is the latest published sample, not the date the derived sampling-gap signal changed.',
  }
  if (type.startsWith('OATH_')) return dated('decision_date', 'Decision date') ?? dated('hearing_date', 'Hearing date') ?? dated('violation_date', 'Violation date') ?? {
    value: source, label: source ? 'Case reference date' : 'Date not published',
    note: 'The retained OATH reference may be a decision, scheduled hearing or violation date. It is not proof that this status, penalty or balance changed on that date.',
  }
  if (type.startsWith('HPD_')) return {
    value: calendarDate(record.last_registration_date) ?? source, label: source ? 'Registration reference date' : 'Date not published',
    note: 'The registration source date does not establish when a contact or managing agent changed.',
  }
  const dobFields: Record<string, [string, string]> = {
    DOB_JOB_FILED: ['filing_date', 'Filed date'], DOB_PERMIT_ISSUED: ['first_permit_date', 'Permit date'],
    DOB_JOB_APPROVED: ['approved_date', 'Approval date'], DOB_JOB_SIGNED_OFF: ['signoff_date', 'Sign-off date'],
  }
  if (dobFields[type]) {
    const [field, label] = dobFields[type]
    return dated(field, label) ?? { value: source, label: source ? label : 'Date not published' }
  }
  if (type.startsWith('DOB_')) return { value: source, label: source ? 'DOB reference date' : 'Date not published' }
  if (type === 'SYSTEM_FIRST_SEEN') return dated('date_registered', 'Registration date') ?? { value: source, label: source ? 'Registration reference date' : 'Date not published' }
  return { value: source, label: source ? 'Source reference date' : 'Date not published' }
}

export function compareEventDates(a: ChangeEvent, b: ChangeEvent, direction: 'asc' | 'desc'): number {
  const left = eventDate(a).value, right = eventDate(b).value
  if (!left || !right) return left ? -1 : right ? 1 : 0
  return left.localeCompare(right) * (direction === 'asc' ? 1 : -1)
}

export function inSourceRange(event: ChangeEvent, days: string, from: string, to: string, today: string): boolean {
  if (days === '0') return true
  const value = eventDate(event).value
  if (!value) return false
  if (days === 'custom') return (!from || value >= from) && (!to || value <= to) && !(from && to && from > to)
  const span = Number(days)
  if (!Number.isInteger(span) || span < 1 || !calendarDate(today)) return false
  const lower = new Date(Date.parse(`${today}T00:00:00Z`) - (span - 1) * 86_400_000).toISOString().slice(0, 10)
  return value >= lower && value <= today
}

const sources: Record<string, string> = {
  NYC_COOLING_TOWER_INSPECTIONS: 'NYC Health inspections',
  NYC_COOLING_TOWER_REGISTRATIONS: 'NYC tower registry',
  NYC_OATH_HEARINGS_DIVISION_CASE_STATUS: 'OATH case records',
  NYC_DOB_NOW_JOB_APPLICATION_FILINGS: 'DOB NOW filings',
  NYC_HPD_REGISTRATION_CONTACTS: 'HPD registered contacts',
  NYC_HPD_MULTIPLE_DWELLING_REGISTRATION: 'HPD registrations',
  NYC_DCP_PLUTO: 'NYC PLUTO property records',
  TOWERSIGNAL_DERIVED: 'TowerSignal derived signal',
}
export const sourceLabel = (value: string) => sources[value] ?? value.replaceAll('_', ' ')
export const evidenceLabel = (value: string) => value.split(';').map(part => ({
  SYSTEM_ID_EXACT: 'Exact system ID', BBL_EXACT: 'Exact BBL', BIN_EXACT: 'Exact BIN',
  SUMMONS_TICKET_EXACT: 'Exact summons match', REGISTRATION_ID_EXACT: 'Exact registration ID',
  JOB_FILING_NUMBER_EXACT: 'Exact filing number', DETERMINISTIC_RULE_CHANGE: 'Rule-derived signal',
  JOB_DESCRIPTION_EXPLICIT_COOLING_TOWER_TEXT: 'Explicit cooling-tower wording',
})[part.trim()] ?? part.trim().replaceAll('_', ' ').toLowerCase()).join(' · ')

const labels: Record<string, string> = {
  ticket_number: 'Summons', summons_number: 'Summons', job_filing_number: 'Filing', filing_status: 'Status',
  hearing_status: 'Hearing status', hearing_result: 'Result', inspection_type: 'Inspection', inspection_status: 'Status',
  penalty_imposed: 'Penalty', amount_due: 'Balance due', balance_due: 'Balance due', contact_type: 'Contact',
  corporation: 'Organization', first_name: 'First name', last_name: 'Last name', business_address: 'Business address',
  latest_sample_date: 'Latest sample', last_registration_date: 'Registration', job_description: 'Work',
}
function words(value: string): string { return value.replaceAll('_', ' ').replace(/^\w/, first => first.toUpperCase()) }
export function readableValue(value: unknown, depth = 0): string {
  if (value == null || value === '') return 'Not published'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (typeof value === 'number') return value.toLocaleString('en-US')
  if (typeof value === 'string') {
    if (value.trim().startsWith('{')) {
      const parsed = recordValue(value)
      return Object.keys(parsed).length ? readableValue(parsed, depth) : 'Source detail unavailable'
    }
    return value
  }
  if (depth > 3) return 'Additional source details'
  if (Array.isArray(value)) return value.map(item => readableValue(item, depth + 1)).join(' · ') || 'No entries'
  return Object.entries(recordValue(value)).filter(([, v]) => v != null && v !== '').map(([key, v]) => {
    const number = typeof v === 'number' && /penalty|amount_due|balance/.test(key)
      ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(v) : readableValue(v, depth + 1)
    return `${labels[key] ?? words(key)}: ${number}`
  }).join(' · ') || 'No published details'
}
