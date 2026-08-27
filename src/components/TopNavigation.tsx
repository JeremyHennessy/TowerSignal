import { type FormEvent } from 'react'
import type { WorkflowUser } from '../types/workflow'
import { ShareButton } from './ShareButton'
import { WorkflowAuthPanel } from './WorkflowAuthPanel'

export type WorkspaceMode = 'prospect' | 'monitor' | 'map' | 'nys' | 'nys-changes' | 'opportunities' | 'companies' | 'portfolios' | 'workflow' | 'source-health' | 'account'

const navigation: Array<{ mode: WorkspaceMode; label: string }> = [
  { mode: 'prospect', label: 'Prospect' },
  { mode: 'monitor', label: 'Monitor' },
  { mode: 'map', label: 'Map' },
  { mode: 'nys', label: 'NYS Market' },
  { mode: 'nys-changes', label: 'NYS Changes' },
  { mode: 'opportunities', label: 'Opportunities' },
  { mode: 'companies', label: 'Companies' },
  { mode: 'portfolios', label: 'Portfolios' },
  { mode: 'workflow', label: 'Workflow' },
]

function TowerSignalMark() {
  return <svg className="reference-brand-antenna" viewBox="0 0 28 32" aria-hidden="true">
    <circle cx="14" cy="9" r="2.2" />
    <path d="M14 12v16M10.5 28h7M11.5 20h5M9.5 25h9" />
    <path d="M8.5 15.5a9 9 0 0 1 0-13M19.5 2.5a9 9 0 0 1 0 13" />
    <path d="M5 19a14 14 0 0 1 0-20M23-1a14 14 0 0 1 0 20" />
  </svg>
}

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
    <button className="reference-brand" onClick={() => onNavigate('prospect')} aria-label="TowerSignal home"><span className="reference-brand-mark"><TowerSignalMark /></span><strong>TowerSignal</strong></button>
    <nav aria-label="TowerSignal workspace">{navigation.map(item => <button key={item.mode} className={mode === item.mode || (mode === 'account' && item.mode === 'prospect') ? 'active' : ''} onClick={() => onNavigate(item.mode)}>{item.label}</button>)}</nav>
    <div className="reference-nav-tools">
      <form className="global-account-search" onSubmit={submit}><span aria-hidden="true">⌕</span><input aria-label="Search accounts or locations" value={search} onChange={event => onSearchChange(event.target.value)} placeholder="Search accounts or locations" /></form>
      <ShareButton label="Share" className="global-share-button" />
      <button className={`source-health-nav-button ${mode === 'source-health' ? 'active' : ''}`} onClick={() => onNavigate('source-health')} aria-label="Source Health & Coverage" title="Source Health & Coverage"><span className="status-dot" /><span className="source-health-nav-label">{healthySources}/{sourceCount || '—'}</span></button>
      <WorkflowAuthPanel user={user} loading={authLoading} busy={authBusy} error={authError} onSignIn={onSignIn} onSignUp={onSignUp} onSignOut={onSignOut} />
    </div>
  </header>
}