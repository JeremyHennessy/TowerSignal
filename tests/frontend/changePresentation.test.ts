import { expect, test } from 'vitest'
import { compareEventDates, eventDate, inSourceRange, readableValue, sourceDay } from '../../src/domain/changePresentation'
import type { ChangeEvent } from '../../src/types/history'
const event = (values: Partial<ChangeEvent> = {}): ChangeEvent => ({ event_type: 'VIOLATION_ADDED', system_id:'1', bbl:null,bin:null,address:'1414 MADISON AVE',borough:'Manhattan', detected_at:'2026-09-15T16:56:00Z',source_observation_date:'2026-07-14',previous_value:null,new_value:{violation_text:'Missing records', summons_number:'0123'},source:'NYC_COOLING_TOWER_INSPECTIONS',evidence_basis:'SYSTEM_ID_EXACT',priority_score:78,evidence_confidence:'CONFIRMED',contact_available:true,...values })
test('violation uses occurrence or labeled inspection date, never ingestion time', () => {
  expect(eventDate(event())).toMatchObject({ value:'2026-07-14',label:'Inspection date' })
  expect(eventDate(event({new_value:{violation_date:'2026-07-13',inspection_date:'2026-07-14'}}))).toMatchObject({ value:'2026-07-13',label:'Violation date' })
  expect(eventDate(event({source_observation_date:null})).value).toBeNull()
})
test('future hearing date is not reused as OATH balance-change date', () => {
  expect(eventDate(event({event_type:'OATH_BALANCE_CHANGED',source_observation_date:'2027-04-15'})).value).toBeNull()
})
test('sort and date filters use source dates and retain undated only in all dates', () => {
  const old = event(), recent = event({source_observation_date:'2026-09-10'}), missing=event({source_observation_date:null})
  expect(compareEventDates(recent,old,'desc')).toBeLessThan(0)
  expect(compareEventDates(missing,old,'asc')).toBeGreaterThan(0)
  expect(inSourceRange(old,'7','','','2026-09-15')).toBe(false)
  expect(inSourceRange(old,'custom','2026-07-01','2026-07-31','2026-09-15')).toBe(true)
  expect(inSourceRange(missing,'0','','','2026-09-15')).toBe(true)
  expect(inSourceRange(missing,'7','','','2026-09-15')).toBe(false)
})
test('calendar day is timezone stable and invalid dates rejected', () => {
  expect(sourceDay('2026-07-14T00:00:00')).toBe('2026-07-14')
  expect(sourceDay('2026-02-30')).toBeNull()
  expect(sourceDay(null)).toBeNull()
})
test('raw source objects are readable descriptions, not JSON syntax', () => {
  expect(readableValue({ticket_number:'0123',balance_due:100})).toBe('Ticket: 0123 · Balance: 100')
  expect(readableValue(null)).toBe('Not published')
})
