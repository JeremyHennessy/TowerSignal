import { describe, expect, it } from 'vitest'
import type { ChangeEvent } from '../../src/types/history'
import { eventDate, compareEventDates, inSourceRange, readableValue, sourceLabel } from '../../src/domain/changePresentation'
const event = (patch: Partial<ChangeEvent> = {}): ChangeEvent => ({ event_type: 'VIOLATION_ADDED', system_id: '2000015925', bbl: null, bin: null, address: '1414 MADISON AVE', borough: 'Manhattan', detected_at: '2026-09-15T16:56:42Z', source_observation_date: '2026-07-14', previous_value: null, new_value: { inspection_date: '2026-07-14', description: 'No Maintenance Program or Plan', violation_code: 'AH8A', summons_number: '0881341735' }, source: 'NYC_COOLING_TOWER_INSPECTIONS', evidence_basis: 'SYSTEM_ID_EXACT', priority_score: 78, evidence_confidence: 'CONFIRMED', contact_available: true, ...patch })
describe('Monitor source-event dates', () => {
  it('shows the July inspection, not September collection, for the reported Madison violation', () => { expect(eventDate(event())).toEqual({ value: '2026-07-14', label: 'Inspection date' }) })
  it('prefers an explicit violation date over the inspection reference', () => { expect(eventDate(event({ new_value: { violation_date: '2026-07-13', inspection_date: '2026-07-14' } }))).toEqual({ value: '2026-07-13', label: 'Violation date' }) })
  it('does not relabel the observation timestamp as an event date', () => { expect(eventDate(event({ source_observation_date: null, new_value: {} })).value).toBeNull() })
  it('rejects invalid source dates and never guesses the collection date', () => { expect(eventDate(event({ source_observation_date: '2026-02-30', new_value: { inspection_date: 'invalid' } })).value).toBeNull() })
  it('preserves calendar dates independent of timezone', () => { expect(eventDate(event({ new_value: { inspection_date: '2026-07-14T00:00:00Z' } })).value).toBe('2026-07-14') })
  it('supports previously serialized violation records', () => { expect(eventDate(event({ new_value: '{"inspection_date":"2026-07-12"}' })).value).toBe('2026-07-12') })
  it('sorts by source date, keeping undated last in both directions', () => {
    const older = event(), newer = event({ new_value: { inspection_date: '2026-09-12' }, detected_at: '2026-09-13' }), undated = event({ source_observation_date: null, new_value: {} })
    expect(compareEventDates(older, newer, 'desc')).toBeGreaterThan(0)
    for (const direction of ['asc', 'desc'] as const) expect(compareEventDates(undated, newer, direction)).toBeGreaterThan(0)
  })
  it('filters by event date even for a newly ingested old event', () => {
    expect(inSourceRange(event(), '7', '', '', '2026-09-15')).toBe(false)
    expect(inSourceRange(event(), 'custom', '2026-07-14', '2026-07-14', '2026-09-15')).toBe(true)
  })
  it('uses inclusive calendar days and excludes future scheduled dates from recent ranges', () => {
    const dated = (day: string) => event({ new_value: { inspection_date: day } })
    expect(inSourceRange(dated('2026-09-09'), '7', '', '', '2026-09-15')).toBe(true)
    expect(inSourceRange(dated('2026-09-08'), '7', '', '', '2026-09-15')).toBe(false)
    expect(inSourceRange(dated('2026-09-16'), '7', '', '', '2026-09-15')).toBe(false)
  })
  it('includes undated records only with all retained dates', () => {
    const missing = event({ source_observation_date: null, new_value: {} })
    expect(inSourceRange(missing, '0', '', '', '2026-09-15')).toBe(true)
    expect(inSourceRange(missing, 'custom', '', '', '2026-09-15')).toBe(false)
  })
  it('labels ambiguous OATH dates as case references, not violation dates', () => { expect(eventDate(event({ event_type: 'OATH_CASE_ADDED', source_observation_date: '2026-10-13', new_value: { ticket_number: '0881345237' } })).label).toBe('Case reference date') })
  it('does not treat latest sample as the date a derived gap signal changed', () => { expect(eventDate(event({ event_type: 'SAMPLING_GAP_ENTERED', new_value: true })).label).toBe('Sample reference date') })
  it('formats structured details and source names rather than rendering raw JSON', () => {
    expect(readableValue({ ticket_number: '0881345237', hearing_result: 'DISMISSED' })).toBe('Summons: 0881345237 · Result: DISMISSED')
    expect(readableValue({ penalty_imposed: 2000 })).toBe('Penalty: $2,000.00')
    expect(sourceLabel(event().source)).toBe('NYC Health inspections')
  })
})
