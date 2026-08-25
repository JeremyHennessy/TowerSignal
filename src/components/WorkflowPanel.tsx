import { useState } from 'react'
import type { WorkflowUser, WorkflowWatchlist } from '../types/workflow'

export function WorkflowPanel({
  user,
  watchlists,
  watchedSystemIds,
  memberships,
  watchedOnly,
  busy,
  onToggleWatchedOnly,
  onCreateWatchlist,
  onDeleteWatchlist,
  onExport,
}: {
  user: WorkflowUser | null
  watchlists: WorkflowWatchlist[]
  watchedSystemIds: Set<string>
  memberships: Array<{ watchlist_id: string; system_id: string }>
  watchedOnly: boolean
  busy: boolean
  onToggleWatchedOnly: () => void
  onCreateWatchlist: (name: string) => Promise<void>
  onDeleteWatchlist: (id: string) => Promise<void>
  onExport: () => void
}) {
  const [name, setName] = useState('')

  if (!user) return <section className="workflow-panel"><div className="section-title"><div><span className="eyebrow">Workflow</span><h3>Account watchlists</h3></div><span>—</span></div><p>Public intelligence remains available without a login. Use <strong>Sync workflow</strong> above when you want cross-device watchlists, notes and next actions.</p></section>

  const create = async () => {
    const value = name.trim()
    if (!value) return
    await onCreateWatchlist(value)
    setName('')
  }

  return <section className="workflow-panel">
    <div className="section-title"><div><span className="eyebrow">Workflow</span><h3>Account watchlists</h3></div><span>{watchedSystemIds.size}</span></div>
    <button className={watchedOnly ? 'workflow-filter active' : 'workflow-filter'} onClick={onToggleWatchedOnly}>{watchedOnly ? 'Showing watched accounts' : 'Show watched accounts only'}</button>
    <div className="watchlist-create"><input aria-label="New watchlist name" value={name} onChange={event => setName(event.target.value)} placeholder="e.g. Manhattan Q4" /><button disabled={busy || !name.trim()} onClick={() => void create()}>Add</button></div>
    <div className="watchlist-list">{watchlists.map(watchlist => {
      const count = memberships.filter(item => item.watchlist_id === watchlist.id).length
      return <div key={watchlist.id}><span><strong>{watchlist.name}</strong><small>{count} account{count === 1 ? '' : 's'}</small></span>{watchlists.length > 1 && <button aria-label={`Delete ${watchlist.name}`} disabled={busy} onClick={() => void onDeleteWatchlist(watchlist.id)}>×</button>}</div>
    })}</div>
    <button className="workflow-export" disabled={watchedSystemIds.size === 0} onClick={onExport}>Export workflow for CRM</button>
    <p className="microcopy">Watchlists and account state are private workflow records. Public evidence and scoring remain unchanged.</p>
  </section>
}
