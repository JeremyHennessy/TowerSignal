import { useEffect, useState, type FormEvent } from 'react'
import type { WorkflowUser } from '../types/workflow'

const logoAsset = `${import.meta.env.BASE_URL}marketing/towersignal-logo.webp`

type PortalRoute = 'home' | 'my-account'
type PortalNavItem = { label: string; hash: string }

const primaryItems: PortalNavItem[] = [
  { label: 'Prospect', hash: '#/prospect' },
  { label: 'Monitor', hash: '#/monitor' },
  { label: 'Map', hash: '#/map' },
  { label: 'Opportunities', hash: '#/opportunities' },
  { label: 'NYS Market', hash: '#/nys' },
]

const secondaryItems: PortalNavItem[] = [
  { label: 'NYS Changes', hash: '#/nys-changes' },
  { label: 'Companies', hash: '#/companies' },
  { label: 'Water Quality', hash: '#/water-quality' },
  { label: 'Portfolios', hash: '#/portfolios' },
  { label: 'Workflow', hash: '#/workflow' },
  { label: 'Source Health', hash: '#/source-health' },
]

function initials(user: WorkflowUser): string {
  const source = user.name?.trim() || user.email.split('@')[0] || 'TS'
  const parts = source.split(/[\s._-]+/).filter(Boolean)
  return (parts.length > 1 ? `${parts[0][0]}${parts[1][0]}` : source.slice(0, 2)).toUpperCase()
}

export function PortalNavigation({ current, user }: { current: PortalRoute; user: WorkflowUser }) {
  const [moreOpen, setMoreOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [mobileSearchOpen, setMobileSearchOpen] = useState(false)
  const [search, setSearch] = useState('')

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

  const go = (hash: string) => {
    setMoreOpen(false)
    setMobileMenuOpen(false)
    setMobileSearchOpen(false)
    window.location.hash = hash
  }

  const submit = (event: FormEvent) => {
    event.preventDefault()
    const value = search.trim()
    go(value ? `#/prospect?search=${encodeURIComponent(value)}` : '#/prospect')
  }

  const currentLabel = current === 'home' ? 'Home' : 'My account'
  const avatar = initials(user)

  return <header className="reference-top-nav portal-route-nav">
    <button className="reference-brand" onClick={() => go('#/home')} aria-label="TowerSignal home"><img src={logoAsset} alt="TowerSignal" /></button>

    <nav className="reference-desktop-nav" aria-label="TowerSignal workspace">
      <button className={current === 'home' ? 'active' : ''} onClick={() => go('#/home')}>Home</button>
      {primaryItems.map(item => <button key={item.hash} onClick={() => go(item.hash)}>{item.label}</button>)}
      <div className={`reference-more-menu ${moreOpen ? 'open' : ''}`}>
        <button aria-haspopup="menu" aria-expanded={moreOpen} onClick={() => setMoreOpen(value => !value)}>More <span aria-hidden="true">⌄</span></button>
        {moreOpen && <div className="reference-more-popover" role="menu">
          {secondaryItems.map(item => <button key={item.hash} role="menuitem" onClick={() => go(item.hash)}>{item.label}</button>)}
        </div>}
      </div>
    </nav>

    <span className="reference-mobile-current" aria-label={`Current workspace: ${currentLabel}`}>{currentLabel}</span>

    <div className="reference-nav-tools">
      <form className="global-account-search reference-desktop-search" onSubmit={submit}><span aria-hidden="true">⌕</span><input aria-label="Search accounts or locations" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search accounts or locations" /></form>
      <button className="reference-mobile-search-trigger" aria-label="Search accounts" aria-expanded={mobileSearchOpen} onClick={() => { setMobileSearchOpen(value => !value); setMobileMenuOpen(false) }}>⌕</button>
      <button className="reference-mobile-menu-trigger" aria-label="Open workspace menu" aria-expanded={mobileMenuOpen} onClick={() => { setMobileMenuOpen(value => !value); setMobileSearchOpen(false) }}>☰</button>
      <button className={`workflow-profile-trigger ${current === 'my-account' ? 'active' : ''}`} aria-label="Open TowerSignal account" title={user.email} onClick={() => go('#/my-account')}><span>{avatar}</span></button>
      <button className={`portal-account-button reference-desktop-account ${current === 'my-account' ? 'active' : ''}`} onClick={() => go('#/my-account')}>My account</button>
    </div>

    {mobileSearchOpen && <form className="reference-mobile-search-panel" onSubmit={submit}>
      <input autoFocus aria-label="Search accounts or locations" value={search} onChange={event => setSearch(event.target.value)} placeholder="Account, address or location" />
      <button type="submit">Search</button>
    </form>}

    {mobileMenuOpen && <div className="reference-mobile-workspace-menu" role="dialog" aria-label="TowerSignal workspace menu">
      <div className="reference-mobile-menu-heading"><div><small>Current workspace</small><strong>{currentLabel}</strong></div><button aria-label="Close workspace menu" onClick={() => setMobileMenuOpen(false)}>×</button></div>
      <nav aria-label="All TowerSignal workspaces">
        <button className={current === 'home' ? 'active' : ''} onClick={() => go('#/home')}><span>Home</span>{current === 'home' && <small>Current</small>}</button>
        {[...primaryItems, ...secondaryItems].map(item => <button key={item.hash} onClick={() => go(item.hash)}><span>{item.label}</span></button>)}
      </nav>
      <div className="reference-mobile-menu-tools"><button className={current === 'my-account' ? 'active' : ''} onClick={() => go('#/my-account')}><span>My account</span><strong>{avatar}</strong></button></div>
    </div>}
  </header>
}
