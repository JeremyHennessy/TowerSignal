import type { SystemSummary } from '../types/data'
import type { AccountDisposition, WorkflowAccountState, WorkflowMembership, WorkflowSavedView, WorkflowUser, WorkflowWatchlist } from '../types/workflow'
import { formatDate } from '../domain/labels'
import { ShareButton } from './ShareButton'

const columns: Array<{ value: AccountDisposition; label: string }> = [
  { value: 'new', label: 'New' },
  { value: 'investigate', label: 'Investigate' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'follow-up', label: 'Follow-up' },
  { value: 'monitor', label: 'Monitor' },
  { value: 'dismissed', label: 'Dismissed' },
]

const number = new Intl.NumberFormat('en-US')

export function WorkflowWorkspacePage({
  user,
  systems,
  accounts,
  watchlists,
  memberships,
  savedViews,
  onOpenAccount,
}: {
  user: WorkflowUser | null
  systems: SystemSummary[]
  accounts: WorkflowAccountState[]
  watchlists: WorkflowWatchlist[]
  memberships: WorkflowMembership[]
  savedViews: WorkflowSavedView[]
  onOpenAccount: (row: SystemSummary) => void
}) {
  const byId = new Map(systems.map(row => [row.system_id, row]))
  const membershipCounts = new Map<string, number>()
  memberships.forEach(item => membershipCounts.set(item.watchlist_id, (membershipCounts.get(item.watchlist_id) ?? 0) + 1))
  const today = new Date().toISOString().slice(0, 10)
  const due = accounts.filter(account => account.next_action_date && account.next_action_date <= today).sort((a, b) => String(a.next_action_date).localeCompare(String(b.next_action_date)))
  const upcoming = accounts.filter(account => account.next_action_date).sort((a, b) => String(a.next_action_date).localeCompare(String(b.next_action_date))).slice(0, 12)
  const watchedIds = new Set(memberships.map(item => item.system_id))

  return <section className="product-page workflow-workspace-page">
    <div className="product-page-heading">
      <div><span className="page-kicker">New York City · private workspace</span><h1>Workflow workspace <span className="private-chip">Private</span></h1><p>Saved views, watchlists, account disposition, notes and next actions remain separate from public-source evidence.</p></div>
      <div className="page-actions"><ShareButton label="Share public page link" /></div>
    </div>

    {!user && <div className="workflow-login-callout"><div><span className="roadmap-status">PRIVATE WORKSPACE</span><strong>Sign in from the profile control to sync workflow state across sessions and devices.</strong><p>Your existing browser-local saved views remain available. Account notes, status and watchlists require an authenticated private workspace.</p></div></div>}

    <div className="reference-metric-grid workflow-metrics">
      <article><span className="reference-metric-icon success">★</span><div><small>Watched accounts</small><strong>{number.format(watchedIds.size)}</strong><span>Across {watchlists.length} watchlists</span></div></article>
      <article><span className="reference-metric-icon">◎</span><div><small>Workflow accounts</small><strong>{number.format(accounts.length)}</strong><span>Accounts with saved state</span></div></article>
      <article><span className="reference-metric-icon urgent">!</span><div><small>Due / overdue</small><strong>{number.format(due.length)}</strong><span>Next-action date today or earlier</span></div></article>
      <article><span className="reference-metric-icon warning">▤</span><div><small>Saved views</small><strong>{number.format(savedViews.length)}</strong><span>Repeat prospecting criteria</span></div></article>
    </div>

    <div className="workflow-reference-layout">
      <aside className="workflow-reference-sidebar">
        <section><div className="workflow-sidebar-heading"><span className="page-kicker">Saved views</span><strong>{savedViews.length}</strong></div>{savedViews.length === 0 ? <p>No saved views yet.</p> : savedViews.slice(0, 12).map(view => <div className="workflow-sidebar-row" key={view.id}><span>▤</span><strong>{view.name}</strong></div>)}</section>
        <section><div className="workflow-sidebar-heading"><span className="page-kicker">Watchlists</span><strong>{watchlists.length}</strong></div>{watchlists.length === 0 ? <p>Sign in to create private watchlists.</p> : watchlists.map(watchlist => <div className="workflow-sidebar-row" key={watchlist.id}><span>★</span><strong>{watchlist.name}</strong><small>{membershipCounts.get(watchlist.id) ?? 0}</small></div>)}</section>
      </aside>

      <div className="workflow-reference-main">
        <div className="kanban-heading"><div><h2>Accounts by status</h2><p>Current private disposition state. Public timing scores remain unchanged by workflow status.</p></div></div>
        <div className="workflow-kanban">{columns.map(column => {
          const items = accounts.filter(account => account.status === column.value)
          return <section key={column.value} className="kanban-column"><header><span className={`kanban-dot kanban-${column.value}`} />{column.label}<strong>{items.length}</strong></header><div>{items.slice(0, 6).map(account => {
            const row = byId.get(account.system_id)
            return <article key={account.system_id} className="kanban-card" onClick={() => row && onOpenAccount(row)}><strong>{row?.address ?? account.system_id}</strong><span>{row ? [row.borough, row.zip].filter(Boolean).join(' · ') : 'Account not present in current public snapshot'}</span>{account.note && <p>{account.note}</p>}<footer>{row && <span className={row.priority_score >= 70 ? 'priority-text-high' : ''}>P{row.priority_score}</span>}<span>{account.next_action_date ? formatDate(account.next_action_date) : 'No next action'}</span></footer></article>
          })}{items.length > 6 && <button className="kanban-more">+ {items.length - 6} more</button>}</div></section>
        })}</div>

        <div className="reference-table-card workflow-followups">
          <div className="reference-table-heading"><div><strong>Next actions</strong><span>{upcoming.length === 0 ? 'No dated next actions saved' : 'Earliest saved actions'}</span></div></div>
          {upcoming.length === 0 ? <div className="reference-empty-state compact"><span>Add a status, note and next-action date from any account profile.</span></div> : <div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Account</th><th>Status</th><th>Note</th><th>Next action</th><th>Action</th></tr></thead><tbody>{upcoming.map(account => {
            const row = byId.get(account.system_id)
            return <tr key={account.system_id}><td><strong>{row?.address ?? account.system_id}</strong><small>{row ? [row.borough, row.zip].filter(Boolean).join(' · ') : account.system_id}</small></td><td><span className="status-chip">{account.status}</span></td><td>{account.note || '—'}</td><td className={account.next_action_date && account.next_action_date <= today ? 'due-date' : ''}>{account.next_action_date ? formatDate(account.next_action_date) : '—'}</td><td>{row ? <button className="table-link" onClick={() => onOpenAccount(row)}>Open →</button> : 'Unavailable'}</td></tr>
          })}</tbody></table></div>}
        </div>
      </div>
    </div>
  </section>
}
