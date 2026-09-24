import { useEffect, useMemo, useState } from 'react'
import {
  addServiceAction,
  addServiceAgreement,
  addServiceAsset,
  addServiceDocument,
  addServiceMeasurement,
  addServiceVisit,
  createServiceClient,
  createServicePortfolio,
  ensureServiceReport,
  ensureServiceSite,
  loadServiceReportingAccess,
  loadServiceWorkspace,
  updateServiceSiteOrganization,
  updateServiceVisit,
} from '../serviceReporting/client'
import type {
  ServiceActionSeverity,
  ServiceAsset,
  ServiceDocumentType,
  ServiceMeasurementStatus,
  ServiceWorkspace,
} from '../types/serviceReporting'

const assetTypes: ServiceAsset['asset_type'][] = [
  'cooling_tower','controller','pump','chemical_feed','heat_exchanger','domestic_water_tank','sensor','other',
]
const documentTypes: ServiceDocumentType[] = [
  'visit-report','photo','lab-result','water-management-plan','contract','schematic','sds','invoice','other',
]
const measurementStatuses: ServiceMeasurementStatus[] = ['normal','attention','action']
const severities: ServiceActionSeverity[] = ['low','medium','high','critical']
const human = (value: string) => value.replaceAll('_',' ').replaceAll('-',' ').replace(/(^|\s)\S/g, m => m.toUpperCase())
const dateTimeLocal = () => {
  const d=new Date(Date.now()+3600000)
  return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16)
}

export function ServiceReportingPanel({
  systemId,
  address,
}: {
  systemId: string
  address: string | null
}) {
  const [allowed,setAllowed]=useState(false)
  const [workspace,setWorkspace]=useState<ServiceWorkspace | null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState<string | null>(null)

  const [clientId,setClientId]=useState('')
  const [portfolioId,setPortfolioId]=useState('')
  const [newClient,setNewClient]=useState('')
  const [newPortfolio,setNewPortfolio]=useState('')

  const [assetType,setAssetType]=useState<ServiceAsset['asset_type']>('cooling_tower')
  const [assetLabel,setAssetLabel]=useState('')
  const [agreementName,setAgreementName]=useState('')
  const [agreementInterval,setAgreementInterval]=useState('30')

  const [visitDate,setVisitDate]=useState(dateTimeLocal())
  const [technician,setTechnician]=useState('')
  const [selectedVisitId,setSelectedVisitId]=useState('')

  const [measurementParameter,setMeasurementParameter]=useState('')
  const [measurementValue,setMeasurementValue]=useState('')
  const [measurementUnit,setMeasurementUnit]=useState('')
  const [measurementStatus,setMeasurementStatus]=useState<ServiceMeasurementStatus>('normal')

  const [actionTitle,setActionTitle]=useState('')
  const [actionSeverity,setActionSeverity]=useState<ServiceActionSeverity>('medium')
  const [actionDue,setActionDue]=useState('')

  const [documentName,setDocumentName]=useState('')
  const [documentType,setDocumentType]=useState<ServiceDocumentType>('other')
  const [documentUrl,setDocumentUrl]=useState('')

  const refresh=async()=>{
    const next=await loadServiceWorkspace(systemId)
    setWorkspace(next)
    if(next.site){
      setClientId(next.site.client_id ?? '')
      setPortfolioId(next.site.portfolio_id ?? '')
    }
    setSelectedVisitId(current => current && next.visits.some(v=>v.visit_id===current) ? current : (next.visits[0]?.visit_id ?? ''))
  }

  useEffect(()=>{
    let cancelled=false
    loadServiceReportingAccess().then(async isAdmin=>{
      if(cancelled || !isAdmin) return
      const next=await loadServiceWorkspace(systemId)
      if(cancelled) return
      setAllowed(true)
      setWorkspace(next)
      if(next.site){
        setClientId(next.site.client_id ?? '')
        setPortfolioId(next.site.portfolio_id ?? '')
      }
      setSelectedVisitId(next.visits[0]?.visit_id ?? '')
    }).catch(()=>{ if(!cancelled) setAllowed(false) })
    return()=>{cancelled=true}
  },[systemId])

  const run=async(task:()=>Promise<void>)=>{
    setBusy(true); setError(null)
    try{ await task(); await refresh() }
    catch(err){ setError(err instanceof Error ? err.message : 'Service reporting operation failed') }
    finally{ setBusy(false) }
  }

  const portfolios=useMemo(()=>workspace?.portfolios.filter(p=>!clientId || p.client_id===clientId) ?? [],[workspace?.portfolios,clientId])
  const selectedVisit=workspace?.visits.find(v=>v.visit_id===selectedVisitId) ?? null
  const selectedMeasurements=workspace?.measurements.filter(m=>m.visit_id===selectedVisitId) ?? []
  const selectedActions=workspace?.actions.filter(a=>a.visit_id===selectedVisitId) ?? []
  const selectedDocuments=workspace?.documents.filter(d=>d.visit_id===selectedVisitId) ?? []
  const openActions=workspace?.actions.filter(a=>['open','in-progress'].includes(a.status)).length ?? 0

  if(!allowed) return null

  if(!workspace?.site){
    return <section className="service-reporting-panel">
      <div className="service-reporting-heading">
        <div>
          <span className="page-kicker">Admin only · service reporting add-on</span>
          <h3>Service operations</h3>
          <p>Track the private service relationship for this exact TowerSignal system without altering public regulatory evidence.</p>
        </div>
        <button disabled={busy} onClick={()=>void run(async()=>{ await ensureServiceSite(systemId,address) })}>{busy?'Enabling…':'Enable service tracking'}</button>
      </div>
      {error && <div className="company-admin-error">{error}</div>}
    </section>
  }

  const site=workspace.site
  return <section className="service-reporting-panel" aria-label="Private service reporting workspace">
    <div className="service-reporting-heading">
      <div>
        <span className="page-kicker">Admin only · service reporting add-on</span>
        <h3>Service operations</h3>
        <p>Private operational records for System {systemId}. Public TowerSignal evidence remains read-only and separately sourced.</p>
      </div>
      <div className="service-reporting-heading-actions">
        <a className="secondary-link-button" href="#/service">Portfolio dashboard</a>
        <span className="service-site-status">{human(site.status)}</span>
      </div>
    </div>
    {error && <div className="company-admin-error">{error}</div>}

    <div className="service-reporting-metrics">
      <article><small>Assets</small><strong>{workspace.assets.length}</strong></article>
      <article><small>Agreements</small><strong>{workspace.agreements.length}</strong></article>
      <article><small>Visits</small><strong>{workspace.visits.length}</strong></article>
      <article><small>Open actions</small><strong>{openActions}</strong></article>
      <article><small>Documents</small><strong>{workspace.documents.length}</strong></article>
      <article><small>Reports</small><strong>{workspace.reports.length}</strong></article>
    </div>

    <div className="service-reporting-grid">
      <section className="service-reporting-card">
        <div className="service-card-heading"><strong>Client &amp; portfolio</strong><span>Private organizational ownership</span></div>
        <div className="service-form-grid">
          <label><span>Client</span><select value={clientId} onChange={e=>{setClientId(e.target.value);setPortfolioId('')}}><option value="">Unassigned</option>{workspace.clients.map(c=><option key={c.client_id} value={c.client_id}>{c.name}</option>)}</select></label>
          <label><span>Portfolio</span><select value={portfolioId} onChange={e=>setPortfolioId(e.target.value)}><option value="">Unassigned</option>{portfolios.map(p=><option key={p.portfolio_id} value={p.portfolio_id}>{p.name}</option>)}</select></label>
          <button disabled={busy} onClick={()=>void run(async()=>{await updateServiceSiteOrganization(site.service_site_id,clientId||null,portfolioId||null)})}>Save assignment</button>
        </div>
        <div className="service-inline-form">
          <input aria-label="New service client" value={newClient} onChange={e=>setNewClient(e.target.value)} placeholder="New client name" />
          <button disabled={busy||!newClient.trim()} onClick={()=>void run(async()=>{const c=await createServiceClient(newClient.trim());setNewClient('');setClientId(c.client_id)})}>Add client</button>
        </div>
        <div className="service-inline-form">
          <input aria-label="New service portfolio" value={newPortfolio} onChange={e=>setNewPortfolio(e.target.value)} placeholder="New portfolio name" />
          <button disabled={busy||!clientId||!newPortfolio.trim()} onClick={()=>void run(async()=>{const p=await createServicePortfolio(clientId,newPortfolio.trim());setNewPortfolio('');setPortfolioId(p.portfolio_id)})}>Add portfolio</button>
        </div>
      </section>

      <section className="service-reporting-card">
        <div className="service-card-heading"><strong>Assets</strong><span>{workspace.assets.length} tracked</span></div>
        <div className="service-inline-form">
          <select aria-label="Asset type" value={assetType} onChange={e=>setAssetType(e.target.value as ServiceAsset['asset_type'])}>{assetTypes.map(v=><option key={v} value={v}>{human(v)}</option>)}</select>
          <input aria-label="Asset label" value={assetLabel} onChange={e=>setAssetLabel(e.target.value)} placeholder="Tower 1, Controller A…" />
          <button disabled={busy||!assetLabel.trim()} onClick={()=>void run(async()=>{await addServiceAsset(site.service_site_id,assetType,assetLabel.trim());setAssetLabel('')})}>Add asset</button>
        </div>
        <div className="service-chip-list">{workspace.assets.map(a=><span key={a.asset_id}><strong>{a.asset_label}</strong> · {human(a.asset_type)}</span>)}</div>
      </section>

      <section className="service-reporting-card">
        <div className="service-card-heading"><strong>Service agreements</strong><span>{workspace.agreements.filter(a=>a.status==='active').length} active</span></div>
        <div className="service-inline-form">
          <input aria-label="Agreement name" value={agreementName} onChange={e=>setAgreementName(e.target.value)} placeholder="Monthly water treatment" />
          <input aria-label="Agreement interval" type="number" min="1" value={agreementInterval} onChange={e=>setAgreementInterval(e.target.value)} placeholder="Days" />
          <button disabled={busy||!agreementName.trim()} onClick={()=>void run(async()=>{await addServiceAgreement(site.service_site_id,agreementName.trim(),agreementInterval?Number(agreementInterval):null);setAgreementName('')})}>Add agreement</button>
        </div>
        <div className="service-list">{workspace.agreements.map(a=><article key={a.agreement_id}><strong>{a.agreement_name}</strong><span>{human(a.status)}{a.service_interval_days? ` · every ${a.service_interval_days} days`:''}</span></article>)}</div>
      </section>

      <section className="service-reporting-card service-visits-card">
        <div className="service-card-heading"><strong>Visits</strong><span>Schedule → field record → report</span></div>
        <div className="service-inline-form">
          <input aria-label="Visit date" type="datetime-local" value={visitDate} onChange={e=>setVisitDate(e.target.value)} />
          <input aria-label="Technician" value={technician} onChange={e=>setTechnician(e.target.value)} placeholder="Technician" />
          <button disabled={busy||!visitDate} onClick={()=>void run(async()=>{const iso=new Date(visitDate).toISOString();const v=await addServiceVisit(site.service_site_id,iso,technician.trim()||null);setSelectedVisitId(v.visit_id)})}>Schedule visit</button>
        </div>
        <div className="service-visit-list">{workspace.visits.map(v=><article key={v.visit_id} className={v.visit_id===selectedVisitId?'selected':''}>
          <button onClick={()=>setSelectedVisitId(v.visit_id)}>
            <strong>{v.scheduled_for?new Date(v.scheduled_for).toLocaleString():'Unscheduled visit'}</strong>
            <span>{human(v.status)} · {v.technician_name||'Technician unassigned'}</span>
          </button>
          <div>
            {v.status==='scheduled' && <button disabled={busy} onClick={()=>void run(async()=>{await updateServiceVisit(v.visit_id,{status:'in-progress',started_at:new Date().toISOString()})})}>Start</button>}
            {v.status==='in-progress' && <button disabled={busy} onClick={()=>void run(async()=>{await updateServiceVisit(v.visit_id,{status:'completed',completed_at:new Date().toISOString(),report_status:'ready'})})}>Complete</button>}
            <button disabled={busy} onClick={()=>void run(async()=>{await ensureServiceReport(site.service_site_id,v.visit_id,`Service Visit · ${address||systemId}`)})}>Draft report</button>
          </div>
        </article>)}</div>
      </section>
    </div>

    {selectedVisit && <section className="service-reporting-card service-selected-visit">
      <div className="service-card-heading">
        <div><strong>Selected visit</strong><span>{selectedVisit.scheduled_for?new Date(selectedVisit.scheduled_for).toLocaleString():selectedVisit.visit_id}</span></div>
        <span>{human(selectedVisit.status)} · report {human(selectedVisit.report_status)}</span>
      </div>

      <div className="service-entry-grid">
        <div>
          <h4>Measurements</h4>
          <div className="service-inline-form">
            <input aria-label="Measurement parameter" value={measurementParameter} onChange={e=>setMeasurementParameter(e.target.value)} placeholder="pH, conductivity, inhibitor…" />
            <input aria-label="Measurement value" value={measurementValue} onChange={e=>setMeasurementValue(e.target.value)} placeholder="Value" />
            <input aria-label="Measurement unit" value={measurementUnit} onChange={e=>setMeasurementUnit(e.target.value)} placeholder="Unit" />
            <select aria-label="Measurement status" value={measurementStatus} onChange={e=>setMeasurementStatus(e.target.value as ServiceMeasurementStatus)}>{measurementStatuses.map(v=><option key={v} value={v}>{human(v)}</option>)}</select>
            <button disabled={busy||!measurementParameter.trim()||!measurementValue.trim()} onClick={()=>void run(async()=>{await addServiceMeasurement(site.service_site_id,selectedVisit.visit_id,measurementParameter.trim(),measurementValue.trim(),measurementUnit.trim()||null,measurementStatus);setMeasurementParameter('');setMeasurementValue('');setMeasurementUnit('')})}>Add reading</button>
          </div>
          <div className="service-list">{selectedMeasurements.map(m=><article key={m.measurement_id}><strong>{m.parameter}</strong><span>{m.value_numeric??m.value_text} {m.unit||''} · {human(m.result_status)}</span></article>)}</div>
        </div>

        <div>
          <h4>Corrective actions</h4>
          <div className="service-inline-form">
            <input aria-label="Action title" value={actionTitle} onChange={e=>setActionTitle(e.target.value)} placeholder="Action required" />
            <select aria-label="Action severity" value={actionSeverity} onChange={e=>setActionSeverity(e.target.value as ServiceActionSeverity)}>{severities.map(v=><option key={v} value={v}>{human(v)}</option>)}</select>
            <input aria-label="Action due" type="date" value={actionDue} onChange={e=>setActionDue(e.target.value)} />
            <button disabled={busy||!actionTitle.trim()} onClick={()=>void run(async()=>{await addServiceAction(site.service_site_id,selectedVisit.visit_id,actionTitle.trim(),actionSeverity,actionDue||null);setActionTitle('');setActionDue('')})}>Add action</button>
          </div>
          <div className="service-list">{selectedActions.map(a=><article key={a.action_id}><strong>{a.title}</strong><span>{human(a.severity)} · {human(a.status)}{a.due_date?` · due ${a.due_date}`:''}</span></article>)}</div>
        </div>

        <div>
          <h4>Documents &amp; photos</h4>
          <div className="service-inline-form">
            <input aria-label="Document name" value={documentName} onChange={e=>setDocumentName(e.target.value)} placeholder="File / photo name" />
            <select aria-label="Document type" value={documentType} onChange={e=>setDocumentType(e.target.value as ServiceDocumentType)}>{documentTypes.map(v=><option key={v} value={v}>{human(v)}</option>)}</select>
            <input aria-label="Document URL" type="url" value={documentUrl} onChange={e=>setDocumentUrl(e.target.value)} placeholder="Private storage URL (optional)" />
            <button disabled={busy||!documentName.trim()} onClick={()=>void run(async()=>{await addServiceDocument(site.service_site_id,selectedVisit.visit_id,documentName.trim(),documentType,documentUrl.trim()||null);setDocumentName('');setDocumentUrl('')})}>Register document</button>
          </div>
          <p className="microcopy">This foundation stores private document/photo metadata and extraction state. Binary upload and secure object storage are the next storage phase; do not place private files in the public Pages repository.</p>
          <div className="service-list">{selectedDocuments.map(d=><article key={d.document_id}><strong>{d.file_name}</strong><span>{human(d.document_type)} · extraction {human(d.extraction_status)}</span>{d.storage_url&&<a href={d.storage_url} target="_blank" rel="noreferrer">Open private file ↗</a>}</article>)}</div>
        </div>
      </div>
    </section>}
  </section>
}
