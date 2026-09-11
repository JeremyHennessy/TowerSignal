import { useEffect, useMemo, useState } from 'react'
import type { ChangeEvent } from '../types/history'
import type { SystemSummary } from '../types/data'
import type { AccountDisposition, WorkflowAccountState, WorkflowMembership, WorkflowSavedView, WorkflowWatchlist } from '../types/workflow'
import { formatDate, signalLabel } from '../domain/labels'
import { TowerMap } from './TowerMap'
import '../styles/workflow-scale-command-center.css'

const PAGE_SIZE = 50
const EVENT_PAGE_SIZE = 75
const ACTION_STATUSES = new Set<AccountDisposition>(['investigate', 'contacted', 'follow-up'])

const statuses: Array<{ value: AccountDisposition; label: string }> = [
  { value: 'new', label: 'New' },
  { value: 'investigate', label: 'Investigate' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'follow-up', label: 'Follow-up' },
  { value: 'monitor', label: 'Monitor' },
  { value: 'dismissed', label: 'Dismissed' },
]

type WorkspaceTab = 'accounts' | 'changes' | 'actions'
type AccountView = 'split' | 'table' | 'map'
type StatusFilter = 'all' | 'none' | AccountDisposition
type AttentionFilter = 'all' | 'due' | 'changed' | 'high' | 'contact' | 'unscheduled'
type SortKey = 'address' | 'status' | 'next_action' | 'priority' | 'changes'

type Props<T extends SystemSummary> = {
  systems: T[]
  marketCount: number
  accounts: WorkflowAccountState[]
  watchlists: WorkflowWatchlist[]
  memberships: WorkflowMembership[]
  savedViews: WorkflowSavedView[]
  recentEvents: ChangeEvent[]
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

function titleCase(value: string) {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, match => match.toUpperCase())
}

function dueState(account: WorkflowAccountState | undefined, today: string) {
  if (!account?.next_action_date) return 'none'
  if (account.next_action_date < today) return 'overdue'
  if (account.next_action_date === today) return 'today'
  return 'future'
}

function actionRank(account: WorkflowAccountState | undefined, today: string) {
  const state = dueState(account, today)
  if (state === 'overdue') return 0
  if (state === 'today') return 1
  if (state === 'future') return 2
  if (account && ACTION_STATUSES.has(account.status)) return 3
  return 4
}

export function WorkflowScaleWorkspace<T extends SystemSummary>({
  systems,
  marketCount,
  accounts,
  watchlists,
  memberships,
  savedViews,
  recentEvents,
  eventsBySystem,
  today,
  onOpenAccount,
}: Props<T>) {
  const [tab, setTab] = useState<WorkspaceTab>('accounts')
  const [accountView, setAccountView] = useState<AccountView>('split')
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [watchlistFilter, setWatchlistFilter] = useState('all')
  const [boroughFilter, setBoroughFilter] = useState('all')
  const [attentionFilter, setAttentionFilter] = useState<AttentionFilter>('all')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const [eventPage, setEventPage] = useState(0)
  const [actionPage, setActionPage] = useState(0)
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({ key: 'priority', dir: 'desc' })

  const accountById = useMemo(() => new Map(accounts.map(account => [account.system_id, account])), [accounts])
  const rowById = useMemo(() => new Map(systems.map(row => [row.system_id, row])), [systems])
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
  const boroughs = useMemo(() => [...new Set(systems.map(row => row.borough).filter((value): value is string => Boolean(value)))].sort(), [systems])

  const counts = useMemo(() => {
    const due = systems.filter(row => {
      const account = accountById.get(row.system_id)
      return Boolean(account?.next_action_date && account.next_action_date <= today)
    }).length
    const changed = systems.filter(row => (eventsBySystem.get(row.system_id)?.length ?? 0) > 0).length
    const high = systems.filter(row => row.priority_score >= 70).length
    const contact = systems.filter(row => (row.hpd_contact_count ?? 0) > 0).length
    const unscheduled = systems.filter(row => {
      const account = accountById.get(row.system_id)
      return Boolean(account && ACTION_STATUSES.has(account.status) && !account.next_action_date)
    }).length
    return { due, changed, high, contact, unscheduled }
  }, [accountById, eventsBySystem, systems, today])

  const statusCounts = useMemo(() => {
    const result = new Map<StatusFilter, number>()
    result.set('none', 0)
    statuses.forEach(status => result.set(status.value, 0))
    systems.forEach(row => {
      const status = accountById.get(row.system_id)?.status ?? 'none'
      result.set(status, (result.get(status) ?? 0) + 1)
    })
    return result
  }, [accountById, systems])

  const watchlistCounts = useMemo(() => {
    const result = new Map<string, number>()
    memberships.forEach(membership => {
      if (!rowById.has(membership.system_id)) return
      result.set(membership.watchlist_id, (result.get(membership.watchlist_id) ?? 0) + 1)
    })
    return result
  }, [memberships, rowById])

  const filteredRows = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return systems.filter(row => {
      const account = accountById.get(row.system_id)
      const membershipIds = membershipIdsBySystem.get(row.system_id) ?? []
      const watchlistNames = membershipIds.map(id => watchlistById.get(id) ?? '').filter(Boolean)
      if (needle) {
        const searchable = [row.address, row.borough, row.zip, row.system_id, row.pluto_owner_name, account?.note, ...watchlistNames]
          .filter(Boolean).join(' ').toLowerCase()
        if (!searchable.includes(needle)) return false
      }
      if (statusFilter === 'none' && account) return false
      if (statusFilter !== 'all' && statusFilter !== 'none' && account?.status !== statusFilter) return false
      if (watchlistFilter !== 'all' && !membershipIds.includes(watchlistFilter)) return false
      if (boroughFilter !== 'all' && row.borough !== boroughFilter) return false
      if (attentionFilter === 'due' && !(account?.next_action_date && account.next_action_date <= today)) return false
      if (attentionFilter === 'changed' && (eventsBySystem.get(row.system_id)?.length ?? 0) === 0) return false
      if (attentionFilter === 'high' && row.priority_score < 70) return false
      if (attentionFilter === 'contact' && (row.hpd_contact_count ?? 0) === 0) return false
      if (attentionFilter === 'unscheduled' && !(account && ACTION_STATUSES.has(account.status) && !account.next_action_date)) return false
      return true
    })
  }, [accountById, attentionFilter, boroughFilter, eventsBySystem, membershipIdsBySystem, query, statusFilter, systems, today, watchlistById, watchlistFilter])

  const sortedRows = useMemo(() => [...filteredRows].sort((a, b) => {
    const accountA = accountById.get(a.system_id)
    const accountB = accountById.get(b.system_id)
    let result = 0
    if (sort.key === 'address') result = String(a.address ?? a.system_id).localeCompare(String(b.address ?? b.system_id))
    if (sort.key === 'status') result = statusLabel(accountA?.status).localeCompare(statusLabel(accountB?.status))
    if (sort.key === 'next_action') result = String(accountA?.next_action_date ?? '9999-12-31').localeCompare(String(accountB?.next_action_date ?? '9999-12-31'))
    if (sort.key === 'priority') result = a.priority_score - b.priority_score
    if (sort.key === 'changes') result = (eventsBySystem.get(a.system_id)?.length ?? 0) - (eventsBySystem.get(b.system_id)?.length ?? 0)
    if (result === 0) result = String(a.address ?? a.system_id).localeCompare(String(b.address ?? b.system_id))
    return sort.dir === 'asc' ? result : -result
  }), [accountById, eventsBySystem, filteredRows, sort])

  const maxPage = Math.max(0, Math.ceil(sortedRows.length / PAGE_SIZE) - 1)
  const activePage = Math.min(page, maxPage)
  const visibleRows = sortedRows.slice(activePage * PAGE_SIZE, activePage * PAGE_SIZE + PAGE_SIZE)
  const filteredIds = useMemo(() => new Set(filteredRows.map(row => row.system_id)), [filteredRows])
  const filteredEvents = useMemo(() => recentEvents.filter(event => filteredIds.has(event.system_id)).sort((a, b) => b.detected_at.localeCompare(a.detected_at)), [filteredIds, recentEvents])
  const eventMaxPage = Math.max(0, Math.ceil(filteredEvents.length / EVENT_PAGE_SIZE) - 1)
  const activeEventPage = Math.min(eventPage, eventMaxPage)
  const visibleEvents = filteredEvents.slice(activeEventPage * EVENT_PAGE_SIZE, activeEventPage * EVENT_PAGE_SIZE + EVENT_PAGE_SIZE)
  const actionRows = useMemo(() => filteredRows.filter(row => {
    const account = accountById.get(row.system_id)
    return Boolean(account?.next_action_date || (account && ACTION_STATUSES.has(account.status)))
  }).sort((a, b) => {
    const accountA = accountById.get(a.system_id)
    const accountB = accountById.get(b.system_id)
    const rank = actionRank(accountA, today) - actionRank(accountB, today)
    if (rank !== 0) return rank
    const date = String(accountA?.next_action_date ?? '9999-12-31').localeCompare(String(accountB?.next_action_date ?? '9999-12-31'))
    if (date !== 0) return date
    return b.priority_score - a.priority_score
  }), [accountById, filteredRows, today])
  const actionMaxPage = Math.max(0, Math.ceil(actionRows.length / PAGE_SIZE) - 1)
  const activeActionPage = Math.min(actionPage, actionMaxPage)
  const visibleActions = actionRows.slice(activeActionPage * PAGE_SIZE, activeActionPage * PAGE_SIZE + PAGE_SIZE)

  const selectedRow = (selectedId ? rowById.get(selectedId) : undefined) ?? null
  const selectedAccount = selectedRow ? accountById.get(selectedRow.system_id) : undefined
  const selectedEvents = selectedRow ? (eventsBySystem.get(selectedRow.system_id) ?? []) : []
  const selectedWatchlists = selectedRow ? (membershipIdsBySystem.get(selectedRow.system_id) ?? []).map(id => watchlistById.get(id)).filter((name): name is string => Boolean(name)) : []

  useEffect(() => { setPage(0); setEventPage(0); setActionPage(0) }, [query, statusFilter, watchlistFilter, boroughFilter, attentionFilter])
  useEffect(() => { if (selectedId && !rowById.has(selectedId)) setSelectedId(null) }, [rowById, selectedId])

  const changeSort = (key: SortKey) => setSort(current => current.key === key ? { key, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'priority' || key === 'changes' ? 'desc' : 'asc' })
  const sortIndicator = (key: SortKey) => sort.key === key ? (sort.dir === 'asc' ? ' ↑' : ' ↓') : ''
  const clearFilters = () => { setQuery(''); setStatusFilter('all'); setWatchlistFilter('all'); setBoroughFilter('all'); setAttentionFilter('all') }
  const applyQuickView = (nextTab: WorkspaceTab, filter: AttentionFilter) => { setTab(nextTab); setAttentionFilter(filter) }

  const tabCounts = { accounts: filteredRows.length, changes: filteredEvents.length, actions: actionRows.length }

  return <section className="workflow-command-center" aria-label="Workflow command center">
    <div className="workflow-command-strip" aria-label="Workflow quick views">
      <button className={attentionFilter === 'all' && tab === 'accounts' ? 'active' : ''} onClick={() => applyQuickView('accounts', 'all')}><span>All workflow</span><strong>{systems.length.toLocaleString()}</strong><small>of {marketCount.toLocaleString()} NYC accounts</small></button>
      <button className={attentionFilter === 'due' ? 'active urgent' : 'urgent'} onClick={() => applyQuickView('actions', 'due')}><span>Due / overdue</span><strong>{counts.due.toLocaleString()}</strong><small>dated next actions</small></button>
      <button className={attentionFilter === 'changed' ? 'active' : ''} onClick={() => applyQuickView('changes', 'changed')}><span>Changed · 7d</span><strong>{counts.changed.toLocaleString()}</strong><small>accounts with source changes</small></button>
      <button className={attentionFilter === 'high' ? 'active' : ''} onClick={() => applyQuickView('accounts', 'high')}><span>High priority</span><strong>{counts.high.toLocaleString()}</strong><small>Priority Score 70+</small></button>
      <button className={attentionFilter === 'unscheduled' ? 'active warning' : 'warning'} onClick={() => applyQuickView('actions', 'unscheduled')}><span>Needs a date</span><strong>{counts.unscheduled.toLocaleString()}</strong><small>active follow-up without date</small></button>
      <button className={attentionFilter === 'contact' ? 'active' : ''} onClick={() => applyQuickView('accounts', 'contact')}><span>Contact-ready</span><strong>{counts.contact.toLocaleString()}</strong><small>HPD contact evidence</small></button>
    </div>

    <div className="workflow-pipeline-strip" aria-label="Workflow status distribution"><span>Pipeline</span><button className={statusFilter === 'none' ? 'active' : ''} onClick={() => setStatusFilter(current => current === 'none' ? 'all' : 'none')}>No status <strong>{statusCounts.get('none') ?? 0}</strong></button>{statuses.map(status => <button key={status.value} className={statusFilter === status.value ? 'active' : ''} onClick={() => setStatusFilter(current => current === status.value ? 'all' : status.value)}>{status.label} <strong>{statusCounts.get(status.value) ?? 0}</strong></button>)}</div>

    <div className="workflow-command-tabs" role="tablist" aria-label="Workflow views">{(['accounts', 'changes', 'actions'] as WorkspaceTab[]).map(value => <button key={value} role="tab" aria-selected={tab === value} className={tab === value ? 'active' : ''} onClick={() => setTab(value)}><span>{value === 'accounts' ? 'Accounts' : value === 'changes' ? 'Changes' : 'Actions'}</span><strong>{tabCounts[value].toLocaleString()}</strong></button>)}<div className="workflow-command-view-summary">{filteredRows.length.toLocaleString()} matching accounts</div></div>

    <div className="workflow-command-filters"><label className="workflow-command-search">Search<input aria-label="Search workflow accounts" value={query} onChange={event => setQuery(event.target.value)} placeholder="Address, owner, borough, ID, note or watchlist" /></label><label>Status<select aria-label="Workflow status filter" value={statusFilter} onChange={event => setStatusFilter(event.target.value as StatusFilter)}><option value="all">All statuses</option><option value="none">No status</option>{statuses.map(status => <option key={status.value} value={status.value}>{status.label}</option>)}</select></label><label>Watchlist<select aria-label="Workflow watchlist filter" value={watchlistFilter} onChange={event => setWatchlistFilter(event.target.value)}><option value="all">All watchlists</option>{watchlists.map(watchlist => <option key={watchlist.id} value={watchlist.id}>{watchlist.name} ({watchlistCounts.get(watchlist.id) ?? 0})</option>)}</select></label><label>Borough<select aria-label="Workflow borough filter" value={boroughFilter} onChange={event => setBoroughFilter(event.target.value)}><option value="all">All boroughs</option>{boroughs.map(borough => <option key={borough} value={borough}>{borough}</option>)}</select></label><label>Attention<select aria-label="Workflow attention filter" value={attentionFilter} onChange={event => setAttentionFilter(event.target.value as AttentionFilter)}><option value="all">All accounts</option><option value="due">Due / overdue</option><option value="changed">Changed · 7d</option><option value="high">High priority · 70+</option><option value="contact">Contact-ready</option><option value="unscheduled">Needs next-action date</option></select></label><button type="button" className="workflow-command-clear" onClick={clearFilters}>Clear</button></div>

    {watchlists.length > 0 && <div className="workflow-watchlist-shortcuts"><span>Watchlists</span>{watchlists.slice(0, 8).map(watchlist => <button key={watchlist.id} className={watchlistFilter === watchlist.id ? 'active' : ''} onClick={() => setWatchlistFilter(current => current === watchlist.id ? 'all' : watchlist.id)}>{watchlist.name}<strong>{watchlistCounts.get(watchlist.id) ?? 0}</strong></button>)}</div>}

    <div className="workflow-command-grid"><div className="workflow-command-primary">
      {tab === 'accounts' && <><div className="workflow-account-view-toggle" aria-label="Account view mode"><span>Account view</span>{(['split', 'table', 'map'] as AccountView[]).map(value => <button key={value} className={accountView === value ? 'active' : ''} onClick={() => setAccountView(value)}>{value === 'split' ? 'Map + table' : value === 'table' ? 'Table' : 'Map'}</button>)}</div>{filteredRows.length === 0 ? <div className="reference-empty-state compact"><strong>No workflow accounts match these filters.</strong><span>Clear or widen the filters to return accounts to the workspace.</span></div> : <>{accountView !== 'table' && <div className="workflow-command-map"><TowerMap systems={filteredRows} selectedId={selectedId} onSelect={row => setSelectedId(row.system_id)} /></div>}{accountView !== 'map' && <div className="table-card workflow-command-table-card"><div className="table-heading"><div><strong>{filteredRows.length.toLocaleString()}</strong> workflow accounts</div><span>Showing {visibleRows.length ? activePage * PAGE_SIZE + 1 : 0}–{Math.min((activePage + 1) * PAGE_SIZE, filteredRows.length)}</span></div><div className="table-scroll"><table className="workflow-command-table"><thead><tr><th><button onClick={() => changeSort('address')}>Account{sortIndicator('address')}</button></th><th><button onClick={() => changeSort('status')}>Status{sortIndicator('status')}</button></th><th><button onClick={() => changeSort('next_action')}>Next action{sortIndicator('next_action')}</button></th><th><button onClick={() => changeSort('priority')}>Priority{sortIndicator('priority')}</button></th><th>Why now</th><th><button onClick={() => changeSort('changes')}>Changes{sortIndicator('changes')}</button></th><th>Contact</th><th>Watchlists</th><th aria-label="Open account" /></tr></thead><tbody>{visibleRows.map(row => { const account = accountById.get(row.system_id); const events = eventsBySystem.get(row.system_id) ?? []; const names = (membershipIdsBySystem.get(row.system_id) ?? []).map(id => watchlistById.get(id)).filter((name): name is string => Boolean(name)); const state = dueState(account, today); return <tr key={row.system_id} className={selectedId === row.system_id ? 'selected-row' : ''} onClick={() => setSelectedId(row.system_id)} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') setSelectedId(row.system_id) }}><td className="account-cell"><strong>{row.address ?? 'Address unavailable'}</strong><span>{[row.borough, row.zip].filter(Boolean).join(' · ') || 'Location unavailable'}</span><small className="mono">{row.system_id}</small></td><td><span className="status-chip">{statusLabel(account?.status)}</span></td><td>{account?.next_action_date ? <><strong className={state === 'overdue' || state === 'today' ? 'due-date' : ''}>{formatDate(account.next_action_date)}</strong><small>{state === 'overdue' ? 'Overdue' : state === 'today' ? 'Due today' : 'Scheduled'}</small></> : account && ACTION_STATUSES.has(account.status) ? <span className="workflow-needs-date">Needs date</span> : <span className="muted-copy">—</span>}</td><td><div className={`priority-indicator priority-${priorityBand(row.priority_score)}`}><strong>{row.priority_score}</strong><span><i style={{ width: `${Math.max(4, row.priority_score)}%` }} /></span></div></td><td><span className={`signal signal-${row.primary_signal.toLowerCase()}`}>{signalLabel(row.primary_signal)}</span>{row.recent_confirmed_violation && <small className="urgent-copy">Recent violation</small>}</td><td>{events.length ? <strong>{events.length}</strong> : <span className="muted-copy">0</span>}</td><td>{(row.hpd_contact_count ?? 0) > 0 ? <span className="contact-ready">✓ {row.hpd_contact_count}</span> : <span className="muted-copy">—</span>}</td><td>{names.length ? <div className="workflow-mini-tags">{names.slice(0, 2).map(name => <span key={name}>{name}</span>)}{names.length > 2 && <span>+{names.length - 2}</span>}</div> : <span className="muted-copy">—</span>}</td><td className="row-arrow"><button type="button" className="table-link" aria-label={`Open ${row.address ?? row.system_id}`} onClick={event => { event.stopPropagation(); onOpenAccount(row) }}>›</button></td></tr> })}</tbody></table></div><div className="pagination"><button disabled={activePage === 0} onClick={() => setPage(current => Math.max(0, current - 1))}>Previous</button><span>Page {activePage + 1} of {maxPage + 1}</span><button disabled={activePage === maxPage} onClick={() => setPage(current => Math.min(maxPage, current + 1))}>Next</button></div></div>}</>}</>}

      {tab === 'changes' && <div className="table-card workflow-command-table-card"><div className="table-heading"><div><strong>{filteredEvents.length.toLocaleString()}</strong> source changes in the current 7-day monitor window</div><span>{counts.changed.toLocaleString()} affected workflow accounts</span></div>{filteredEvents.length === 0 ? <div className="empty-state"><strong>No recent source changes match these filters.</strong><span>Widen the account filters or return to all workflow accounts.</span></div> : <div className="table-scroll"><table className="workflow-command-table workflow-change-table"><thead><tr><th>Detected</th><th>Account</th><th>Change</th><th>Source observation</th><th>Priority</th><th>Workflow</th><th>Source</th><th aria-label="Open account" /></tr></thead><tbody>{visibleEvents.map((event, index) => { const row = rowById.get(event.system_id); const account = accountById.get(event.system_id); return <tr key={`${event.system_id}-${event.event_type}-${event.detected_at}-${index}`} className={selectedId === event.system_id ? 'selected-row' : ''} onClick={() => setSelectedId(event.system_id)}><td><strong>{formatDate(event.detected_at)}</strong></td><td className="account-cell"><strong>{row?.address ?? event.address ?? event.system_id}</strong><span>{row?.borough ?? event.borough ?? '—'}</span><small className="mono">{event.system_id}</small></td><td><strong>{titleCase(event.event_type)}</strong><small>{event.evidence_confidence ?? 'Evidence confidence unavailable'}</small></td><td>{event.source_observation_date ? formatDate(event.source_observation_date) : '—'}</td><td>{row ? <span className={row.priority_score >= 70 ? 'priority-text-high' : ''}>P{row.priority_score}</span> : event.priority_score != null ? `P${event.priority_score}` : '—'}</td><td><span className="status-chip">{statusLabel(account?.status)}</span></td><td><span className="workflow-source-label">{event.source}</span></td><td className="row-arrow">{row && <button className="table-link" onClick={click => { click.stopPropagation(); onOpenAccount(row) }}>›</button>}</td></tr> })}</tbody></table></div>}<div className="pagination"><button disabled={activeEventPage === 0} onClick={() => setEventPage(current => Math.max(0, current - 1))}>Previous</button><span>Page {activeEventPage + 1} of {eventMaxPage + 1}</span><button disabled={activeEventPage === eventMaxPage} onClick={() => setEventPage(current => Math.min(eventMaxPage, current + 1))}>Next</button></div></div>}

      {tab === 'actions' && <div className="table-card workflow-command-table-card"><div className="table-heading"><div><strong>{actionRows.length.toLocaleString()}</strong> accounts requiring or carrying a next action</div><span>Overdue first · then due today · scheduled · active status without a date</span></div>{actionRows.length === 0 ? <div className="empty-state"><strong>No action items match these filters.</strong><span>Set a workflow status or next-action date from an account profile.</span></div> : <div className="table-scroll"><table className="workflow-command-table workflow-actions-table"><thead><tr><th>Next action</th><th>Account</th><th>Status</th><th>Priority</th><th>Changes · 7d</th><th>Private note</th><th>Watchlists</th><th aria-label="Open account" /></tr></thead><tbody>{visibleActions.map(row => { const account = accountById.get(row.system_id); const state = dueState(account, today); const names = (membershipIdsBySystem.get(row.system_id) ?? []).map(id => watchlistById.get(id)).filter((name): name is string => Boolean(name)); return <tr key={row.system_id} className={selectedId === row.system_id ? 'selected-row' : ''} onClick={() => setSelectedId(row.system_id)}><td>{account?.next_action_date ? <><strong className={state === 'overdue' || state === 'today' ? 'due-date' : ''}>{formatDate(account.next_action_date)}</strong><small>{state === 'overdue' ? 'Overdue' : state === 'today' ? 'Due today' : 'Scheduled'}</small></> : <span className="workflow-needs-date">Needs date</span>}</td><td className="account-cell"><strong>{row.address ?? row.system_id}</strong><span>{[row.borough, row.zip].filter(Boolean).join(' · ') || '—'}</span></td><td><span className="status-chip">{statusLabel(account?.status)}</span></td><td><span className={row.priority_score >= 70 ? 'priority-text-high' : ''}>P{row.priority_score}</span></td><td>{eventsBySystem.get(row.system_id)?.length ?? 0}</td><td className="workflow-action-note">{account?.note || <span className="muted-copy">No note</span>}</td><td>{names.length ? <div className="workflow-mini-tags">{names.slice(0, 2).map(name => <span key={name}>{name}</span>)}{names.length > 2 && <span>+{names.length - 2}</span>}</div> : <span className="muted-copy">—</span>}</td><td className="row-arrow"><button className="table-link" onClick={event => { event.stopPropagation(); onOpenAccount(row) }}>›</button></td></tr> })}</tbody></table></div>}<div className="pagination"><button disabled={activeActionPage === 0} onClick={() => setActionPage(current => Math.max(0, current - 1))}>Previous</button><span>Page {activeActionPage + 1} of {actionMaxPage + 1}</span><button disabled={activeActionPage === actionMaxPage} onClick={() => setActionPage(current => Math.min(actionMaxPage, current + 1))}>Next</button></div></div>}
    </div>

    <aside className="workflow-account-inspector" aria-live="polite">{selectedRow ? <><div className="workflow-inspector-head"><div><span className="page-kicker">Selected account</span><strong>{selectedRow.address ?? selectedRow.system_id}</strong><small>{[selectedRow.borough, selectedRow.zip].filter(Boolean).join(' · ') || selectedRow.system_id}</small></div><span className={`workflow-inspector-score ${selectedRow.priority_score >= 70 ? 'high' : ''}`}>P{selectedRow.priority_score}</span></div><div className="workflow-inspector-signals"><span className={`signal signal-${selectedRow.primary_signal.toLowerCase()}`}>{signalLabel(selectedRow.primary_signal)}</span>{dueState(selectedAccount, today) === 'overdue' && <span className="workflow-alert-chip">Overdue</span>}{dueState(selectedAccount, today) === 'today' && <span className="workflow-alert-chip">Due today</span>}{selectedEvents.length > 0 && <span>{selectedEvents.length} change{selectedEvents.length === 1 ? '' : 's'} · 7d</span>}{selectedRow.recent_confirmed_violation && <span className="workflow-alert-chip">Recent violation</span>}</div><dl className="workflow-inspector-facts"><div><dt>Status</dt><dd>{statusLabel(selectedAccount?.status)}</dd></div><div><dt>Next action</dt><dd>{selectedAccount?.next_action_date ? formatDate(selectedAccount.next_action_date) : selectedAccount && ACTION_STATUSES.has(selectedAccount.status) ? 'Needs date' : 'None'}</dd></div><div><dt>Equipment</dt><dd>{selectedRow.active_equipment} active</dd></div><div><dt>Latest sample</dt><dd>{selectedRow.latest_sample_date ? formatDate(selectedRow.latest_sample_date) : 'No public date'}</dd></div><div><dt>HPD contacts</dt><dd>{selectedRow.hpd_contact_count ?? 0}</dd></div><div><dt>Recent DOB</dt><dd>{selectedRow.dob_recent_activity_count ?? 0}</dd></div><div><dt>Watchlists</dt><dd>{selectedWatchlists.length ? selectedWatchlists.join(', ') : 'None'}</dd></div></dl>{selectedAccount?.note && <div className="workflow-inspector-note"><span>Private note</span><p>{selectedAccount.note}</p></div>}<button className="primary workflow-open-full" onClick={() => onOpenAccount(selectedRow)}>Open account to manage →</button><p className="workflow-inspector-boundary">Status, notes, next-action date and watchlist edits remain on the account workflow control so there is one verified persistence path.</p></> : <div className="workflow-inspector-empty"><span className="page-kicker">Account inspector</span><strong>Select any account, change or action</strong><p>Keep the portfolio in context, then open only the account you need to edit or inspect in full.</p></div>}</aside>
    </div>

    <details className="workflow-command-toolbox"><summary><div><strong>Saved views & watchlists</strong><span>{savedViews.length} saved prospect view{savedViews.length === 1 ? '' : 's'} · {watchlists.length} watchlist{watchlists.length === 1 ? '' : 's'}</span></div><span>Expand</span></summary><div className="workflow-command-toolbox-grid"><section><span className="page-kicker">Saved prospect views</span>{savedViews.length ? <div className="workflow-toolbox-list">{savedViews.slice(0, 20).map(view => <span key={view.id}>▤ {view.name}</span>)}</div> : <p>No saved prospect views yet.</p>}</section><section><span className="page-kicker">Private watchlists</span>{watchlists.length ? <div className="workflow-toolbox-list">{watchlists.map(watchlist => <button key={watchlist.id} onClick={() => { setWatchlistFilter(watchlist.id); setTab('accounts') }}>★ {watchlist.name}<strong>{watchlistCounts.get(watchlist.id) ?? 0}</strong></button>)}</div> : <p>No private watchlists yet.</p>}</section></div></details>
  </section>
}
