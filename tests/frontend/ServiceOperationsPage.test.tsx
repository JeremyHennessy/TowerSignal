import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import { ServiceOperationsPage } from '../../src/components/ServiceOperationsPage'
import * as client from '../../src/serviceReporting/client'
import type { ServiceOperationsOverview } from '../../src/types/serviceReporting'

vi.mock('../../src/serviceReporting/client', () => ({
  loadServiceReportingAccess: vi.fn(),
  loadServiceOperationsOverview: vi.fn(),
}))

beforeEach(() => vi.clearAllMocks())

const overview: ServiceOperationsOverview = {
  clients:[{
    client_id:'client-1',name:'Example Client',linked_company_id:null,billing_name:null,status:'active',
    account_owner:null,notes:null,created_at:'2026-09-24T00:00:00Z',updated_at:'2026-09-24T00:00:00Z',
  }],
  portfolios:[{
    portfolio_id:'portfolio-1',client_id:'client-1',name:'NYC Portfolio',description:null,status:'active',
    created_at:'2026-09-24T00:00:00Z',updated_at:'2026-09-24T00:00:00Z',
  }],
  sites:[{
    service_site_id:'site-1',system_id:'2000014227',client_id:'client-1',portfolio_id:'portfolio-1',
    display_name:'400 West 61st Street',address:'400 West 61st Street',status:'active',access_notes:null,service_notes:null,
    created_at:'2026-09-24T00:00:00Z',updated_at:'2026-09-24T00:00:00Z',
  }],
  assets:[],
  agreements:[],
  visits:[{
    visit_id:'visit-1',service_site_id:'site-1',agreement_id:null,status:'scheduled',visit_type:'routine',
    scheduled_for:new Date(Date.now()+86400000).toISOString(),started_at:null,completed_at:null,technician_name:'Technician A',
    summary:null,next_visit_date:null,report_status:'draft',created_at:'2026-09-24T00:00:00Z',updated_at:'2026-09-24T00:00:00Z',
  }],
  measurements:[],
  actions:[{
    action_id:'action-1',service_site_id:'site-1',visit_id:'visit-1',asset_id:null,title:'Correct chemical feed',
    severity:'high',status:'open',due_date:'2020-01-01',completed_at:null,owner:null,details:null,
    created_at:'2026-09-24T00:00:00Z',updated_at:'2026-09-24T00:00:00Z',
  }],
  reports:[{
    report_id:'report-1',service_site_id:'site-1',visit_id:'visit-1',report_number:null,title:'Visit report',
    status:'ready',executive_summary:null,recommendations:null,generated_at:null,finalized_at:null,client_visible:false,
    created_at:'2026-09-24T00:00:00Z',updated_at:'2026-09-24T00:00:00Z',
  }],
  documents:[{
    document_id:'doc-1',service_site_id:'site-1',visit_id:'visit-1',report_id:'report-1',asset_id:null,
    document_type:'photo',file_name:'tower.jpg',mime_type:'image/jpeg',storage_url:null,sha256:null,captured_at:null,notes:null,
    extraction_status:'pending',extracted_text:null,created_at:'2026-09-24T00:00:00Z',updated_at:'2026-09-24T00:00:00Z',
  }],
}

test('service operations is admin gated', async () => {
  vi.mocked(client.loadServiceReportingAccess).mockResolvedValue(false)
  render(<ServiceOperationsPage />)
  expect(await screen.findByText('Admin service access required.')).toBeInTheDocument()
  expect(client.loadServiceOperationsOverview).not.toHaveBeenCalled()
})

test('service operations renders private portfolio metrics and account drill-through', async () => {
  vi.mocked(client.loadServiceReportingAccess).mockResolvedValue(true)
  vi.mocked(client.loadServiceOperationsOverview).mockResolvedValue(overview)
  render(<ServiceOperationsPage />)

  expect(await screen.findByRole('heading',{name:'Service operations'})).toBeInTheDocument()
  expect(screen.getAllByText('400 West 61st Street').length).toBeGreaterThanOrEqual(2)
  expect(screen.getAllByText('Example Client').length).toBeGreaterThanOrEqual(2)
  expect(screen.getAllByText('NYC Portfolio').length).toBeGreaterThanOrEqual(2)
  expect(screen.getByText('Correct chemical feed')).toBeInTheDocument()
  const link=screen.getByRole('link',{name:'Open account 2000014227'})
  expect(link).toHaveAttribute('href','#/account/2000014227')
  await waitFor(()=>expect(client.loadServiceOperationsOverview).toHaveBeenCalledTimes(1))
})
