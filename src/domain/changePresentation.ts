import type { ChangeEvent } from '../types/history'

/** Calendar dates stay in the source's day; collection time is never a fallback. */
export function sourceDay(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const match = /^(\d{4}-\d{2}-\d{2})(?:$|T| )/.exec(value.trim())
  if (!match) return null
  const time = Date.parse(`${match[1]}T00:00:00Z`)
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === match[1] ? match[1] : null
}
export function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}
export function eventDate(event: ChangeEvent): { value: string | null; label: string; note: string } {
  const record = recordValue(event.new_value)
  const direct = (field: string, label: string, useSource = true) => ({ value: sourceDay(record[field]) ?? (useSource ? sourceDay(event.source_observation_date) : null), label, note: '' })
  switch (event.event_type) {
    case 'VIOLATION_ADDED':
      return sourceDay(record.violation_date) ? direct('violation_date', 'Violation date') : direct('inspection_date', 'Inspection date')
    case 'INSPECTION_ADDED': return direct('inspection_date', 'Inspection date')
    case 'SAMPLE_REPORTED': case 'LATEST_SAMPLE_CHANGED':
      return { value: sourceDay(event.new_value) ?? sourceDay(event.source_observation_date), label: 'Sample date', note: '' }
    case 'DOB_JOB_FILED': return direct('filing_date', 'Filing date')
    case 'DOB_JOB_APPROVED': return direct('approved_date', 'Approval date')
    case 'DOB_JOB_SIGNED_OFF': return direct('signoff_date', 'Sign-off date')
    case 'DOB_PERMIT_ISSUED': return direct('first_permit_date', 'Permit date')
    case 'DOB_STATUS_CHANGED': return direct('current_status_date', 'Status date')
    case 'HPD_REGISTRATION_CHANGED': return direct('hpd_last_registration_date', 'Registration date')
    case 'OATH_CASE_ADDED': return direct('violation_date', 'Violation date', false)
    case 'OATH_DECISION_CHANGED': return direct('decision_date', 'Decision date', false)
    default: return { value: null, label: 'Date not published', note: 'The source does not publish an occurrence date for this change. Collection time and case/reference dates are not substituted.' }
  }
}
export function compareEventDates(a: ChangeEvent, b: ChangeEvent, direction: 'asc' | 'desc'): number {
  const left = eventDate(a).value, right = eventDate(b).value
  if (!left || !right) return left ? -1 : right ? 1 : 0
  return left.localeCompare(right) * (direction === 'asc' ? 1 : -1)
}
export function inSourceRange(event: ChangeEvent, days: string, start: string, end: string, today: string): boolean {
  if (days === '0') return true
  const value = eventDate(event).value
  if (!value) return false
  if (days === 'custom') return (!start || value >= start) && (!end || value <= end)
  const cutoff = new Date(Date.parse(`${today}T00:00:00Z`) - (Number(days) - 1) * 86400000).toISOString().slice(0, 10)
  return value >= cutoff && value <= today
}
export function readableValue(value: unknown): string {
  if (value == null) return 'Not published'
  if (typeof value !== 'object') return typeof value === 'boolean' ? value ? 'Yes' : 'No' : String(value)
  if (Array.isArray(value)) return value.map(readableValue).join(' · ')
  const labels: Record<string, string> = { job_filing_number: 'Job', ticket_number: 'Ticket', inspection_date: 'Inspected', inspection_type: 'Inspection', filing_status: 'Status', hearing_status: 'Case status', hearing_result: 'Result', penalty_imposed: 'Penalty', balance_due: 'Balance', first_permit_date: 'Permit', approved_date: 'Approved', signoff_date: 'Signed off', filing_date: 'Filed', corporation_name: 'Company', person_name: 'Contact', hpd_registration_id: 'Registration' }
  return Object.entries(recordValue(value)).filter(([, v]) => v != null && v !== '').map(([key, v]) => `${labels[key] ?? key.replaceAll('_', ' ')}: ${readableValue(v)}`).join(' · ') || 'No published detail'
}
export function sourceLabel(value: string): string {
  const labels: Record<string, string> = { NYC_COOLING_TOWER_INSPECTIONS: 'NYC Health · tower inspections', NYC_COOLING_TOWER_REGISTRATIONS: 'NYC Health · tower registry', NYC_OATH_HEARINGS_DIVISION_CASE_STATUS: 'OATH · case status', NYC_DOB_NOW_JOB_APPLICATION_FILINGS: 'DOB NOW · filings', NYC_HPD_REGISTRATION_CONTACTS: 'HPD · registered contacts', NYC_HPD_MULTIPLE_DWELLING_REGISTRATION: 'HPD · registrations', NYC_DCP_MAPPLUTO: 'DCP · MapPLUTO' }
  return labels[value] ?? value.replaceAll('_', ' ')
}
export function evidenceLabel(value: string): string {
  return value.split(';').map(v => ({ SYSTEM_ID_EXACT: 'Exact system ID', BBL_EXACT: 'Exact property BBL', BIN_EXACT: 'Exact building BIN', SUMMONS_TICKET_EXACT: 'Exact summons / ticket', JOB_FILING_NUMBER_EXACT: 'Exact filing', REGISTRATION_ID_EXACT: 'Exact registration' }[v.trim()] ?? v.trim().replaceAll('_', ' ').toLowerCase())).join(' · ')
}
