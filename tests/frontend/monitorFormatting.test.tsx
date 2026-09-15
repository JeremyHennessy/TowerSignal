import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { ChangesView } from '../../src/components/ChangesView'
import { formatMonitorField, monitorFields } from '../../src/domain/monitorFields'
import { eventDate } from '../../src/domain/changePresentation'
import type { ChangeEvent, ChangesPayload } from '../../src/types/history'

afterEach(cleanup)
const event = (patch: Partial<ChangeEvent> = {}): ChangeEvent => ({ event_type:'OATH_BALANCE_CHANGED',system_id:'2000000001',bbl:null,bin:null,
  address:'10 MAIN ST',borough:'Manhattan',detected_at:'2026-09-15T16:56:42Z',source_observation_date:'2027-04-15',
  previous_value:{ticket_number:'00123',balance_due:1030},new_value:{ticket_number:'00123',balance_due:0},
  source:'NYC_OATH_HEARINGS_DIVISION_CASE_STATUS',evidence_basis:'SUMMONS_TICKET_EXACT',priority_score:70,evidence_confidence:'CONFIRMED',contact_available:true,...patch })
const payload = (events: ChangeEvent[]): ChangesPayload => ({history_schema_version:'1',history_started_at:'2026-08-01',observed_at:'2026-09-15',baseline_initialized:false,new_event_count:events.length,events})

test('OATH dollars and exact ticket identifiers remain distinguishable, including zero', () => {
  expect(monitorFields(event())).toEqual([{key:'ticket_number',label:'Ticket',value:'00123'},
    {key:'balance_due',label:'Balance due',value:'$0.00',previous:'$1,030.00'}])
  expect(eventDate(event()).value).toBeNull()
  expect(formatMonitorField('penalty_imposed','12.50')).toBe('$12.50')
  expect(formatMonitorField('ticket_number','000012')).toBe('000012')
})
test('sample date values are formatted without changing the source day', () => {
  const record=event({event_type:'LATEST_SAMPLE_CHANGED',previous_value:'2026-07-01',new_value:'2026-07-14',source_observation_date:'2026-07-14'})
  expect(monitorFields(record)[0]).toMatchObject({value:'Jul 14, 2026',previous:'Jul 1, 2026'})
  expect(eventDate(record).value).toBe('2026-07-14')
  expect(monitorFields({...record,new_value:null})[0].value).toBe('Not published')
})
test('false, zero, missing values, unknown fields and serialized records are retained', () => {
  expect(formatMonitorField('explicit_cooling_tower_mention',false)).toBe('No')
  expect(formatMonitorField('active_equipment',0)).toBe('0')
  expect(monitorFields(event({previous_value:null,new_value:'{"ticket_number":"0003","new_field":"Published"}'}))).toEqual([
    {key:'ticket_number',label:'Ticket',value:'0003'},{key:'new_field',label:'New field',value:'Published'}])
  expect(monitorFields(event({previous_value:{title:'Manager'},new_value:{title:null}}))[0]).toMatchObject({previous:'Manager',value:'Not published'})
})
test('derived sampling flags do not masquerade as sample dates', () => {
  const record=event({event_type:'SAMPLING_GAP_RESOLVED',previous_value:true,new_value:false,source_observation_date:'2026-09-14'})
  expect(monitorFields(record)[0]).toMatchObject({label:'Sampling-gap flag',value:'Not flagged',previous:'Flagged'})
  expect(eventDate(record).value).toBeNull()
})
test('structured fields separate old and new values and preserve account navigation', async () => {
  const onSelect=vi.fn();render(<ChangesView payload={payload([event()])} onSelectSystem={onSelect} />)
  const row=screen.getAllByRole('row')[1]
  expect(within(row).getByText('$1,030.00')).toBeVisible();expect(within(row).getByText('$0.00')).toBeVisible()
  expect(within(row).getByText('Previous')).toBeVisible();expect(within(row).getByText('New')).toBeVisible()
  expect(row.querySelector('.monitor-account-cell a')).toHaveAttribute('href','#/account/2000000001')
  expect(screen.getAllByRole('columnheader')).toHaveLength(5)
  expect(within(row).getByText('Not published')).toBeVisible()
  expect(row.textContent).not.toContain('{"')
  await userEvent.click(within(row).getByText('Provenance'));expect(onSelect).not.toHaveBeenCalled()
})
test('all seven categories use the same readable table and unchanged category counts', async () => {
  const records=[event(),event({event_type:'VIOLATION_ADDED',new_value:{description:'Missing plan'},previous_value:null}),
    event({event_type:'DOB_JOB_FILED',new_value:{job_filing_number:'M0001',filing_date:'2026-07-14'},previous_value:null}),
    event({event_type:'SAMPLE_REPORTED',new_value:'2026-07-14',previous_value:null}),
    event({event_type:'PLUTO_OWNER_CHANGED',new_value:'NEW OWNER',previous_value:'OLD OWNER'})]
  const before=JSON.stringify(records);render(<ChangesView payload={payload(records)} onSelectSystem={()=>{}} />)
  const user=userEvent.setup();const tabs=screen.getAllByRole('tab');expect(tabs).toHaveLength(7)
  for(const [index,count] of [5,5,1,1,1,1,1].entries()){
    await user.click(tabs[index]);expect(screen.getAllByRole('row')).toHaveLength(count+1)
    expect(tabs[index]).toHaveAttribute('aria-selected','true')
  }
  expect(JSON.stringify(records)).toBe(before)
})
test('top and bottom pagination remain synchronized and touch sorting resets the page', async () => {
  const records=Array.from({length:55},(_,i)=>event({system_id:String(i).padStart(10,'0'),address:`Account ${String(i).padStart(2,'0')}`}))
  render(<ChangesView payload={payload(records)} onSelectSystem={()=>{}} />)
  const user=userEvent.setup();const top=screen.getByRole('navigation',{name:'Monitor pagination top'})
  await user.click(within(top).getByRole('button',{name:'Next'}))
  expect(screen.getAllByText('Page 2 of 2')).toHaveLength(2);expect(screen.getAllByRole('row')).toHaveLength(6)
  await user.selectOptions(screen.getByLabelText('Sort events'),'address:desc')
  expect(screen.getAllByText('Page 1 of 2')).toHaveLength(2)
  expect(within(screen.getAllByRole('row')[1]).getByText('Account 54')).toBeVisible()
})
