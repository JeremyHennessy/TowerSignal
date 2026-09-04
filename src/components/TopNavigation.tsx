import { type FormEvent } from 'react'
import type { WorkflowUser } from '../types/workflow'
import { ShareButton } from './ShareButton'

export type WorkspaceMode = 'prospect' | 'monitor' | 'map' | 'nys' | 'nys-changes' | 'opportunities' | 'companies' | 'portfolios' | 'workflow' | 'source-health' | 'account'

const logoAsset = `${import.meta.env.BASE_URL}marketing/towersignal-logo.webp`

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

function initials(user: WorkflowUser | null): string {
  if (!user) return 'TS'
  const source = user.name?.trim() || user.email.split('@')[0] || 'TS'
  const parts = source.split(/[\s._-]+/).filter(Boolean)
  return (parts.length > 1 ? `${parts[0][0]}${parts[1][0]}` : source.slice(0, 2)).toUpperCase()
}

function goPortal(hash: '#/home' | '#/my-account') {
  window.location.hash = hash
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
    <button className="reference-brand" onClick={() => goPortal('#/home')} aria-label="TowerSignal home"><img src={logoAsset} alt="TowerSignal" /></button>
    <nav aria-label="TowerSignal workspace"><button onClick={() => goPortal('#/home')}>Home</button>{navigation.map(item => <button key={item.mode} className={mode === item.mode || (mode === 'account' && item.mode === 'prospect') ? 'active' : ''} onClick={() => onNavigate(item.mode)}>{item.label}</button>)}</nav>
    <div className="reference-nav-tools">
      <form className="global-account-search" onSubmit={submit}><span aria-hidden="true">⌕</span><input aria-label="Search accounts or locations" value={search} onChange={event => onSearchChange(event.target.value)} placeholder="Search accounts or locations" /></form>
      <ShareButton label="Share" className="global-share-button" />
      <button className={`source-health-nav-button ${mode === 'source-health' ? 'active' : ''}`} onClick={() => onNavigate('source-health')} aria-label="Source Health & Coverage" title="Source Health & Coverage"><span className="status-dot" /><span className="source-health-nav-label">{healthySources}/{sourceCount || '—'}</span></button>
      <button className="workflow-profile-trigger" aria-label="Open TowerSignal account" title={user?.email || 'TowerSignal account'} onClick={() => goPortal('#/my-account')}><span>{initials(user)}</span></button>
    </div>
  </header>
}
