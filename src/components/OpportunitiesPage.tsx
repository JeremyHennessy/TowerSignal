import { useMemo, useState } from 'react'
import type { SystemSummary, SystemsPayload } from '../types/data'
import type { AcrisSummaryFields } from '../types/acris'
import type { ProcurementBundle, ProcurementRecord } from '../types/procurement'
import { formatDate } from '../domain/labels'
import { ShareButton } from './ShareButton'

const number = new Intl.NumberFormat('en-US')
const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

function signalLabel(value: string): string {
  const labels: Record<string, string> = {
    CONFIRMED_RECENT_VIOLATION: 'Confirmed violation',
    POTENTIAL_SAMPLING_GAP: 'Sampling follow-up',
    NO_PUBLIC_SAMPLE_DATE: 'No public sample date',
    MULTIPLE_ACTIVE_EQUIPMENT: 'Multiple equipment',
    RECENT_NYC_HEALTH_INSPECTION: 'Recent inspection',
    NO_CURRENT_SIGNAL: 'No current timing signal',
  }
  return labels[value] ?? value.replaceAll('_', ' ').toLowerCase()
}

function procurementDate(row: ProcurementRecord): string | null {
  return row.due_date ?? row.award_date ?? row.start_date ?? row.notice_start_date ?? row.retrieved_at ?? null
}

function procurementAmount(row: ProcurementRecord): number | null {
  return row.current_amount ?? row.amount ?? row.original_amount ?? null
}

function sourceLabel(row: ProcurementRecord): string {
  if (row.source === 'NYC_CITY_RECORD') return row.scope === 'OPEN_SOLICITATIONS' ? 'City Record · Solicitation' : 'City Record · Award'
  if (row.source === 'NYC_CHECKBOOK_EDC') return 'Checkbook · NYCEDC'
  return row.vendor_role === 'SUBCONTRACTOR' ? 'Checkbook · Subcontract' : 'Checkbook · Contract'
}

function categoryLabel(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, match => match.toUpperCase())
}

export function OpportunitiesPage({ payload, procurement, onOpenAccount }: {
  payload: SystemsPayload
  procurement: ProcurementBundle
  onOpenAccount: (row: SystemSummary) => void
}) {
  const [sourceFilter, setSourceFilter] = useState('ALL')
  const [categoryFilter, setCategoryFilter] = useState('ALL')
  const rows = payload.systems
  const highPriority = rows.filter(row => row.priority_score >= 70)
  const sampleFollowUp = rows.filter(row => row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE'))
  const contactReady = rows.filter(row => (row.hpd_contact_count ?? 0) > 0)
  const recentDob = rows.filter(row => (row.dob_recent_activity_count ?? 0) > 0)
  const ranked = [...rows]
    .filter(row => row.priority_score >= 50 || (row.dob_recent_activity_count ?? 0) > 0 || (row.hpd_contact_count ?? 0) > 0)
    .sort((a, b) => b.priority_score - a.priority_score || (b.dob_recent_activity_count ?? 0) - (a.dob_recent_activity_count ?? 0))
    .slice(0, 50)

  const procurementRows = useMemo(() => [
    ...procurement.cityRecord.notices,
    ...procurement.checkbook.contracts,
  ].sort((a, b) => (procurementDate(b) ?? '').localeCompare(procurementDate(a) ?? '')), [procurement])

  const categories = useMemo(() => [...new Set(procurementRows.map(row => row.service_category))].sort(), [procurementRows])
  const filteredProcurement = useMemo(() => procurementRows.filter(row => {
    if (sourceFilter === 'CITY_RECORD' && row.source !== 'NYC_CITY_RECORD') return false
    if (sourceFilter === 'CHECKBOOK' && row.source === 'NYC_CITY_RECORD') return false
    if (categoryFilter !== 'ALL' && row.service_category !== categoryFilter) return false
    return true
  }).slice(0, 100), [procurementRows, sourceFilter, categoryFilter])

  const observedContractValue = procurement.checkbook.contracts.reduce((sum, row) => sum + (row.current_amount ?? 0), 0)
  const unresolved = procurementRows.filter(row => row.vendor_raw && !row.company_id).length

  return <section className="product-page opportunities-page">
    <div className="product-page-heading">
      <div><span className="page-kicker">New York City · procurement + commercial timing</span><h1>Opportunities workspace</h1><p>Review live public procurement alongside TowerSignal account timing. Procurement values are source-reported public observations, not vendor revenue, and records are not attached to cooling-tower accounts without a defensible facility/property link.</p></div>
      <div className="page-actions"><ShareButton label="Share this view" /></div>
    </div>

    <div className="reference-metric-grid">
      <article><span className="reference-metric-icon urgent">↗</span><div><small>Open solicitations</small><strong>{number.format(procurement.cityRecord.summary.open_relevant_opportunities)}</strong><span>Relevant City Record notices</span></div></article>
      <article><span className="reference-metric-icon warning">◷</span><div><small>Recent awards</small><strong>{number.format(procurement.cityRecord.summary.recent_relevant_awards)}</strong><span>City Record lookback window</span></div></article>
      <article><span className="reference-metric-icon success">◎</span><div><small>Verified contracts</small><strong>{number.format(procurement.checkbook.summary.relevant_contract_count)}</strong><span>Relevant Checkbook records</span></div></article>
      <article><span className="reference-metric-icon">$</span><div><small>Observed contract value</small><strong>{currency.format(observedContractValue)}</strong><span>Checkbook current amounts · not revenue</span></div></article>
      <article><span className="reference-metric-icon">?</span><div><small>Unresolved vendors</small><strong>{number.format(unresolved)}</strong><span>Preserved for company resolution</span></div></article>
    </div>

    <div className="roadmap-data-banner">
      <div><span className="roadmap-status">LIVE SOURCE DATA</span><strong>City Record + verified Checkbook NYC are connected.</strong><p>City Record is fetched and validated during the product build. Checkbook is published only from its independently verified durable cache. Exact source IDs, classifications, confidence and source links remain available for review.</p></div>
      <div className="roadmap-source-list"><span>City Record · {procurement.cityRecord.source_health.status}</span><span>Checkbook · verified {formatDate(procurement.checkbook.generated_at)}</span><span>No inferred property linkage</span></div>
    </div>

    <div className="reference-table-card">
      <div className="reference-table-heading">
        <div><strong>Public procurement intelligence</strong><span>{number.format(filteredProcurement.length)} shown · {number.format(procurementRows.length)} relevant source-backed records loaded</span></div>
        <div className="page-actions">
          <label>Source <select aria-label="Procurement source" value={sourceFilter} onChange={event => setSourceFilter(event.target.value)}><option value="ALL">All</option><option value="CITY_RECORD">City Record</option><option value="CHECKBOOK">Checkbook NYC</option></select></label>
          <label>Service <select aria-label="Procurement service category" value={categoryFilter} onChange={event => setCategoryFilter(event.target.value)}><option value="ALL">All services</option>{categories.map(category => <option key={category} value={category}>{categoryLabel(category)}</option>)}</select></label>
        </div>
      </div>
      <div className="reference-table-scroll"><table className="reference-table procurement-table"><thead><tr><th>Procurement</th><th>Source</th><th>Agency / buyer</th><th>Vendor</th><th>Service</th><th>Observed value</th><th>Date</th><th>Evidence</th></tr></thead><tbody>{filteredProcurement.map(row => <tr key={row.procurement_id}>
        <td><strong>{row.title ?? row.description ?? row.source_record_id}</strong><small>{row.source_contract_id ?? row.notice_id ?? row.source_record_id}</small></td>
        <td><strong>{sourceLabel(row)}</strong><small>{row.status ?? 'source record'}</small></td>
        <td>{row.agency ?? row.buyer_name ?? '—'}</td>
        <td>{row.vendor_raw ? <><strong>{row.vendor_raw}</strong><small>{row.company_match_confidence ?? 'UNRESOLVED'}</small></> : <span className="muted-label">Not yet awarded / not published</span>}</td>
        <td><strong>{categoryLabel(row.service_category)}</strong><small>{row.service_confidence}</small></td>
        <td>{procurementAmount(row) == null ? '—' : currency.format(procurementAmount(row) ?? 0)}<small>{row.observed_value_evidence ?? row.amount_evidence ?? 'No amount published'}</small></td>
        <td>{procurementDate(row) ? formatDate(procurementDate(row) ?? '') : '—'}<small>{row.due_date ? 'due date' : row.start_date ? 'contract start' : 'source date'}</small></td>
        <td>{row.source_url ? <a className="table-link" href={row.source_url} target="_blank" rel="noreferrer">Open source ↗</a> : '—'}<small>{row.facility_match_confidence ?? row.tower_link_confidence ?? 'UNLINKED'} facility/account</small></td>
      </tr>)}</tbody></table></div>
    </div>

    <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>Current account timing opportunities</strong><span>{number.format(ranked.length)} highest-ranked accounts shown separately from procurement evidence</span></div></div>
      <div className="reference-table-scroll"><table className="reference-table opportunity-table"><thead><tr><th>Account</th><th>Priority</th><th>Strongest reason</th><th>Equipment</th><th>Contact</th><th>DOB activity</th><th>OATH</th><th>Recorded property activity</th><th>Action</th></tr></thead><tbody>{ranked.map(row => {
        const acris = row as SystemSummary & AcrisSummaryFields
        return <tr key={row.system_id} onClick={() => onOpenAccount(row)}>
          <td><strong>{row.address ?? row.system_id}</strong><small>{[row.borough, row.zip].filter(Boolean).join(' · ')} · {row.system_id}</small></td>
          <td><span className={`priority-pill ${row.priority_score >= 70 ? 'priority-pill-high' : 'priority-pill-medium'}`}>{row.priority_score}</span></td>
          <td><strong>{signalLabel(row.primary_signal)}</strong><small>{row.evidence_confidence}</small></td>
          <td>{row.active_equipment}<small>active</small></td>
          <td>{(row.hpd_contact_count ?? 0) > 0 ? <span className="ready-label">Contact-ready</span> : <span className="muted-label">No HPD contact</span>}</td>
          <td>{row.dob_recent_activity_count ?? 0}<small>{row.latest_dob_activity_date ? `latest ${formatDate(row.latest_dob_activity_date)}` : 'no recent activity'}</small></td>
          <td>{row.oath_case_count ?? 0}<small>{(row.oath_case_count ?? 0) > 0 ? 'exact case match' : 'none matched'}</small></td>
          <td>{acris.acris_recent_document_count ?? 0}<small>recent exact-BBL docs</small></td>
          <td><button className="table-link" onClick={event => { event.stopPropagation(); onOpenAccount(row) }}>Open profile →</button></td>
        </tr>
      })}</tbody></table></div>
    </div>

    <div className="source-health-footnote">Priority remains WHY NOW for cooling-tower accounts. Procurement classifications and observed contract values are separate source-backed commercial evidence and do not change Priority Score 1.0.</div>
  </section>
}
