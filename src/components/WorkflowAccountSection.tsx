import { useEffect, useState } from 'react'
import type { AccountDisposition, WorkflowAccountPatch, WorkflowAccountState, WorkflowWatchlist } from '../types/workflow'

const STATUS_OPTIONS: Array<{ value: AccountDisposition; label: string }> = [
  { value: 'new', label: 'New' },
  { value: 'investigate', label: 'Investigate' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'follow-up', label: 'Follow-up' },
  { value: 'monitor', label: 'Monitor' },
  { value: 'dismissed', label: 'Dismissed' },
]

const DEFAULT_ACCOUNT: WorkflowAccountPatch = { status: 'new', note: '', next_action_date: null }

export function WorkflowAccountSection({
  signedIn,
  account,
  watchlists,
  membershipIds,
  busy,
  storageMode = 'remote',
  syncWarning,
  onSave,
  onToggleMembership,
}: {
  signedIn: boolean
  account: WorkflowAccountState | undefined
  watchlists: WorkflowWatchlist[]
  membershipIds: Set<string>
  busy: boolean
  storageMode?: 'remote' | 'local' | 'signed-out'
  syncWarning?: string | null
  onSave: (patch: WorkflowAccountPatch) => Promise<void>
  onToggleMembership: (watchlistId: string, enabled: boolean) => Promise<void>
}) {
  const [draft, setDraft] = useState<WorkflowAccountPatch>(DEFAULT_ACCOUNT)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setDraft(account ? { status: account.status, note: account.note, next_action_date: account.next_action_date } : DEFAULT_ACCOUNT)
  }, [account])

  useEffect(() => {
    setSaved(false)
  }, [account?.system_id])

  if (!signedIn) return <section className="workflow-account-section"><div className="workflow-section-heading"><span className="eyebrow">User workflow</span><h3>Account workflow</h3></div><p>Sign in with <strong>Sync workflow</strong> to keep watchlists, disposition, notes and next actions across sessions and devices.</p><p className="microcopy">Workflow state is private user-entered context and is never treated as public-source evidence or scoring input.</p></section>

  const save = async () => {
    setSaved(false)
    try {
      await onSave(draft)
      setSaved(true)
    } catch {
      setSaved(false)
    }
  }

  return <section className="workflow-account-section">
    <div className="workflow-section-heading"><div><span className="eyebrow">User workflow</span><h3>Account workflow</h3></div><div className="workflow-storage-state">{storageMode === 'local' && <span className="workflow-local-badge">On device</span>}{saved && <span className="workflow-saved">Saved</span>}</div></div>
    {storageMode === 'local' && <p className="workflow-local-warning"><strong>On-device workflow.</strong> Private changes in this browser are stored only on this device until secure remote sync is available again.{syncWarning ? ` ${syncWarning}` : ''}</p>}
    <div className="workflow-account-grid">
      <label>Status<select value={draft.status} onChange={event => setDraft(current => ({ ...current, status: event.target.value as AccountDisposition }))}>{STATUS_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
      <label>Next action<input type="date" value={draft.next_action_date ?? ''} onChange={event => setDraft(current => ({ ...current, next_action_date: event.target.value || null }))} /></label>
    </div>
    <label className="workflow-note">Private note<textarea value={draft.note} onChange={event => setDraft(current => ({ ...current, note: event.target.value }))} placeholder="Commercial context, contact outcome, follow-up detail…" rows={4} /></label>
    <div className="workflow-watchlist-picker"><strong>Watchlists</strong>{watchlists.map(watchlist => <label key={watchlist.id}><input type="checkbox" checked={membershipIds.has(watchlist.id)} disabled={busy} onChange={event => void onToggleMembership(watchlist.id, event.target.checked)} />{watchlist.name}</label>)}</div>
    <button className="primary workflow-save" disabled={busy} onClick={() => void save()}>{busy ? 'Saving…' : 'Save workflow state'}</button>
    <p className="microcopy">Disposition, notes, next-action dates and watchlist membership are user-entered commercial workflow state. They do not alter Priority Score 1.0 or any source-backed evidence.</p>
  </section>
}
