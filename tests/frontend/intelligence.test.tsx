import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { LegionellaIntelligence } from '../../src/components/LegionellaIntelligence'
import { ChangesView } from '../../src/components/ChangesView'
import type { ChangesPayload } from '../../src/types/history'
afterEach(() => { cleanup(); vi.unstubAllGlobals() })
test('Home archive shows true publication dates, publisher, building links and searchable records', async () => {
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:true,json:async()=>({domain:'LEGIONELLA_PUBLIC_HEALTH_ALERTS',generated_at:'2026-09-15',summary:{source_channel_count:12,retrieval_error_count:0},items:[{item_id:'1',url:'https://www.nyc.gov/site/doh/about/press/pr2026/bronx.page',title:'readable-slug-headline',published_date:'2026-09-13',retrieved_at:'2026-09-15T16:00:00Z',agency:'NYC Health Department',document_type:'HTML',linked_building_count:1,building_links:[{system_id:'100',system_address:'10 MAIN ST',address:'10 Main St',bin:'2000001',result:'PCR_POSITIVE_REMEDIATION_ORDER',source_url:'https://www.nyc.gov/source',link_basis:'NAMED_IN_SOURCE'}]}]})}))
 render(<LegionellaIntelligence />)
 expect(await screen.findByText('Readable Slug Headline')).toBeVisible()
 expect(screen.getByText('Sep 13, 2026')).toBeVisible()
 expect(screen.getByText('1 named buildings · 1 system links')).toBeVisible()
 const user=userEvent.setup()
 await user.click(screen.getByText('Evidence & tower links'))
 expect(screen.getByRole('link',{name:'10 MAIN ST →'})).toHaveAttribute('href','#/account/100')
 await user.type(screen.getByRole('searchbox'), 'unmatched')
 expect(screen.getByText('No records match these filters.')).toBeVisible()
})
test('unavailable archive remains an explicit error, not zero news', async () => {
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:503}))
 render(<LegionellaIntelligence />)
 expect(await screen.findByRole('alert')).toHaveTextContent('This does not mean there are no alerts.')
})
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
