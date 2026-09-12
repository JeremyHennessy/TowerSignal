import { useEffect, useState } from 'react'
import type { AccountDisposition, WorkflowAccountPatch, WorkflowAccountState, WorkflowWatchlist } from '../types/workflow'
import type { WorkflowSaveResult } from '../workflow/useWorkflow'

const statusOptions: Array<{ value: AccountDisposition; label: string }> = [
  { value: 'new', label: 'New' },
  { value: 'investigate', label: 'Investigate' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'follow-up', label: 'Follow-up' },
  { value: 'monitor', label: 'Monitor' },
  { value: 'dismissed', label: 'Dismissed' },
]

function initialPatch(account: WorkflowAccountState | undefined): WorkflowAccountPatch {
  return {
    status: account?.status ?? 'new',
    note: account?.note ?? '',
    next_action_date: account?.next_action_date ?? null,
  }
}

export function WorkflowQuickEditor({
  systemId,
  account,
  watchlists,
  membershipIds,
  busy,
  onSave,
  onToggleMembership,
}: {
  systemId: string
  account?: WorkflowAccountState
  watchlists: WorkflowWatchlist[]
  membershipIds: ReadonlySet<string>
  busy: boolean
  onSave: (systemId: string, patch: WorkflowAccountPatch) => Promise<WorkflowSaveResult>
  onToggleMembership: (systemId: string, watchlistId: string, enabled: boolean) => Promise<void>
}) {
  const [draft, setDraft] = useState<WorkflowAccountPatch>(() => initialPatch(account))
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    setDraft(initialPatch(account))
    setMessage(null)
  }, [account, systemId])

  const save = async () => {
    const result = await onSave(systemId, draft)
    setMessage(result === 'synced' ? 'Saved and synced.' : 'Saved in this tab; cross-device sync was not confirmed.')
  }

  return <div className="workflow-quick-editor" aria-label="Quick workflow edit">
    <div className="workflow-quick-editor-head"><strong>Quick manage</strong><span>Uses the same verified workflow persistence path as the account page.</span></div>
    <div className="workflow-quick-editor-grid">
      <label>Status<select value={draft.status} onChange={event => setDraft(current => ({ ...current, status: event.target.value as AccountDisposition }))}>{statusOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label>
      <label>Next action<input type="date" value={draft.next_action_date ?? ''} onChange={event => setDraft(current => ({ ...current, next_action_date: event.target.value || null }))} /></label>
    </div>
    <label className="workflow-quick-note">Private note<textarea rows={3} value={draft.note} onChange={event => setDraft(current => ({ ...current, note: event.target.value }))} placeholder="Private account context" /></label>
    {watchlists.length > 0 && <fieldset className="workflow-quick-watchlists"><legend>Watchlists</legend>{watchlists.map(watchlist => <label key={watchlist.id}><input type="checkbox" checked={membershipIds.has(watchlist.id)} disabled={busy} onChange={event => void onToggleMembership(systemId, watchlist.id, event.target.checked)} /><span>{watchlist.name}</span></label>)}</fieldset>}
    <div className="workflow-quick-actions"><button type="button" className="primary" disabled={busy} onClick={() => void save()}>{busy ? 'Saving…' : 'Save workflow'}</button>{draft.next_action_date && <button type="button" disabled={busy} onClick={() => setDraft(current => ({ ...current, next_action_date: null }))}>Clear date</button>}</div>
    {message && <p className="workflow-quick-message">{message}</p>}
  </div>
}
