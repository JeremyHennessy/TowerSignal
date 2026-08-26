import { type FormEvent } from 'react'
import type { WorkflowUser } from '../types/workflow'
import { WorkflowAuthPanel } from './WorkflowAuthPanel'

export type WorkspaceMode = 'prospect' | 'monitor' | 'map' | 'nys' | 'nys-changes' | 'opportunities' | 'portfolios' | 'workflow' | 'source-health' | 'account'

const navigation: Array<{ mode: WorkspaceMode; label: string }> = [
  { mode: 'prospect', label: 'Prospect' },
  { mode: 'monitor', label: 'Monitor' },
  { mode: 'map', label: 'Map' },
  { mode: 'nys', label: 'NYS Market' },
  { mode: 'nys-changes', label: 'NYS Changes' },
  { mode: 'opportunities', label: 'Opportunities' },
  { mode: 'portfolios', label: 'Portfolios' },
  { mode: 'workflow', label: 'Workflow' },
]

export function TopNavigation({
  mode,
  onNavigate,
  search,
  onSearchChange,
  onSearchSubmit,
  healthySources,
  sourceCount,
  user,
  authLoading,
  authBusy,
  authError,
  onSignIn,
  onSignUp,
  onSignOut,
}: {
  mode: WorkspaceMode
  onNavigate: (mode: WorkspaceMode) => void
  search: string
  onSearchChange: (value: string) => void
  onSearchSubmit: () => void
  healthySources: number
  sourceCount: number
  user: WorkflowUser | null
  authLoading: boolean
  authBusy: boolean
  authError: string | null
  onSignIn: (email: string, password: string) => Promise<void>
  onSignUp: (email: string, password: string) => Promise<void>
  onSignOut: () => Promise<void>
}) {
  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSearchSubmit()
  }

  return <header className="reference-top-nav">
    <button className="reference-brand" onClick={() => onNavigate('prospect')} aria-label="TowerSignal home"><span className="reference-brand-mark">TS</span><strong>TowerSignal</strong></button>
    <nav aria-label="TowerSignal workspace">{navigation.map(item => <button key={item.mode} className={mode === item.mode || (mode === 'account' && item.mode === 'prospect') ? 'active' : ''} onClick={() => onNavigate(item.mode)}>{item.label}</button>)}</nav>
    <div className="reference-nav-tools">
      <form className="global-account-search" onSubmit={submit}><span aria-hidden="true">⌕</span><input aria-label="Search accounts or locations" value={search} onChange={event => onSearchChange(event.target.value)} placeholder="Search accounts or locations" /></form>
      <button className={`source-health-nav-button ${mode === 'source-health' ? 'active' : ''}`} onClick={() => onNavigate('source-health')} aria-label="Source Health & Coverage" title="Source Health & Coverage"><span className="status-dot" /><span className="source-health-nav-label">{healthySources}/{sourceCount || '—'}</span></button>
      <WorkflowAuthPanel user={user} loading={authLoading} busy={authBusy} error={authError} onSignIn={onSignIn} onSignUp={onSignUp} onSignOut={onSignOut} />
    </div>
  </header>
}
