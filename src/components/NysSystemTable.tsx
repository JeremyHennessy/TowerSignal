import { useMemo, useState } from 'react'
import type { NysSystem } from '../types/nys'
import { formatDate } from '../domain/labels'

const PAGE_SIZE = 50

type SortKey = 'regulation_compliance' | 'address' | 'ct_status' | 'latest_sample_date' | 'property_equipment_count' | 'last_update_days'

const statusLabel = (value: string | null) => value ? value.replaceAll('_', ' ') : '—'
const resultLabel = (value: string | null) => {
  if (!value) return '—'
  const labels: Record<string, string> = {
    lt10: '<10',
    lt20: '<20',
    gteq20butlt100: '≥20 to <100',
    gteq100butlt1000: '≥100 to <1,000',
    gteq1000: '≥1,000',
    gt10lt1000: '>10 to <1,000',
  }
  return labels[value] ?? value
}

export function NysSystemTable({ rows, onSelect }: { rows: NysSystem[]; onSelect: (row: NysSystem) => void }) {
  const [page, setPage] = useState(0)
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({ key: 'regulation_compliance', dir: 'desc' })
  const sorted = useMemo(() => [...rows].sort((a,b) => {
    const av = a[sort.key] ?? ''; const bv = b[sort.key] ?? ''
    const result = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv))
    return sort.dir === 'asc' ? result : -result
  }), [rows, sort])
  const maxPage = Math.max(0, Math.ceil(sorted.length / PAGE_SIZE) - 1)
  const activePage = Math.min(page, maxPage)
  const visible = sorted.slice(activePage * PAGE_SIZE, activePage * PAGE_SIZE + PAGE_SIZE)
  const changeSort = (key: SortKey) => setSort(current => current.key === key ? { key, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'property_equipment_count' ? 'desc' : 'asc' })

  return <div className="table-card">
    <div className="table-heading"><div><strong>{rows.length.toLocaleString()}</strong> matching NYS equipment records</div><div>Showing {visible.length ? activePage * PAGE_SIZE + 1 : 0}–{Math.min((activePage + 1) * PAGE_SIZE, rows.length)}</div></div>
    {rows.length === 0 ? <div className="empty-state">No NYS equipment records match the active filters.</div> : <div className="table-scroll"><table className="nys-table"><thead><tr>
      <th><button onClick={() => changeSort('regulation_compliance')}>Compliance</button></th><th><button onClick={() => changeSort('ct_status')}>Registry status</button></th><th><button onClick={() => changeSort('address')}>Address</button></th><th>Published county</th><th>Equipment ID</th><th><button onClick={() => changeSort('property_equipment_count')}>Property equipment</button></th><th><button onClick={() => changeSort('latest_sample_date')}>Latest sample</button></th><th>Legionella result</th><th>Operation</th><th><button onClick={() => changeSort('last_update_days')}>Source update</button></th>
    </tr></thead><tbody>{visible.map(row => <tr key={row.system_id} onClick={() => onSelect(row)} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') onSelect(row) }}>
      <td><span className={`nys-source-status ${row.regulation_compliance === 'Non-compliant' ? 'attention' : 'clear'}`}>{row.regulation_compliance ?? '—'}</span></td>
      <td>{statusLabel(row.ct_status)}</td>
      <td>{row.address ?? 'Address unavailable'}<small>{row.city ?? '—'} {row.zip ?? ''}</small></td>
      <td>{row.source_county ?? '—'}</td>
      <td className="mono">{row.source_equipment_id}</td>
      <td>{row.property_equipment_count.toLocaleString()}<small>{row.property_equipment_count > 1 ? 'Same address key' : 'Single equipment record'}</small></td>
      <td>{formatDate(row.latest_sample_date)}<small>{row.last_sampled_days == null ? 'Relative days unavailable' : `${row.last_sampled_days} source-reported days`}</small></td>
      <td>{resultLabel(row.latest_sample_result)}</td>
      <td>{row.operation_duration ?? '—'}</td>
      <td>{row.last_update_days == null ? '—' : `${row.last_update_days} days`}<small>Published relative counter</small></td>
    </tr>)}</tbody></table></div>}
    <div className="pagination"><button disabled={activePage === 0} onClick={() => setPage(p => Math.max(0,p-1))}>Previous</button><span>Page {activePage + 1} of {maxPage + 1}</span><button disabled={activePage === maxPage} onClick={() => setPage(p => Math.min(maxPage,p+1))}>Next</button></div>
  </div>
}