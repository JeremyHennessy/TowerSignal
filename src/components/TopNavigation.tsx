import { useEffect, useState, type FormEvent } from 'react'
import type { WorkflowUser } from '../types/workflow'
import { ShareButton } from './ShareButton'

export type WorkspaceMode = 'prospect' | 'monitor' | 'map' | 'nys' | 'nys-changes' | 'opportunities' | 'companies' | 'water-quality' | 'portfolios' | 'workflow' | 'source-health' | 'account'

type NavigationItem = { mode: WorkspaceMode; label: string }

const logoAsset = `${import.meta.env.BASE_URL}marketing/towersignal-logo.webp`

const primaryNavigation: NavigationItem[] = [
  { mode: 'prospect', label: 'Prospect' },
  { mode: 'monitor', label: 'Monitor' },
  { mode: 'map', label: 'Map' },
  { mode: 'opportunities', label: 'Opportunities' },
  { mode: 'nys', label: 'NYS Market' },
]

const secondaryNavigation: NavigationItem[] = [
  { mode: 'nys-changes', label: 'NYS Changes' },
  { mode: 'companies', label: 'Companies' },
  { mode: 'water-quality', label: 'Water Quality' },
  { mode: 'portfolios', label: 'Portfolios' },
  { mode: 'workflow', label: 'Workflow' },
]

const allNavigation = [...primaryNavigation, ...secondaryNavigation]

function initials(user: WorkflowUser | null): string {
  if (!user) return 'TS'
  const source = user.name?.trim() || user.email.split('@')[0] || 'TS'
  const parts = source.split(/[\s._-]+/).filter(Boolean)
  return (parts.length > 1 ? `${parts[0][0]}${parts[1][0]}` : source.slice(0, 2)).toUpperCase()
}

function goPortal(hash: '#/home' | '#/my-account') {
  window.location.hash = hash
}

function currentWorkspaceLabel(mode: WorkspaceMode): string {
  if (mode === 'account') return 'Account'
  if (mode === 'source-health') return 'Source Health'
  return allNavigation.find(item => item.mode === mode)?.label ?? 'Workspace'
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
  const [moreOpen, setMoreOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setMoreOpen(false)
      setMobileMenuOpen(false)
      setMobileSearchOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setMobileSearchOpen(false)
    onSearchSubmit()
  }

  const navigate = (item: NavigationItem) => {
    setMoreOpen(false)
    setMobileMenuOpen(false)
    setMobileSearchOpen(false)
    onNavigate(item.mode)
  }

  const goHome = () => {
    setMoreOpen(false)
    setMobileMenuOpen(false)
    setMobileSearchOpen(false)
    goPortal('#/home')
  }

  const primaryActive = (item: NavigationItem) => mode === item.mode || (mode === 'account' && item.mode === 'prospect')
  const overflowActive = secondaryNavigation.find(item => item.mode === mode)
  const currentLabel = currentWorkspaceLabel(mode)

  return <header className="reference-top-nav">
    <button className="reference-brand" onClick={goHome} aria-label="TowerSignal home"><img src={logoAsset} alt="TowerSignal" /></button>

    <nav className="reference-desktop-nav" aria-label="TowerSignal workspace">
      <button onClick={goHome}>Home</button>
      {primaryNavigation.map(item => <button key={item.mode} className={primaryActive(item) ? 'active' : ''} onClick={() => navigate(item)}>{item.label}</button>)}
      {overflowActive && <button className="active reference-overflow-active" onClick={() => navigate(overflowActive)}>{overflowActive.label}</button>}
      <div className={`reference-more-menu ${moreOpen ? 'open' : ''}`}>
        <button className={overflowActive ? 'has-active' : ''} aria-haspopup="menu" aria-expanded={moreOpen} onClick={() => setMoreOpen(value => !value)}>More <span aria-hidden="true">⌄</span></button>
        {moreOpen && <div className="reference-more-popover" role="menu">
          {secondaryNavigation.map(item => <button key={item.mode} role="menuitem" className={mode === item.mode ? 'active' : ''} onClick={() => navigate(item)}>{item.label}</button>)}
        </div>}
      </div>
    </nav>

    <span className="reference-mobile-current" aria-label={`Current workspace: ${currentLabel}`}>{currentLabel}</span>

    <div className="reference-nav-tools">
      <form className="global-account-search reference-desktop-search" onSubmit={submit}><span aria-hidden="true">⌕</span><input aria-label="Search accounts or locations" value={search} onChange={event => onSearchChange(event.target.value)} placeholder="Search accounts or locations" /></form>
      <ShareButton label="Share" className="global-share-button reference-desktop-share" />
      <button className={`source-health-nav-button reference-desktop-health ${mode === 'source-health' ? 'active' : ''}`} onClick={() => onNavigate('source-health')} aria-label="Source Health & Coverage" title="Source Health & Coverage"><span className="status-dot" /><span className="source-health-nav-label">{healthySources}/{sourceCount || '—'}</span></button>
      <button className="reference-mobile-search-trigger" aria-label="Search accounts" aria-expanded={mobileSearchOpen} onClick={() => { setMobileSearchOpen(value => !value); setMobileMenuOpen(false) }}>⌕</button>
      <button className="reference-mobile-menu-trigger" aria-label="Open workspace menu" aria-expanded={mobileMenuOpen} onClick={() => { setMobileMenuOpen(value => !value); setMobileSearchOpen(false) }}>☰</button>
      <button className="workflow-profile-trigger" aria-label="Open TowerSignal account" title={user?.email || 'TowerSignal account'} onClick={() => goPortal('#/my-account')}><span>{initials(user)}</span></button>
    </div>

    {mobileSearchOpen && <form className="reference-mobile-search-panel" onSubmit={submit}>
      <input autoFocus aria-label="Search accounts or locations" value={search} onChange={event => onSearchChange(event.target.value)} placeholder="Account, address or location" />
      <button type="submit">Search</button>
    </form>}

    {mobileMenuOpen && <div className="reference-mobile-workspace-menu" role="dialog" aria-label="TowerSignal workspace menu">
      <div className="reference-mobile-menu-heading"><div><small>Current workspace</small><strong>{currentLabel}</strong></div><button aria-label="Close workspace menu" onClick={() => setMobileMenuOpen(false)}>×</button></div>
      <nav aria-label="All TowerSignal workspaces">
        <button className="mobile-home-link" onClick={goHome}>Home</button>
        {allNavigation.map(item => <button key={item.mode} className={primaryActive(item) || mode === item.mode ? 'active' : ''} onClick={() => navigate(item)}><span>{item.label}</span>{(primaryActive(item) || mode === item.mode) && <small>Current</small>}</button>)}
      </nav>
      <div className="reference-mobile-menu-tools">
        <button className={mode === 'source-health' ? 'active' : ''} onClick={() => { setMobileMenuOpen(false); onNavigate('source-health') }}><span>Source Health & Coverage</span><strong>{healthySources}/{sourceCount || '—'}</strong></button>
        <ShareButton label="Share current view" />
      </div>
    </div>}
  </header>
}
