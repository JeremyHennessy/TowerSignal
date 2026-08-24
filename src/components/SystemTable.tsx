import { useMemo, useState } from 'react'
import type { SystemSummary } from '../types/data'
import type { AcrisSummaryFields } from '../types/acris'
import { formatDate, signalLabel } from '../domain/labels'
import { StatusBadge } from './StatusBadge'

const PAGE_SIZE = 50

type SortKey = 'priority_score' | 'address' | 'active_equipment' | 'days_since_latest_sample' | 'latest_inspection_date' | 'oath_case_count'
type EnrichedSystemSummary = SystemSummary & AcrisSummaryFields

function priorityBand(score: number): string {
  if (score >= 70) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
}

export function SystemTable({ rows, onSelect }: { rows: SystemSummary[]; onSelect: (row: SystemSummary) => void }) {
  const [page, setPage] = useState(0)
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({ key: 'priority_score', dir: 'desc' })
  const sorted = useMemo(() => [...rows].sort((a,b) => {
    const av = a[sort.key] ?? ''; const bv = b[sort.key] ?? ''
    const result = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv))
    return sort.dir === 'asc' ? result : -result
  }), [rows, sort])
  const maxPage = Math.max(0, Math.ceil(sorted.length / PAGE_SIZE) - 1)
  const activePage = Math.min(page, maxPage)
  const visible = sorted.slice(activePage * PAGE_SIZE, activePage * PAGE_SIZE + PAGE_SIZE)
  const changeSort = (key: SortKey) => setSort(current => current.key === key ? { key, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'priority_score' ? 'desc' : 'asc' })

  return <div className="table-card account-table-card">
    <div className="table-heading"><div><strong>{rows.length.toLocaleString()}</strong> matching systems</div><div>Showing {visible.length ? activePage * PAGE_SIZE + 1 : 0}–{Math.min((activePage + 1) * PAGE_SIZE, rows.length)}</div></div>
    {rows.length === 0 ? <div className="empty-state"><strong>No accounts match these filters.</strong><span>Try widening the territory, timing signal or priority criteria.</span></div> : <div className="table-scroll"><table className="account-table"><thead><tr>
      <th><button onClick={() => changeSort('address')}>Account</button></th><th><button onClick={() => changeSort('priority_score')}>Priority</button></th><th>Timing signal</th><th>Contact</th><th><button onClick={() => changeSort('days_since_latest_sample')}>Sampling</button></th><th><button onClick={() => changeSort('oath_case_count')}>Activity</button></th><th>Evidence</th><th aria-label="Open account" />
    </tr></thead><tbody>{visible.map(row => {
      const acris = row as EnrichedSystemSummary
      const acrisCount = acris.acris_recent_document_count ?? 0
      const hasActivity = (row.oath_case_count ?? 0) > 0 || (row.dob_recent_activity_count ?? 0) > 0 || acrisCount > 0
      return <tr key={row.system_id} onClick={() => onSelect(row)} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') onSelect(row) }}>
        <td className="account-cell"><strong>{row.address ?? 'Address unavailable'}</strong><span>{row.borough ?? '—'} · {row.zip ?? '—'}</span><small className="mono">{row.system_id} · {row.active_equipment} active unit{row.active_equipment === 1 ? '' : 's'}</small></td>
        <td><div className={`priority-indicator priority-${priorityBand(row.priority_score)}`}><strong>{row.priority_score}</strong><span><i style={{ width:`${Math.max(4, row.priority_score)}%` }} /></span></div></td>
        <td><span className={`signal signal-${row.primary_signal.toLowerCase()}`}>{signalLabel(row.primary_signal)}</span>{row.confirmed_violation && <small className="urgent-copy">Confirmed record</small>}</td>
        <td>{(row.hpd_contact_count ?? 0) > 0 ? <span className="contact-ready">✓ {row.hpd_contact_count} HPD contact{row.hpd_contact_count === 1 ? '' : 's'}</span> : <span className="muted-copy">No matched contact</span>}</td>
        <td>{formatDate(row.latest_sample_date)}<small>{row.days_since_latest_sample == null ? 'No usable date' : `${row.days_since_latest_sample} days ago`}</small></td>
        <td><div className="activity-stack">{(row.oath_case_count ?? 0) > 0 && <span>OATH · {row.oath_case_count}</span>}{(row.dob_recent_activity_count ?? 0) > 0 && <span>DOB · {row.dob_recent_activity_count}</span>}{acrisCount > 0 && <span title={acris.latest_acris_recorded_date ? `Latest recorded ${formatDate(acris.latest_acris_recorded_date)}` : undefined}>ACRIS · {acrisCount}</span>}{!hasActivity && <span className="muted-copy">No recent match</span>}</div></td>
        <td><StatusBadge value={row.evidence_confidence} /></td><td className="row-arrow">›</td>
      </tr>
    })}</tbody></table></div>}
    <div className="pagination"><button disabled={activePage === 0} onClick={() => setPage(p => Math.max(0,p-1))}>Previous</button><span>Page {activePage + 1} of {maxPage + 1}</span><button disabled={activePage === maxPage} onClick={() => setPage(p => Math.min(maxPage,p+1))}>Next</button></div>
  </div>
}
