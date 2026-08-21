import { useMemo, useState } from 'react'
import type { SystemSummary } from '../types/data'
import { formatDate, signalLabel } from '../domain/labels'
import { StatusBadge } from './StatusBadge'

const PAGE_SIZE = 50

type SortKey = 'priority_score' | 'address' | 'active_equipment' | 'days_since_latest_sample' | 'latest_inspection_date'

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

  return <div className="table-card">
    <div className="table-heading"><div><strong>{rows.length.toLocaleString()}</strong> matching systems</div><div>Showing {visible.length ? activePage * PAGE_SIZE + 1 : 0}–{Math.min((activePage + 1) * PAGE_SIZE, rows.length)}</div></div>
    {rows.length === 0 ? <div className="empty-state">No systems match the active filters.</div> : <div className="table-scroll"><table><thead><tr>
      <th><button onClick={() => changeSort('priority_score')}>Priority</button></th><th>Signal</th><th><button onClick={() => changeSort('address')}>Address</button></th><th>Borough / ZIP</th><th>System ID</th><th><button onClick={() => changeSort('active_equipment')}>Equipment</button></th><th><button onClick={() => changeSort('days_since_latest_sample')}>Latest sample</button></th><th><button onClick={() => changeSort('latest_inspection_date')}>NYC Health inspection</button></th><th>Violation</th><th>Evidence</th>
    </tr></thead><tbody>{visible.map(row => <tr key={row.system_id} onClick={() => onSelect(row)} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') onSelect(row) }}>
      <td><span className="score">{row.priority_score}</span></td><td><span className={`signal signal-${row.primary_signal.toLowerCase()}`}>{signalLabel(row.primary_signal)}</span></td><td>{row.address ?? 'Address unavailable'}</td><td>{row.borough ?? '—'}<small>{row.zip ?? '—'}</small></td><td className="mono">{row.system_id}</td><td>{row.active_equipment}</td><td>{formatDate(row.latest_sample_date)}<small>{row.days_since_latest_sample == null ? 'No usable date' : `${row.days_since_latest_sample} days ago`}</small></td><td>{formatDate(row.latest_inspection_date)}<small>{row.latest_inspection_type ?? '—'}</small></td><td>{row.confirmed_violation ? 'Confirmed record' : 'None recorded'}</td><td><StatusBadge value={row.evidence_confidence} /></td>
    </tr>)}</tbody></table></div>}
    <div className="pagination"><button disabled={activePage === 0} onClick={() => setPage(p => Math.max(0,p-1))}>Previous</button><span>Page {activePage + 1} of {maxPage + 1}</span><button disabled={activePage === maxPage} onClick={() => setPage(p => Math.min(maxPage,p+1))}>Next</button></div>
  </div>
}
