import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent } from '../types/history'
import type { SystemSummary } from '../types/data'
import type { AccountDisposition, WorkflowAccountState, WorkflowMembership, WorkflowWatchlist } from '../types/workflow'
import { formatDate, signalLabel } from '../domain/labels'
import { TowerMap } from './TowerMap'
import '../styles/workflow-portfolio.css'

const PAGE_SIZE = 50

const statuses: Array<{ value: AccountDisposition; label: string }> = [
  { value: 'new', label: 'New' },
  { value: 'investigate', label: 'Investigate' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'follow-up', label: 'Follow-up' },
  { value: 'monitor', label: 'Monitor' },
  { value: 'dismissed', label: 'Dismissed' },
]

type StatusFilter = 'all' | 'none' | AccountDisposition
type AttentionFilter = 'all' | 'due' | 'changed' | 'high'
type SortKey = 'address' | 'status' | 'next_action' | 'priority' | 'changes'

type WorkflowAccountsWorkspaceProps<T extends SystemSummary> = {
  systems: T[]
  accounts: WorkflowAccountState[]
  watchlists: WorkflowWatchlist[]
  memberships: WorkflowMembership[]
  eventsBySystem: ReadonlyMap<string, ChangeEvent[]>
  today: string
  onOpenAccount: (row: T) => void
}

function statusLabel(value: AccountDisposition | undefined) {
  if (!value) return 'No status'
  return statuses.find(status => status.value === value)?.label ?? value
}

function priorityBand(score: number) {
  if (score >= 70) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
}

export function WorkflowAccountsWorkspace<T extends SystemSummary>({
  systems,
  accounts,
  watchlists,
  memberships,
  eventsBySystem,
  today,
  onOpenAccount,
}: WorkflowAccountsWorkspaceProps<T>) {
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [watchlistFilter, setWatchlistFilter] = useState('all')
  const [attentionFilter, setAttentionFilter] = useState<AttentionFilter>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({ key: 'priority', dir: 'desc' })

  const accountById = useMemo(() => new Map(accounts.map(account => [account.system_id, account])), [accounts])
  const watchlistById = useMemo(() => new Map(watchlists.map(watchlist => [watchlist.id, watchlist.name])), [watchlists])
  const membershipIdsBySystem = useMemo(() => {
    const result = new Map<string, string[]>()
    memberships.forEach(membership => {
      const current = result.get(membership.system_id) ?? []
      current.push(membership.watchlist_id)
      result.set(membership.system_id, current)
    })
    return result
  }, [memberships])

  const filteredRows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return systems.filter(row => {
      const account = accountById.get(row.system_id)
      const membershipIds = membershipIdsBySystem.get(row.system_id) ?? []
      const watchlistNames = membershipIds.map(id => watchlistById.get(id) ?? '').filter(Boolean)
      if (needle) {
        const searchable = [row.address, row.borough, row.zip, row.system_id, account?.note, ...watchlistNames]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
        if (!searchable.includes(needle)) return false
      }
      if (statusFilter === 'none' && account) return false
      if (statusFilter !== 'all' && statusFilter !== 'none' && account?.status !== statusFilter) return false
      if (watchlistFilter !== 'all' && !membershipIds.includes(watchlistFilter)) return false
      if (attentionFilter === 'due' && !(account?.next_action_date && account.next_action_date <= today)) return false
      if (attentionFilter === 'changed' && (eventsBySystem.get(row.system_id)?.length ?? 0) === 0) return false
      if (attentionFilter === 'high' && row.priority_score < 70) return false
      return true
    })
  }, [accountById, attentionFilter, eventsBySystem, membershipIdsBySystem, query, statusFilter, systems, today, watchlistById, watchlistFilter])

  const sortedRows = useMemo(() => [...filteredRows].sort((a, b) => {
    const accountA = accountById.get(a.system_id)
    const accountB = accountById.get(b.system_id)
    let result = 0
    if (sort.key === 'address') result = String(a.address ?? a.system_id).localeCompare(String(b.address ?? b.system_id))
    if (sort.key === 'status') result = statusLabel(accountA?.status).localeCompare(statusLabel(accountB?.status))
    if (sort.key === 'next_action') result = String(accountA?.next_action_date ?? '9999-12-31').localeCompare(String(accountB?.next_action_date ?? '9999-12-31'))
    if (sort.key === 'priority') result = a.priority_score - b.priority_score
    if (sort.key === 'changes') result = (eventsBySystem.get(a.system_id)?.length ?? 0) - (eventsBySystem.get(b.system_id)?.length ?? 0)
    return sort.dir === 'asc' ? result : -result
  }), [accountById, eventsBySystem, filteredRows, sort])

  const maxPage = Math.max(0, Math.ceil(sortedRows.length / PAGE_SIZE) - 1)
  const activePage = Math.min(page, maxPage)
  const visibleRows = sortedRows.slice(activePage * PAGE_SIZE, activePage * PAGE_SIZE + PAGE_SIZE)
  const selectedRow = filteredRows.find(row => row.system_id === selectedId) ?? null
  const selectedAccount = selectedRow ? accountById.get(selectedRow.system_id) : undefined
  const selectedEvents = selectedRow ? (eventsBySystem.get(selectedRow.system_id) ?? []) : []
  const selectedWatchlists = selectedRow
    ? (membershipIdsBySystem.get(selectedRow.system_id) ?? []).map(id => watchlistById.get(id)).filter((name): name is string => Boolean(name))
    : []

  useEffect(() => { setPage(0) }, [query, statusFilter, watchlistFilter, attentionFilter])
  useEffect(() => {
    if (selectedId && !filteredRows.some(row => row.system_id === selectedId)) setSelectedId(null)
  }, [filteredRows, selectedId])

  const changeSort = (key: SortKey) => setSort(current => current.key === key
    ? { key, dir: current.dir === 'asc' ? 'desc' : 'asc' }
    : { key, dir: key === 'priority' || key === 'changes' ? 'desc' : 'asc' })

  const clearFilters = () => {
    setQuery('')
    setStatusFilter('all')
    setWatchlistFilter('all')
    setAttentionFilter('all')
  }

  return <section className="workflow-section-block workflow-portfolio-block" aria-labelledby="workflow-portfolio-heading">
    <div className="workflow-block-heading"><div><span className="page-kicker">Portfolio workspace</span><h2 id="workflow-portfolio-heading">Workflow accounts</h2><p>Work the same private account scope spatially and in a sortable table. Filters synchronize the map and table; selecting a marker or row does not change public evidence or Priority Score.</p></div><strong>{filteredRows.length.toLocaleString()} of {systems.length.toLocaleString()}</strong></div>

    <div className="workflow-portfolio-filters" aria-label="Workflow account filters">
      <label className="workflow-portfolio-search">Search<input aria-label="Search workflow accounts" value={query} onChange={event => setQuery(event.target.value)} placeholder="Address, borough, ZIP, ID, note or watchlist" /></label>
      <label>Status<select aria-label="Workflow status filter" value={statusFilter} onChange={event => setStatusFilter(event.target.value as StatusFilter)}><option value="all">All statuses</option><option value="none">No status</option>{statuses.map(status => <option key={status.value} value={status.value}>{status.label}</option>)}</select></label>
      <label>Watchlist<select aria-label="Workflow watchlist filter" value={watchlistFilter} onChange={event => setWatchlistFilter(event.target.value)}><option value="all">All watchlists</option>{watchlists.map(watchlist => <option key={watchlist.id} value={watchlist.id}>{watchlist.name}</option>)}</select></label>
      <label>Attention<select aria-label="Workflow attention filter" value={attentionFilter} onChange={event => setAttentionFilter(event.target.value as AttentionFilter)}><option value="all">All accounts</option><option value="due">Due / overdue</option><option value="changed">Changed · 7d</option><option value="high">High priority · 70+</option></select></label>
      <button type="button" className="workflow-portfolio-clear" onClick={clearFilters}>Clear filters</button>
    </div>

    {systems.length === 0 ? <div className="reference-empty-state compact"><span>Add an account to a watchlist or save workflow state from an account profile. Map and table views will use that same private scope.</span></div> : <>
      <div className="workflow-portfolio-map-layout">
        <div className="workflow-portfolio-map"><TowerMap systems={filteredRows} selectedId={selectedId} onSelect={row => setSelectedId(row.system_id)} /></div>
        <aside className="workflow-portfolio-selection" aria-live="polite">
          {selectedRow ? <>
            <div className="workflow-portfolio-selection-head"><div><span>{[selectedRow.borough, selectedRow.zip].filter(Boolean).join(' · ') || selectedRow.system_id}</span><strong>{selectedRow.address ?? selectedRow.system_id}</strong><small className="mono">{selectedRow.system_id}</small></div><span className={`workflow-priority ${selectedRow.priority_score >= 70 ? 'high' : ''}`}>P{selectedRow.priority_score}</span></div>
            <dl><div><dt>Workflow status</dt><dd><span className="status-chip">{statusLabel(selectedAccount?.status)}</span></dd></div><div><dt>Next action</dt><dd className={selectedAccount?.next_action_date && selectedAccount.next_action_date <= today ? 'due-date' : ''}>{selectedAccount?.next_action_date ? formatDate(selectedAccount.next_action_date) : 'No dated action'}</dd></div><div><dt>Changes · 7d</dt><dd>{selectedEvents.length}</dd></div><div><dt>Watchlists</dt><dd>{selectedWatchlists.length ? selectedWatchlists.join(', ') : 'None'}</dd></div></dl>
            <div className="workflow-portfolio-note"><span>Private note</span><p>{selectedAccount?.note || 'No private note saved.'}</p></div>
            <button type="button" className="primary workflow-portfolio-open" onClick={() => onOpenAccount(selectedRow)}>Open account →</button>
          </> : <div className="workflow-portfolio-selection-empty"><span className="page-kicker">Account preview</span><strong>{filteredRows.length ? 'Select a marker or table row' : 'No accounts match these filters'}</strong><p>{filteredRows.length ? 'Map and table selections stay synchronized. Open the account only when you need the full source-backed profile and private workflow controls.' : 'Clear or widen the filters to return accounts to the workspace.'}</p></div>}
        </aside>
      </div>

      <div className="table-card workflow-portfolio-table-card">
        <div className="table-heading"><div><strong>{filteredRows.length.toLocaleString()}</strong> matching workflow accounts</div><div>Showing {visibleRows.length ? activePage * PAGE_SIZE + 1 : 0}–{Math.min((activePage + 1) * PAGE_SIZE, filteredRows.length)}</div></div>
        {filteredRows.length === 0 ? <div className="empty-state"><strong>No workflow accounts match these filters.</strong><span>Clear or widen the private workflow filters above.</span></div> : <div className="table-scroll"><table className="workflow-portfolio-table"><thead><tr><th><button onClick={() => changeSort('address')}>Account</button></th><th><button onClick={() => changeSort('status')}>Status</button></th><th><button onClick={() => changeSort('next_action')}>Next action</button></th><th><button onClick={() => changeSort('priority')}>Priority</button></th><th>Timing signal</th><th><button onClick={() => changeSort('changes')}>Changes · 7d</button></th><th>Watchlists</th><th>Private note</th><th aria-label="Open account" /></tr></thead><tbody>{visibleRows.map(row => {
          const account = accountById.get(row.system_id)
          const events = eventsBySystem.get(row.system_id) ?? []
          const names = (membershipIdsBySystem.get(row.system_id) ?? []).map(id => watchlistById.get(id)).filter((name): name is string => Boolean(name))
          return <tr key={row.system_id} className={selectedId === row.system_id ? 'selected' : ''} onClick={() => setSelectedId(row.system_id)} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') setSelectedId(row.system_id) }}>
            <td className="account-cell"><strong>{row.address ?? 'Address unavailable'}</strong><span>{row.borough ?? '—'} · {row.zip ?? '—'}</span><small className="mono">{row.system_id}</small></td>
            <td><span className="status-chip">{statusLabel(account?.status)}</span></td>
            <td><strong className={account?.next_action_date && account.next_action_date <= today ? 'due-date' : ''}>{account?.next_action_date ? formatDate(account.next_action_date) : '—'}</strong><small>{account?.next_action_date && account.next_action_date <= today ? 'Due / overdue' : 'Private action date'}</small></td>
            <td><div className={`priority-indicator priority-${priorityBand(row.priority_score)}`}><strong>{row.priority_score}</strong><span><i style={{ width: `${Math.max(4, row.priority_score)}%` }} /></span></div></td>
            <td><span className={`signal signal-${row.primary_signal.toLowerCase()}`}>{signalLabel(row.primary_signal)}</span></td>
            <td>{events.length ? <strong>{events.length}</strong> : <span className="muted-copy">None</span>}</td>
            <td>{names.length ? <div className="workflow-portfolio-watchlists">{names.map(name => <span key={name}>{name}</span>)}</div> : <span className="muted-copy">None</span>}</td>
            <td className="workflow-portfolio-note-cell">{account?.note || <span className="muted-copy">No note</span>}</td>
            <td className="row-arrow"><button type="button" className="table-link" aria-label={`Open ${row.address ?? row.system_id}`} onClick={event => { event.stopPropagation(); onOpenAccount(row) }}>›</button></td>
          </tr>
        })}</tbody></table></div>}
        <div className="pagination"><button disabled={activePage === 0} onClick={() => setPage(current => Math.max(0, current - 1))}>Previous</button><span>Page {activePage + 1} of {maxPage + 1}</span><button disabled={activePage === maxPage} onClick={() => setPage(current => Math.min(maxPage, current + 1))}>Next</button></div>
      </div>
    </>}
  </section>
}
