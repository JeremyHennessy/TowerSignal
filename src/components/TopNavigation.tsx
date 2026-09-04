import { useEffect, useState, type FormEvent } from 'react'
import type { WorkflowUser } from '../types/workflow'
import { ShareButton } from './ShareButton'

export type WorkspaceMode = 'prospect' | 'monitor' | 'map' | 'nys' | 'nys-changes' | 'toronto' | 'opportunities' | 'companies' | 'portfolios' | 'workflow' | 'source-health' | 'account'

const TORONTO_PREVIEW = import.meta.env.VITE_TORONTO_PREVIEW === 'true'
const NEW_YORK_APP_URL = 'https://jeremyhennessy.github.io/TowerSignal/'

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

export const TORONTO_PREVIEW_NAVIGATION = [
  { route: 'prospect', label: 'Prospect' },
  { route: 'monitor', label: 'Monitor' },
  { route: 'map', label: 'Map' },
  { route: 'market', label: 'Toronto Market' },
  { route: 'changes', label: 'Toronto Changes' },
  { route: 'opportunities', label: 'Opportunities' },
  { route: 'companies', label: 'Companies' },
  { route: 'portfolios', label: 'Portfolios' },
  { route: 'workflow', label: 'Workflow' },
] as const

type TorontoPreviewRoute = 'home' | typeof TORONTO_PREVIEW_NAVIGATION[number]['route'] | 'source-health' | 'benchmarking' | 'property' | 'company' | 'portfolio'
const TORONTO_PREVIEW_ROUTES = new Set<TorontoPreviewRoute>(['home', 'source-health', 'benchmarking', 'property', 'company', 'portfolio', ...TORONTO_PREVIEW_NAVIGATION.map(item => item.route)])

function currentTorontoPreviewRoute(): TorontoPreviewRoute {
  const parts = window.location.hash.replace(/^#\/?/, '').split('?')[0].split('/').filter(Boolean)
  const candidate = parts[0] === 'toronto' ? parts[1] : null
  if (!candidate) return 'home'
  return TORONTO_PREVIEW_ROUTES.has(candidate as TorontoPreviewRoute) ? candidate as TorontoPreviewRoute : 'market'
}

function goToronto(route: TorontoPreviewRoute) {
  window.location.hash = `#/toronto/${route}`
}

function TowerSignalMark() {
  return <svg className="reference-brand-antenna" viewBox="0 0 28 32" aria-hidden="true">
    <circle cx="14" cy="9" r="2.2" />
    <path d="M14 12v16M10.5 28h7M11.5 20h5M9.5 25h9" />
    <path d="M8.5 15.5a9 9 0 0 1 0-13M19.5 2.5a9 9 0 0 1 0 13" />
    <path d="M5 19a14 14 0 0 1 0-20M23-1a14 14 0 0 1 0 20" />
  </svg>
}

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
  torontoEnabled,
}: {
  mode: WorkspaceMode
  onNavigate: (mode: WorkspaceMode) => void
  search: string
  onSearchChange: (value: string) => void
  onSearchSubmit: () => void
  healthySources: number
  sourceCount: number
  user: WorkflowUser | null
  torontoEnabled: boolean
  authLoading: boolean
  authBusy: boolean
  authError: string | null
  onSignIn: (email: string, password: string) => Promise<void>
  onSignUp: (email: string, password: string) => Promise<void>
  onSignOut: () => Promise<void>
}) {
  const [torontoRoute, setTorontoRoute] = useState<TorontoPreviewRoute>(() => currentTorontoPreviewRoute())

  useEffect(() => {
    if (!TORONTO_PREVIEW) return
    const sync = () => setTorontoRoute(currentTorontoPreviewRoute())
    sync()
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])

  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (TORONTO_PREVIEW) {
      const term = search.trim()
      window.location.hash = term ? `#/toronto/prospect?search=${encodeURIComponent(term)}` : '#/toronto/prospect'
      return
    }
    onSearchSubmit()
  }

  if (TORONTO_PREVIEW) return <header className="reference-top-nav">
    <style>{'.toronto-filters > *{min-width:0}.toronto-filters input,.toronto-filters select{width:100%;min-width:0;box-sizing:border-box}'}</style>
    <button className="reference-brand" onClick={() => goToronto('home')} aria-label="TowerSignal Toronto home"><span className="reference-brand-mark"><TowerSignalMark /></span><strong>TowerSignal</strong></button>
    <nav aria-label="TowerSignal Toronto workspace">
      <button className={torontoRoute === 'home' ? 'active' : ''} onClick={() => goToronto('home')}>Home</button>
      {TORONTO_PREVIEW_NAVIGATION.map(item => <button key={item.route} className={torontoRoute === item.route || (item.route === 'prospect' && torontoRoute === 'property') || (item.route === 'companies' && torontoRoute === 'company') || (item.route === 'portfolios' && torontoRoute === 'portfolio') ? 'active' : ''} onClick={() => goToronto(item.route)}>{item.label}</button>)}
    </nav>
    <div className="reference-nav-tools">
      <select className="toronto-market-select" aria-label="Market" value="toronto" onChange={event => {
        if (event.target.value === 'nyc') window.location.assign(NEW_YORK_APP_URL)
        if (event.target.value === 'nys') window.location.assign(`${NEW_YORK_APP_URL}#/nys`)
      }}><option value="toronto">Toronto</option><option value="nyc">New York City</option><option value="nys">New York State</option></select>
      <form className="global-account-search" onSubmit={submit}><span aria-hidden="true">⌕</span><input aria-label="Search accounts or locations" value={search} onChange={event => onSearchChange(event.target.value)} placeholder="Search accounts or locations" /></form>
      <ShareButton label="Share" className="global-share-button" />
      <button className={`source-health-nav-button ${torontoRoute === 'source-health' ? 'active' : ''}`} onClick={() => goToronto('source-health')} aria-label="Source Health & Coverage" title="Source Health & Coverage"><span className="status-dot" /><span className="source-health-nav-label">Sources</span></button>
      <button className="workflow-profile-trigger" aria-label="Open Toronto workflow" title="Toronto workflow" onClick={() => goToronto('workflow')}><span>TS</span></button>
    </div>
  </header>

  return <header className="reference-top-nav">
    <button className="reference-brand" onClick={() => goPortal('#/home')} aria-label="TowerSignal home"><span className="reference-brand-mark"><TowerSignalMark /></span><strong>TowerSignal</strong></button>
    <nav aria-label="TowerSignal workspace"><button onClick={() => goPortal('#/home')}>Home</button>{navigation.map(item => <button key={item.mode} className={mode === item.mode || (mode === 'account' && item.mode === 'prospect') ? 'active' : ''} onClick={() => onNavigate(item.mode)}>{item.label}</button>)}</nav>
    <div className="reference-nav-tools">
      {torontoEnabled && <select className="toronto-market-select" aria-label="Market" value={mode === 'toronto' ? 'toronto' : mode === 'nys' || mode === 'nys-changes' ? 'nys' : 'nyc'} onChange={event => onNavigate(event.target.value === 'toronto' ? 'toronto' : event.target.value === 'nys' ? 'nys' : 'prospect')}><option value="nyc">New York City</option><option value="nys">New York State</option><option value="toronto">Toronto Beta</option></select>}
      <form className="global-account-search" onSubmit={submit}><span aria-hidden="true">⌕</span><input aria-label="Search accounts or locations" value={search} onChange={event => onSearchChange(event.target.value)} placeholder="Search accounts or locations" /></form>
      <ShareButton label="Share" className="global-share-button" />
      <button className={`source-health-nav-button ${mode === 'source-health' ? 'active' : ''}`} onClick={() => onNavigate('source-health')} aria-label="Source Health & Coverage" title="Source Health & Coverage"><span className="status-dot" /><span className="source-health-nav-label">{healthySources}/{sourceCount || '—'}</span></button>
      <button className="workflow-profile-trigger" aria-label="Open TowerSignal account" title={user?.email || 'TowerSignal account'} onClick={() => goPortal('#/my-account')}><span>{initials(user)}</span></button>
    </div>
  </header>
}
