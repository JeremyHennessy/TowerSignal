import type { ChangeEvent } from '../types/history'
import { formatDate } from './labels'
import { readableValue, recordValue, sourceDay } from './changePresentation'

export interface MonitorField {
  key: string
  label: string
  value: string
  previous?: string
}

const fieldLabels: Record<string, string> = {
  job_filing_number: 'Job', ticket_number: 'Ticket', summons_number: 'Summons',
  filing_status: 'Filing status', hearing_status: 'Case status', hearing_result: 'Hearing result',
  penalty_imposed: 'Penalty imposed', balance_due: 'Balance due', job_type: 'Job type',
  filing_date: 'Filed', approved_date: 'Approved', first_permit_date: 'Permit issued',
  signoff_date: 'Signed off', current_status_date: 'Status date', decision_date: 'Decision date',
  inspection_date: 'Inspection date', inspection_type: 'Inspection type', violation_date: 'Violation date',
  explicit_cooling_tower_mention: 'Explicit cooling-tower mention', job_description: 'Work description',
  hpd_registration_id: 'Registration', hpd_last_registration_date: 'Registration date',
  registration_contact_id: 'Contact record', corporation_name: 'Company', person_name: 'Contact',
  business_address: 'Business address', type: 'Contact type', description: 'Description',
  title: 'Title', status: 'Status', present_in_snapshot: 'Present in registry snapshot',
}
const scalarLabels: Record<string, string> = {
  SAMPLE_REPORTED: 'Public sample date', LATEST_SAMPLE_CHANGED: 'Public sample date',
  SAMPLING_GAP_ENTERED: 'Sampling-gap flag', SAMPLING_GAP_RESOLVED: 'Sampling-gap flag',
  ACTIVE_EQUIPMENT_CHANGED: 'Active equipment', PLUTO_OWNER_CHANGED: 'Recorded owner',
}
const dateFields = new Set(['sample_date', 'filing_date', 'approved_date', 'first_permit_date', 'signoff_date',
  'current_status_date', 'decision_date', 'inspection_date', 'violation_date', 'hpd_last_registration_date'])
const moneyFields = new Set(['penalty_imposed', 'balance_due'])

/** Presentation only: retain identifiers, zero amounts, booleans and unknown fields. */
export function formatMonitorField(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Not published'
  if (dateFields.has(key) && sourceDay(value)) return formatDate(sourceDay(value))
  if (moneyFields.has(key) && (typeof value === 'number' || typeof value === 'string' && /^-?\d+(\.\d+)?$/.test(value))) {
    const amount = Number(value)
    if (Number.isFinite(amount)) return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount)
  }
  if (key === 'sampling_flag' && typeof value === 'boolean') return value ? 'Flagged' : 'Not flagged'
  return readableValue(value)
}

export function monitorFields(event: ChangeEvent): MonitorField[] {
  const current = recordValue(event.new_value), previous = recordValue(event.previous_value)
  const keys = [...new Set([...Object.keys(current), ...Object.keys(previous)])]
  if (!keys.length) {
    const key = event.event_type.includes('SAMPLE') ? 'sample_date'
      : event.event_type.startsWith('SAMPLING_GAP_') ? 'sampling_flag' : 'value'
    const value = formatMonitorField(key, event.new_value)
    const old = event.previous_value == null ? undefined : formatMonitorField(key, event.previous_value)
    return [{ key, label: scalarLabels[event.event_type] ?? 'Source value', value,
      ...(old !== undefined && old !== value ? { previous: old } : {}) }]
  }
  return keys.filter(key => current[key] != null && current[key] !== '' || previous[key] != null && previous[key] !== '').map(key => {
    const value = formatMonitorField(key, current[key])
    const old = formatMonitorField(key, previous[key])
    const hasPreviousRecord = Object.keys(previous).length > 0
    return { key, label: fieldLabels[key] ?? key.replaceAll('_', ' ').replace(/^./, char => char.toUpperCase()),
      value, ...(hasPreviousRecord && old !== value ? { previous: old } : {}) }
  })
}
