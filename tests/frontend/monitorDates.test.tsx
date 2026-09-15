import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { ChangesView } from '../../src/components/ChangesView'
import type { ChangesPayload } from '../../src/types/history'
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
test('Monitor renders July inspection date and citation, with collection timestamp only in provenance', async () => {
 const payload={history_schema_version:'1',history_started_at:'2026-08-01',observed_at:'2026-09-15',baseline_initialized:false,new_event_count:1,events:[{event_type:'VIOLATION_ADDED',system_id:'1',bbl:null,bin:null,address:'1414 MADISON AVE',borough:'Manhattan',detected_at:'2026-09-15T16:56:00Z',source_observation_date:'2026-07-14',new_value:{violation_text:'Maintain monitoring records',violation_code:'A1',summons_number:'0123'},previous_value:null,source:'NYC_COOLING_TOWER_INSPECTIONS',evidence_basis:'SYSTEM_ID_EXACT',priority_score:78,evidence_confidence:'CONFIRMED',contact_available:true}]} as ChangesPayload
 render(<ChangesView payload={payload} onSelectSystem={()=>{}} />)
 const body=screen.getAllByRole('row')[1]
 expect(within(body).getByText('Jul 14, 2026')).toBeVisible()
 expect(within(body).getByText('Inspection date')).toBeVisible()
 expect(within(body).getByText('Maintain monitoring records')).toBeVisible()
 expect(within(body).getByText('Summons 0123')).toBeVisible()
 expect(body.querySelector('time')).toHaveAttribute('datetime','2026-07-14')
 expect(body.textContent).not.toContain('{"')
 expect(body.querySelector('details')).not.toHaveAttribute('open')
 const user=userEvent.setup()
 await user.selectOptions(screen.getByLabelText('Event date range'),'custom')
 await user.type(screen.getByLabelText('From'),'2026-09-01')
 expect(screen.getByText('No recorded events match these filters.')).toBeVisible()
})
