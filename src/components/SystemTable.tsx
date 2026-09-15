import { useEffect, useMemo, useState } from 'react'
import type { SystemSummary } from '../types/data'
import type { AcrisSummaryFields } from '../types/acris'
import type { LegionellaAlertPayload, PropertyEnforcementSummaryFields } from '../types/enforcement'
import { formatDate, signalLabel } from '../domain/labels'
import { StatusBadge } from './StatusBadge'

const PAGE_SIZE = 50

type SortKey = 'priority_score' | 'address' | 'active_equipment' | 'days_since_latest_sample' | 'latest_inspection_date' | 'oath_case_count'
type EnrichedSystemSummary = SystemSummary & AcrisSummaryFields & PropertyEnforcementSummaryFields

function priorityBand(score: number): string {
  if (score >= 70) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
}

export function SystemTable({ rows, onSelect }: { rows: SystemSummary[]; onSelect: (row: SystemSummary) => void }) {
  const [page, setPage] = useState(0)
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({ key: 'priority_score', dir: 'desc' })
  const [legionella, setLegionella] = useState<LegionellaAlertPayload | null>(null)
  const [legionellaError, setLegionellaError] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    fetch(`${import.meta.env.BASE_URL}data/legionella-alerts.json`, { cache: 'no-store', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const payload = await response.json() as LegionellaAlertPayload
        if (payload?.domain !== 'LEGIONELLA_PUBLIC_HEALTH_ALERTS' || !Array.isArray(payload.items)) throw new Error('Malformed Legionella alert cache')
        setLegionella(payload)
      })
      .catch(error => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setLegionellaError(true)
      })
    return () => controller.abort()
  }, [])

  const sorted = useMemo(() => [...rows].sort((a,b) => {
    const av = a[sort.key] ?? ''; const bv = b[sort.key] ?? ''
    const result = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv))
    return sort.dir === 'asc' ? result : -result
  }), [rows, sort])
  const maxPage = Math.max(0, Math.ceil(sorted.length / PAGE_SIZE) - 1)
  const activePage = Math.min(page, maxPage)
  const visible = sorted.slice(activePage * PAGE_SIZE, activePage * PAGE_SIZE + PAGE_SIZE)
  const changeSort = (key: SortKey) => setSort(current => current.key === key ? { key, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'priority_score' ? 'desc' : 'asc' })
  const latestLegionellaItems = useMemo(() => {
    const items = legionella?.items ?? []
    const dated = items.filter(item => item.published_date)
    return (dated.length ? dated : items).slice(0, 3)
  }, [legionella])

  return <>
    {legionella && <section className="table-card" aria-label="Legionnaires official intelligence">
      <div className="table-heading">
        <div><strong>Legionnaires official intelligence</strong> · {legionella.summary.source_channel_count.toLocaleString()} official channels</div>
        <div>{legionella.summary.discovered_relevant_item_count.toLocaleString()} retained relevant items</div>
      </div>
      <div className="signal-list">
        {latestLegionellaItems.map(item => <article className="signal-card" key={item.item_id}>
          <div className="signal-card-head"><strong>{item.title ?? 'Official Legionella / Legionnaires update'}</strong><span>{item.agency}</span></div>
          <p>{item.published_date ? formatDate(item.published_date) : 'Publication date not published'} · {item.channel_kind.replaceAll('_', ' ').toLowerCase()}</p>
          <a href={item.url} target="_blank" rel="noreferrer">Open official source</a>
        </article>)}
      </div>
      <p className="microcopy">Official NYC and New York State public-health intelligence only. These items are not assigned to a property unless a source publishes a deterministic building identity.</p>
    </section>}
    {legionellaError && <div className="field-pack-alert"><strong>Legionnaires source status:</strong> the optional official-alert cache could not be loaded in this browser session. Account evidence remains available; this is not interpreted as zero alerts.</div>}
    <div className="table-card account-table-card">
      <div className="table-heading"><div><strong>{rows.length.toLocaleString()}</strong> matching systems</div><div>Showing {visible.length ? activePage * PAGE_SIZE + 1 : 0}–{Math.min((activePage + 1) * PAGE_SIZE, rows.length)}</div></div>
      {rows.length === 0 ? <div className="empty-state"><strong>No accounts match these filters.</strong><span>Try widening the territory, timing signal or priority criteria.</span></div> : <div className="table-scroll"><table className="account-table"><thead><tr>
        <th><button onClick={() => changeSort('address')}>Account</button></th><th><button onClick={() => changeSort('priority_score')}>Priority</button></th><th>Timing signal</th><th>Contact</th><th><button onClick={() => changeSort('days_since_latest_sample')}>Sampling</button></th><th><button onClick={() => changeSort('oath_case_count')}>Activity</button></th><th>Evidence</th><th aria-label="Open account" />
      </tr></thead><tbody>{visible.map(row => {
        const enriched = row as EnrichedSystemSummary
        const acrisCount = enriched.acris_recent_document_count ?? 0
        const hpdOpen = enriched.hpd_open_violation_count ?? 0
        const swoCount = enriched.stop_work_order_event_count ?? 0
        const fispStatus = enriched.facade_latest_status
        const hasActivity = (row.oath_case_count ?? 0) > 0 || (row.dob_recent_activity_count ?? 0) > 0 || acrisCount > 0 || hpdOpen > 0 || swoCount > 0 || Boolean(fispStatus)
        return <tr key={row.system_id} onClick={() => onSelect(row)} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') onSelect(row) }}>
          <td className="account-cell"><strong>{row.address ?? 'Address unavailable'}</strong><span>{row.borough ?? '—'} · {row.zip ?? '—'}</span><small className="mono">{row.system_id} · {row.active_equipment} active unit{row.active_equipment === 1 ? '' : 's'}</small></td>
          <td><div className={`priority-indicator priority-${priorityBand(row.priority_score)}`}><strong>{row.priority_score}</strong><span><i style={{ width:`${Math.max(4, row.priority_score)}%` }} /></span></div></td>
          <td><span className={`signal signal-${row.primary_signal.toLowerCase()}`}>{signalLabel(row.primary_signal)}</span>{row.confirmed_violation && <small className="urgent-copy">Confirmed record</small>}</td>
          <td>{(row.hpd_contact_count ?? 0) > 0 ? <span className="contact-ready">✓ {row.hpd_contact_count} HPD contact{row.hpd_contact_count === 1 ? '' : 's'}</span> : <span className="muted-copy">No matched contact</span>}</td>
          <td>{formatDate(row.latest_sample_date)}<small>{row.days_since_latest_sample == null ? 'No usable date' : `${row.days_since_latest_sample} days ago`}</small></td>
          <td><div className="activity-stack">{(row.oath_case_count ?? 0) > 0 && <span>OATH · {row.oath_case_count}</span>}{(row.dob_recent_activity_count ?? 0) > 0 && <span>DOB · {row.dob_recent_activity_count}</span>}{acrisCount > 0 && <span title={enriched.latest_acris_recorded_date ? `Latest recorded ${formatDate(enriched.latest_acris_recorded_date)}` : undefined}>ACRIS · {acrisCount}</span>}{hpdOpen > 0 && <span title={enriched.latest_hpd_violation_inspection_date ? `Latest inspection ${formatDate(enriched.latest_hpd_violation_inspection_date)}` : undefined}>HPD open · {hpdOpen}</span>}{swoCount > 0 && <span title="DOB complaint-disposition Stop Work Order evidence; not a claim that an order remains active">SWO evidence · {swoCount}</span>}{fispStatus && <span>FISP · {fispStatus}</span>}{!hasActivity && <span className="muted-copy">No recent match</span>}</div></td>
          <td><StatusBadge value={row.evidence_confidence} /></td><td className="row-arrow">›</td>
        </tr>
      })}</tbody></table></div>}
      <div className="pagination"><button disabled={activePage === 0} onClick={() => setPage(p => Math.max(0,p-1))}>Previous</button><span>Page {activePage + 1} of {maxPage + 1}</span><button disabled={activePage === maxPage} onClick={() => setPage(p => Math.min(maxPage,p+1))}>Next</button></div>
    </div>
  </>
}
