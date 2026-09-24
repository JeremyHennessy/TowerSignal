import { useEffect, useMemo, useState } from 'react'
import { loadServiceOperationsOverview, loadServiceReportingAccess } from '../serviceReporting/client'
import type { ServiceOperationsOverview } from '../types/serviceReporting'

const number=new Intl.NumberFormat('en-US')
const human=(value:string)=>value.replaceAll('_',' ').replaceAll('-',' ').replace(/(^|\s)\S/g,m=>m.toUpperCase())

export function ServiceOperationsPage(){
  const [allowed,setAllowed]=useState<boolean|null>(null)
  const [data,setData]=useState<ServiceOperationsOverview|null>(null)
  const [error,setError]=useState<string|null>(null)
  const [search,setSearch]=useState('')
  const [clientId,setClientId]=useState('')
  const [portfolioId,setPortfolioId]=useState('')
  const [siteStatus,setSiteStatus]=useState('ACTIVE')

  useEffect(()=>{
    let cancelled=false
    loadServiceReportingAccess().then(async isAdmin=>{
      if(cancelled) return
      setAllowed(isAdmin)
      if(!isAdmin) return
      const overview=await loadServiceOperationsOverview()
      if(!cancelled) setData(overview)
    }).catch(err=>{
      if(!cancelled){ setAllowed(false); setError(err instanceof Error?err.message:'Unable to load service operations') }
    })
    return()=>{cancelled=true}
  },[])

  const clientById=useMemo(()=>new Map(data?.clients.map(row=>[row.client_id,row])??[]),[data?.clients])
  const portfolioById=useMemo(()=>new Map(data?.portfolios.map(row=>[row.portfolio_id,row])??[]),[data?.portfolios])

  const nextVisitBySite=useMemo(()=>{
    const map=new Map<string,string>()
    const now=Date.now()
    ;(data?.visits??[]).filter(v=>v.scheduled_for&&new Date(v.scheduled_for).getTime()>=now&&v.status!=='cancelled')
      .sort((a,b)=>new Date(a.scheduled_for||0).getTime()-new Date(b.scheduled_for||0).getTime())
      .forEach(v=>{if(!map.has(v.service_site_id)&&v.scheduled_for) map.set(v.service_site_id,v.scheduled_for)})
    return map
  },[data?.visits])

  const lastVisitBySite=useMemo(()=>{
    const map=new Map<string,string>()
    ;(data?.visits??[]).filter(v=>v.completed_at)
      .sort((a,b)=>new Date(b.completed_at||0).getTime()-new Date(a.completed_at||0).getTime())
      .forEach(v=>{if(!map.has(v.service_site_id)&&v.completed_at) map.set(v.service_site_id,v.completed_at)})
    return map
  },[data?.visits])

  const openActionsBySite=useMemo(()=>{
    const map=new Map<string,number>()
    ;(data?.actions??[]).filter(a=>a.status==='open'||a.status==='in-progress').forEach(a=>map.set(a.service_site_id,(map.get(a.service_site_id)||0)+1))
    return map
  },[data?.actions])

  const docsBySite=useMemo(()=>{
    const map=new Map<string,number>()
    ;(data?.documents??[]).forEach(d=>map.set(d.service_site_id,(map.get(d.service_site_id)||0)+1))
    return map
  },[data?.documents])

  const reportsBySite=useMemo(()=>{
    const map=new Map<string,number>()
    ;(data?.reports??[]).forEach(r=>map.set(r.service_site_id,(map.get(r.service_site_id)||0)+1))
    return map
  },[data?.reports])

  const portfolios=useMemo(()=>data?.portfolios.filter(p=>!clientId||p.client_id===clientId)??[],[data?.portfolios,clientId])

  const filteredSites=useMemo(()=>{
    if(!data) return []
    const needle=search.trim().toLowerCase()
    return data.sites.filter(site=>{
      if(clientId&&site.client_id!==clientId) return false
      if(portfolioId&&site.portfolio_id!==portfolioId) return false
      if(siteStatus!=='ALL'&&site.status.toUpperCase()!==siteStatus) return false
      if(!needle) return true
      const client=site.client_id?clientById.get(site.client_id):undefined
      const portfolio=site.portfolio_id?portfolioById.get(site.portfolio_id):undefined
      return [site.display_name,site.address,site.system_id,client?.name,portfolio?.name].some(v=>String(v||'').toLowerCase().includes(needle))
    }).sort((a,b)=>{
      const an=nextVisitBySite.get(a.service_site_id)
      const bn=nextVisitBySite.get(b.service_site_id)
      if(an&&bn) return an.localeCompare(bn)
      if(an) return -1
      if(bn) return 1
      return (a.display_name||a.address||a.system_id).localeCompare(b.display_name||b.address||b.system_id)
    })
  },[data,search,clientId,portfolioId,siteStatus,clientById,portfolioById,nextVisitBySite])

  if(allowed===null) return <section className="product-page service-operations-page"><div className="reference-empty-state"><strong>Loading private service operations…</strong></div></section>
  if(!allowed) return <section className="product-page service-operations-page"><div className="reference-empty-state"><strong>Admin service access required.</strong><span>This workspace contains private client, visit and service-reporting records.</span>{error&&<span>{error}</span>}</div></section>
  if(!data) return <section className="product-page service-operations-page"><div className="reference-empty-state"><strong>Loading service portfolio data…</strong></div></section>

  const now=Date.now()
  const sevenDays=now+7*86400000
  const upcoming=data.visits.filter(v=>v.scheduled_for&&['scheduled','in-progress'].includes(v.status)&&new Date(v.scheduled_for).getTime()>=now&&new Date(v.scheduled_for).getTime()<=sevenDays)
  const overdueActions=data.actions.filter(a=>['open','in-progress'].includes(a.status)&&a.due_date&&new Date(a.due_date+'T23:59:59').getTime()<now)
  const attentionReadings=data.measurements.filter(m=>m.result_status==='attention'||m.result_status==='action')
  const readyReports=data.reports.filter(r=>r.status==='ready')
  const pendingDocs=data.documents.filter(d=>d.extraction_status==='pending'||d.extraction_status==='failed')

  return <section className="product-page service-operations-page">
    <div className="product-page-heading compact-heading">
      <div>
        <span className="page-kicker">Admin only · field service operations</span>
        <h1>Service operations</h1>
        <p>Portfolio-scale scheduling, corrective actions and reporting layered onto exact TowerSignal system IDs.</p>
      </div>
      <div className="page-actions"><a className="secondary-link-button" href="#/companies">Company CRM</a><a className="secondary-link-button" href="#/portfolios">Public portfolios</a></div>
    </div>

    <div className="service-ops-metrics">
      <article><small>Tracked sites</small><strong>{number.format(data.sites.length)}</strong><span>{number.format(data.clients.length)} clients · {number.format(data.portfolios.length)} portfolios</span></article>
      <article><small>Visits next 7 days</small><strong>{number.format(upcoming.length)}</strong><span>{number.format(data.visits.filter(v=>v.status==='in-progress').length)} currently in progress</span></article>
      <article><small>Overdue actions</small><strong>{number.format(overdueActions.length)}</strong><span>{number.format(data.actions.filter(a=>a.status==='open'||a.status==='in-progress').length)} open total</span></article>
      <article><small>Attention readings</small><strong>{number.format(attentionReadings.length)}</strong><span>Measurements marked attention/action</span></article>
      <article><small>Reports ready</small><strong>{number.format(readyReports.length)}</strong><span>{number.format(data.reports.filter(r=>r.status==='finalized').length)} finalized</span></article>
      <article><small>Document intake</small><strong>{number.format(data.documents.length)}</strong><span>{number.format(pendingDocs.length)} pending/failed extraction</span></article>
    </div>

    <div className="service-ops-filters">
      <input aria-label="Service site search" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search site, system ID, client or portfolio…" />
      <select aria-label="Service client filter" value={clientId} onChange={e=>{setClientId(e.target.value);setPortfolioId('')}}><option value="">All clients</option>{data.clients.map(c=><option key={c.client_id} value={c.client_id}>{c.name}</option>)}</select>
      <select aria-label="Service portfolio filter" value={portfolioId} onChange={e=>setPortfolioId(e.target.value)}><option value="">All portfolios</option>{portfolios.map(p=><option key={p.portfolio_id} value={p.portfolio_id}>{p.name}</option>)}</select>
      <select aria-label="Service site status filter" value={siteStatus} onChange={e=>setSiteStatus(e.target.value)}><option value="ALL">All statuses</option><option value="ACTIVE">Active</option><option value="PROSPECT">Prospect</option><option value="INACTIVE">Inactive</option></select>
    </div>

    {filteredSites.length===0?<div className="reference-empty-state"><strong>No service sites match these filters.</strong><span>Enable service tracking from an Account page to add a site.</span></div>:<div className="table-card account-table-card service-ops-table-card"><div className="table-scroll"><table className="account-table service-ops-table"><thead><tr><th>Site</th><th>Client / portfolio</th><th>Next visit</th><th>Last completed</th><th>Open actions</th><th>Reports / documents</th><th></th></tr></thead><tbody>
      {filteredSites.map(site=>{
        const client=site.client_id?clientById.get(site.client_id):undefined
        const portfolio=site.portfolio_id?portfolioById.get(site.portfolio_id):undefined
        const next=nextVisitBySite.get(site.service_site_id)
        const last=lastVisitBySite.get(site.service_site_id)
        return <tr key={site.service_site_id}>
          <td><strong>{site.display_name||site.address||site.system_id}</strong><small>System {site.system_id} · {human(site.status)}</small></td>
          <td><strong>{client?.name||'Unassigned client'}</strong><small>{portfolio?.name||'No portfolio'}</small></td>
          <td>{next?<><strong>{new Date(next).toLocaleDateString()}</strong><small>{new Date(next).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</small></>:'—'}</td>
          <td>{last?new Date(last).toLocaleDateString():'—'}</td>
          <td><strong>{openActionsBySite.get(site.service_site_id)||0}</strong></td>
          <td><strong>{reportsBySite.get(site.service_site_id)||0} reports</strong><small>{docsBySite.get(site.service_site_id)||0} documents</small></td>
          <td className="row-arrow"><a href={`#/account/${encodeURIComponent(site.system_id)}`} aria-label={`Open account ${site.system_id}`}>›</a></td>
        </tr>
      })}
    </tbody></table></div></div>}

    {(upcoming.length>0||overdueActions.length>0)&&<div className="service-ops-lower-grid">
      <section className="service-ops-card"><div className="service-ops-card-heading"><strong>Upcoming visits</strong><span>Next 7 days</span></div>{upcoming.sort((a,b)=>(a.scheduled_for||'').localeCompare(b.scheduled_for||'')).slice(0,20).map(v=>{const site=data.sites.find(s=>s.service_site_id===v.service_site_id);return <article key={v.visit_id}><a href={site?`#/account/${encodeURIComponent(site.system_id)}`:'#/service'}>{site?.display_name||site?.address||site?.system_id||v.service_site_id}</a><strong>{v.scheduled_for?new Date(v.scheduled_for).toLocaleString():'Unscheduled'}</strong><span>{v.technician_name||'Technician unassigned'} · {human(v.status)}</span></article>})}</section>
      <section className="service-ops-card"><div className="service-ops-card-heading"><strong>Overdue corrective actions</strong><span>{overdueActions.length}</span></div>{overdueActions.sort((a,b)=>(a.due_date||'').localeCompare(b.due_date||'')).slice(0,20).map(a=>{const site=data.sites.find(s=>s.service_site_id===a.service_site_id);return <article key={a.action_id}><a href={site?`#/account/${encodeURIComponent(site.system_id)}`:'#/service'}>{a.title}</a><strong>{a.due_date||'No due date'}</strong><span>{site?.display_name||site?.address||site?.system_id||a.service_site_id} · {human(a.severity)}</span></article>})}</section>
    </div>}
  </section>
}
