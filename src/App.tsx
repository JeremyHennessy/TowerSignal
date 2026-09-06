import { useCallback, useEffect, useMemo, useState } from 'react'
import { loadChanges, loadNysChanges, loadNysSystems, loadSystems } from './data/api'
import type { SystemSummary, SystemsPayload } from './types/data'
import type { AcrisMetadataFields, AcrisPayloadSummaryFields } from './types/acris'
import type { ChangesPayload } from './types/history'
import type { NysChangesPayload, NysSystem, NysSystemsPayload } from './types/nys'
import type { CompanyIntelligenceRecord } from './types/company'
import { formatTimestamp } from './domain/labels'
import { ChangesView } from './components/ChangesView'
import { DetailPanel } from './components/DetailPanel'
import { Filters, filterSystems, initialFilters, type FilterState } from './components/Filters'
import { NysChangesView } from './components/NysChangesView'
import { NysDetailPanel } from './components/NysDetailPanel'
import { NysRegistryView } from './components/NysRegistryView'
import { SystemTable } from './components/SystemTable'
import { TowerMap } from './components/TowerMap'
import { WorkflowAccountSection } from './components/WorkflowAccountSection'
import { WorkflowPanel } from './components/WorkflowPanel'
import { OpportunitiesPage } from './components/OpportunitiesPage'
import { CompaniesPage } from './components/CompaniesPage'
import { CompanyProfilePage } from './components/CompanyProfilePage'
import { PortfoliosPage } from './components/PortfoliosPage'
import { SourceHealthPage } from './components/SourceHealthPage'
import { WaterQualityPage } from './components/WaterQualityPage'
import { WorkflowWorkspacePage } from './components/WorkflowWorkspacePage'
import { ShareButton } from './components/ShareButton'
import { TopNavigation, type WorkspaceMode } from './components/TopNavigation'
import { exportCsv } from './utils/export'
import { exportWorkflowCsv } from './utils/workflowExport'
import { useWorkflow } from './workflow/useWorkflow'

type ProductMode = WorkspaceMode | 'nys-account' | 'company'

const validModes = new Set<ProductMode>(['prospect','monitor','map','nys','nys-changes','opportunities','companies','company','water-quality','portfolios','workflow','source-health','account','nys-account'])
const filterKeys = Object.keys(initialFilters) as Array<keyof FilterState>

function pct(value: number, total: number): string {
  return total > 0 ? `${Math.round((value / total) * 100)}%` : '—'
}

function parseRoute(): { mode: ProductMode; id: string | null; filters: Partial<FilterState> } {
  const raw = window.location.hash.replace(/^#\/?/, '')
  if (!raw) return { mode:'prospect', id:null, filters:{} }
  const [path, query = ''] = raw.split('?')
  const parts = path.split('/').filter(Boolean)
  const mode = validModes.has(parts[0] as ProductMode) ? parts[0] as ProductMode : 'prospect'
  const params = new URLSearchParams(query)
  const filters: Partial<FilterState> = {}
  filterKeys.forEach(key => {
    const value = params.get(key)
    if (value != null) filters[key] = value
  })
  return { mode, id: parts[1] ? decodeURIComponent(parts[1]) : null, filters }
}

function routeHash(mode: ProductMode, id?: string | null, filters?: FilterState): string {
  const path = id ? `#/${mode}/${encodeURIComponent(id)}` : `#/${mode}`
  if (!filters || !['prospect','map'].includes(mode)) return path
  const params = new URLSearchParams()
  filterKeys.forEach(key => {
    const value = filters[key]
    if (value) params.set(key, value)
  })
  const query = params.toString()
  return query ? `${path}?${query}` : path
}

function shareUrl(mode: ProductMode, filters: FilterState, id?: string | null): string {
  const base = `${window.location.origin}${window.location.pathname}${window.location.search}`
  return `${base}${routeHash(mode, id, filters)}`
}

export default function App() {
  const initialRoute = parseRoute()
  const [payload, setPayload] = useState<SystemsPayload | null>(null)
  const [changes, setChanges] = useState<ChangesPayload | null>(null)
  const [nysPayload, setNysPayload] = useState<NysSystemsPayload | null>(null)
  const [nysChanges, setNysChanges] = useState<NysChangesPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<FilterState>({ ...initialFilters, ...initialRoute.filters })
  const [selected, setSelected] = useState<SystemSummary | null>(null)
  const [selectedNys, setSelectedNys] = useState<NysSystem | null>(null)
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(initialRoute.mode === 'company' ? initialRoute.id : null)
  const [mode, setMode] = useState<ProductMode>(initialRoute.mode)
  const [returnMode, setReturnMode] = useState<ProductMode>('prospect')
  const [viewName, setViewName] = useState('')
  const [watchedOnly, setWatchedOnly] = useState(false)
  const [globalSearch, setGlobalSearch] = useState(initialRoute.filters.search ?? '')
  const workflow = useWorkflow()

  useEffect(() => {
    Promise.all([loadSystems(), loadChanges(), loadNysSystems(), loadNysChanges()])
      .then(([systemsPayload, changesPayload, nysSystemsPayload, nysChangesPayload]) => {
        setPayload(systemsPayload)
        setChanges(changesPayload)
        setNysPayload(nysSystemsPayload)
        setNysChanges(nysChangesPayload)
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Unable to load TowerSignal data'))
  }, [])

  useEffect(() => {
    const apply = () => {
      const route = parseRoute()
      setMode(route.mode)
      if (Object.keys(route.filters).length > 0) setFilters(current => ({ ...current, ...route.filters }))
      if (route.mode === 'account' && route.id && payload) {
        setSelected(payload.systems.find(row => row.system_id === route.id) ?? null)
      } else if (route.mode !== 'account') {
        setSelected(null)
      }
      if (route.mode === 'nys-account' && route.id && nysPayload) {
        setSelectedNys(nysPayload.systems.find(row => row.system_id === route.id || row.source_equipment_id === route.id) ?? null)
      } else if (route.mode !== 'nys-account') {
        setSelectedNys(null)
      }
      if (route.mode === 'company' && route.id) {
        setSelectedCompanyId(route.id)
      } else if (route.mode !== 'company') {
        setSelectedCompanyId(null)
      }
    }
    apply()
    window.addEventListener('hashchange', apply)
    return () => window.removeEventListener('hashchange', apply)
  }, [payload, nysPayload])

  const sourceFiltered = useMemo(() => payload ? filterSystems(payload.systems, filters) : [], [payload, filters])
  const filtered = useMemo(() => watchedOnly && workflow.user
    ? sourceFiltered.filter(row => workflow.watchedSystemIds.has(row.system_id))
    : sourceFiltered, [sourceFiltered, watchedOnly, workflow.user, workflow.watchedSystemIds])
  const monitorChanges = useMemo(() => {
    if (!changes || !watchedOnly || !workflow.user) return changes
    const events = changes.events.filter(event => workflow.watchedSystemIds.has(event.system_id))
    return { ...changes, events, new_event_count: events.length }
  }, [changes, watchedOnly, workflow.user, workflow.watchedSystemIds])

  const navigate = useCallback((next: ProductMode) => {
    if (next === 'account' || next === 'nys-account' || next === 'company') return
    setMode(next)
    setSelected(null)
    setSelectedNys(null)
    setSelectedCompanyId(null)
    window.location.hash = routeHash(next)
  }, [])

  const openAccount = useCallback((row: SystemSummary) => {
    setReturnMode(mode === 'account' || mode === 'nys-account' || mode === 'company' ? 'prospect' : mode)
    setSelected(row)
    setMode('account')
    window.location.hash = routeHash('account', row.system_id)
  }, [mode])

  const openNysAccount = useCallback((row: NysSystem) => {
    setReturnMode(mode === 'account' || mode === 'nys-account' || mode === 'company' ? 'nys' : mode)
    setSelectedNys(row)
    setMode('nys-account')
    window.location.hash = routeHash('nys-account', row.system_id)
  }, [mode])

  const openCompany = useCallback((company: CompanyIntelligenceRecord) => {
    setSelectedCompanyId(company.company_id)
    setMode('company')
    window.location.hash = routeHash('company', company.company_id)
  }, [])

  const selectById = useCallback((id: string) => {
    const row = payload?.systems.find(item => item.system_id === id)
    if (row) openAccount(row)
  }, [payload, openAccount])

  const quick = (kind: string) => {
    if (kind === 'Confirmed violations') setFilters({ ...initialFilters, confirmed:'true' })
    if (kind === 'OATH cases') setFilters({ ...initialFilters, oath:'true' })
    if (kind === 'Recent ACRIS activity') setFilters({ ...initialFilters, acrisActivity:'true' })
    if (kind === 'Sampling-gap signals') setFilters({ ...initialFilters, signal:'POTENTIAL_SAMPLING_GAP' })
    if (kind === 'No sample date') setFilters({ ...initialFilters, signal:'NO_PUBLIC_SAMPLE_DATE' })
    if (kind === '3+ active units') setFilters({ ...initialFilters, minEquipment:'3' })
    if (kind === 'Manhattan') setFilters({ ...initialFilters, borough:'Manhattan' })
    if (kind === 'Highest priority') setFilters({ ...initialFilters, minScore:'70' })
  }

  const saveView = async () => {
    const name = viewName.trim()
    if (!name) return
    await workflow.saveView(name, filters)
    setViewName('')
  }

  const submitGlobalSearch = () => {
    const search = globalSearch.trim()
    setFilters({ ...initialFilters, search })
    setMode('prospect')
    setSelectedCompanyId(null)
    window.location.hash = routeHash('prospect', null, { ...initialFilters, search })
  }

  if (error) return <main className="app-shell"><div className="fatal-state"><div className="brand-lockup"><span className="brand-mark">TS</span><strong>TowerSignal</strong></div><h2>Intelligence workspace unavailable</h2><p>{error}</p><p>The application will not substitute fixture or mock records for a failed production dataset.</p></div></main>
  if (!payload || !changes || !nysPayload || !nysChanges || !monitorChanges) return <main className="app-shell"><div className="loading-page"><div className="brand-mark">TS</div><h1>TowerSignal</h1><p>Building the latest account-intelligence workspace…</p></div></main>

  const sourceHealth = payload.metadata.source_health ?? []
  const healthyHealth = sourceHealth.filter(source => source.status === 'HEALTHY')
  const nysMode = mode === 'nys' || mode === 'nys-changes' || mode === 'nys-account'
  const acrisMetadata = payload.metadata as SystemsPayload['metadata'] & AcrisMetadataFields
  const acrisSummary = payload.summary as SystemsPayload['summary'] & AcrisPayloadSummaryFields
  const acrisAvailable = acrisMetadata.acris_cache_available === true
  const registered = payload.summary.registered_systems
  const outreachReady = payload.systems.filter(row => row.priority_score >= 70).length
  const contactReady = payload.systems.filter(row => (row.hpd_contact_count ?? 0) > 0).length
  const samplingFollowUp = payload.systems.filter(row => row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE')).length
  const newOathCases = changes.events.filter(event => event.event_type === 'OATH_CASE_ADDED').length
  const recentDob = payload.summary.systems_with_recent_dob_activity ?? 0
  const recentAcris = acrisSummary.systems_with_recent_acris_activity ?? 0
  const watchedRows = payload.systems.filter(row => workflow.watchedSystemIds.has(row.system_id))
  const workflowAccount = selected ? workflow.accountBySystemId.get(selected.system_id) : undefined
  const workflowMembershipIds = selected ? workflow.watchlistIdsBySystemId.get(selected.system_id) ?? new Set<string>() : new Set<string>()
  const highPriorityChanges = monitorChanges.events.filter(event => (event.priority_score ?? 0) >= 70).length
  const sampleChanges = monitorChanges.events.filter(event => event.event_type.includes('SAMPLE') || event.event_type.includes('SAMPLING')).length
  const dobChanges = monitorChanges.events.filter(event => event.event_type.startsWith('DOB_')).length
  const propertyChanges = monitorChanges.events.filter(event => event.event_type.startsWith('HPD_') || event.event_type === 'PLUTO_OWNER_CHANGED').length
  const currentShareUrl = shareUrl(mode, filters, mode === 'account' ? selected?.system_id : mode === 'nys-account' ? selectedNys?.system_id : mode === 'company' ? selectedCompanyId : null)

  const exportWorkflow = () => exportWorkflowCsv(watchedRows, payload.metadata, workflow.accounts, workflow.memberships, workflow.watchlists)

  return <main className={`app-shell saas-shell reference-shell mode-${mode}`}>
    <TopNavigation
      mode={mode === 'nys-account' ? 'nys' : mode === 'company' ? 'companies' : mode}
      onNavigate={next => navigate(next)}
      search={globalSearch}
      onSearchChange={setGlobalSearch}
      onSearchSubmit={submitGlobalSearch}
      healthySources={healthyHealth.length}
      sourceCount={sourceHealth.length}
      user={workflow.user}
      authLoading={workflow.loading}
      authBusy={workflow.busy}
      authError={workflow.error}
      onSignIn={workflow.signIn}
      onSignUp={workflow.signUp}
      onSignOut={workflow.signOut}
    />

    <div className="main-stage">
      {!['opportunities','companies','company','water-quality','portfolios','workflow','source-health','account','nys-account'].includes(mode) && <header className="utility-bar reference-utility-bar">
        <div><span className="utility-kicker">{nysMode ? 'New York State' : 'New York City'}</span><strong>{mode === 'prospect' ? 'Prospect workspace' : mode === 'monitor' ? 'Monitor workspace' : mode === 'map' ? 'Map workspace' : mode === 'nys' ? 'NYS Market' : 'NYS Changes'}</strong></div>
        <div className="utility-actions"><ShareButton url={currentShareUrl} label="Share view" /><span className="coverage-chip">Data refreshed {formatTimestamp(nysMode ? nysPayload.metadata.generated_at : payload.metadata.generated_at)}</span>{!nysMode && acrisAvailable && acrisMetadata.acris_cache_generated_at && <span className="coverage-chip">ACRIS verified {formatTimestamp(acrisMetadata.acris_cache_generated_at)}</span>}{!nysMode && <button className="primary" onClick={() => exportCsv(filtered, payload.metadata)}>Export {filtered.length.toLocaleString()} accounts</button>}</div>
      </header>}

      {mode === 'prospect' && <section className="product-page prospect-reference-page">
        <div className="product-page-heading compact-heading"><div><span className="page-kicker">New York City</span><h1>Prospect workspace</h1><p>Find source-backed accounts that deserve commercial attention now, then open a shareable account profile for the evidence and next action.</p></div></div>
        <div className="reference-metric-grid prospect-reference-metrics" aria-label="Commercial signal summary">
          <article><span className="reference-metric-icon urgent">↗</span><div><small>High priority accounts</small><strong>{outreachReady.toLocaleString()}</strong><span>Priority score 70+</span></div></article>
          <article><span className="reference-metric-icon warning">◷</span><div><small>Sampling follow-up</small><strong>{samplingFollowUp.toLocaleString()}</strong><span>Gap or missing-date signals</span></div></article>
          <article><span className="reference-metric-icon success">◎</span><div><small>Contact-ready</small><strong>{contactReady.toLocaleString()}</strong><span>HPD contacts matched</span></div></article>
          <article><span className="reference-metric-icon">⌁</span><div><small>Recent DOB activity</small><strong>{recentDob.toLocaleString()}</strong><span>Project timing context</span></div></article>
          <article><button className="metric-card-button" onClick={() => navigate('source-health')}><span className="reference-metric-icon success">⌂</span><span><small>Total NYC accounts</small><strong>{registered.toLocaleString()}</strong><em>{healthyHealth.length}/{sourceHealth.length || '—'} sources healthy</em></span></button></article>
        </div>
        <div className="prospect-layout reference-prospect-layout">
          <aside className="filter-rail">
            <Filters rows={payload.systems} value={filters} onChange={setFilters} onQuick={quick} acrisAvailable={acrisAvailable} />
            <section className="saved-views"><div className="section-title"><div><span className="eyebrow">Monitor</span><h3>Saved views</h3></div><span>{workflow.savedViews.length}</span></div><div className="save-view-row"><input aria-label="Saved view name" value={viewName} onChange={event => setViewName(event.target.value)} placeholder="e.g. Manhattan follow-up" /><button onClick={() => void saveView()} disabled={!viewName.trim() || workflow.busy}>Save</button></div>{workflow.savedViews.length === 0 ? <p>No saved views yet. Save this filter set for repeat prospecting.</p> : <div className="saved-view-list">{workflow.savedViews.map(view => <div key={view.id}><button onClick={() => setFilters({ ...initialFilters, ...view.filters })}>{view.name}</button><button className="icon-button-small" aria-label={`Delete ${view.name}`} onClick={() => void workflow.deleteView(view.id)}>×</button></div>)}</div>}<p className="microcopy">{workflow.user ? 'Saved views sync with your private workflow account.' : 'Saved views remain in this browser until you sign in to sync them.'}</p></section>
            <WorkflowPanel user={workflow.user} watchlists={workflow.watchlists} watchedSystemIds={workflow.watchedSystemIds} memberships={workflow.memberships} watchedOnly={watchedOnly} busy={workflow.busy} onToggleWatchedOnly={() => setWatchedOnly(value => !value)} onCreateWatchlist={workflow.createWatchlist} onDeleteWatchlist={workflow.deleteWatchlist} onExport={exportWorkflow} />
          </aside>
          <section className="account-workspace"><div className="workspace-heading"><div><span className="eyebrow">Account intelligence</span><h2>Sales-ready accounts</h2><p>{watchedOnly && workflow.user ? 'Watched accounts matching the current public-evidence filters.' : 'Priority is WHY NOW. Commercial enrichment remains separate from the deterministic timing score.'}</p></div><div className="workspace-heading-actions"><ShareButton url={shareUrl('prospect', filters)} label="Share filters" /><button onClick={() => navigate('map')}>View on map</button></div></div><SystemTable rows={filtered} onSelect={openAccount} /></section>
        </div>
      </section>}

      {mode === 'monitor' && <section className="product-page monitor-reference-page"><div className="product-page-heading"><div><span className="page-kicker">New York City · preserved history</span><h1>Monitor workspace</h1><p>What changed since the last observation? Review source-backed changes and re-open accounts when new timing evidence appears.</p></div><div className="page-actions">{workflow.user && <button className={watchedOnly ? 'active-control' : ''} onClick={() => setWatchedOnly(value => !value)}>{watchedOnly ? 'Watched accounts only' : 'Filter to watched accounts'}</button>}</div></div><div className="reference-metric-grid monitor-reference-metrics"><article><span className="reference-metric-icon urgent">↗</span><div><small>High-priority changes</small><strong>{highPriorityChanges.toLocaleString()}</strong><span>Events on score 70+ accounts</span></div></article><article><span className="reference-metric-icon warning">◷</span><div><small>Sampling changes</small><strong>{sampleChanges.toLocaleString()}</strong><span>Sample date or gap events</span></div></article><article><span className="reference-metric-icon">§</span><div><small>New OATH cases</small><strong>{newOathCases.toLocaleString()}</strong><span>Exact-matched additions</span></div></article><article><span className="reference-metric-icon success">⌁</span><div><small>DOB / permit changes</small><strong>{dobChanges.toLocaleString()}</strong><span>Project lifecycle events</span></div></article><article><span className="reference-metric-icon">⌂</span><div><small>Property / contact</small><strong>{propertyChanges.toLocaleString()}</strong><span>HPD or PLUTO changes</span></div></article></div><ChangesView payload={monitorChanges} onSelectSystem={selectById} /></section>}

      {mode === 'map' && <section className="product-page map-reference-page"><div className="product-page-heading"><div><span className="page-kicker">New York City · territory intelligence</span><h1>Map workspace</h1><p>Explore the same filtered prospect set geographically, then open any account as a shareable source-backed profile.</p></div><div className="page-actions"><ShareButton url={shareUrl('map', filters)} label="Share map view" /></div></div><div className="map-reference-grid"><aside className="map-reference-rail"><div className="map-kpis"><article><small>High priority</small><strong>{filtered.filter(row => row.priority_score >= 70).length.toLocaleString()}</strong></article><article><small>Sampling follow-up</small><strong>{filtered.filter(row => row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE')).length.toLocaleString()}</strong></article><article><small>Contact-ready</small><strong>{filtered.filter(row => (row.hpd_contact_count ?? 0) > 0).length.toLocaleString()}</strong></article><article><small>Matching accounts</small><strong>{filtered.length.toLocaleString()}</strong></article></div><Filters rows={payload.systems} value={filters} onChange={setFilters} onQuick={quick} acrisAvailable={acrisAvailable} /></aside><div className="map-reference-canvas"><TowerMap systems={filtered} selectedId={selected?.system_id ?? null} onSelect={openAccount} /></div></div></section>}

      {mode === 'nys' && <section className="product-page nys-reference-page"><div className="product-page-heading"><div><span className="page-kicker">New York State</span><h1>NYS Market</h1><p>Explore the official statewide cooling-tower registry outside NYC while preserving source-native status, compliance, sample and location context.</p></div></div><div className="reference-metric-grid nys-reference-metrics"><article><span className="reference-metric-icon success">◎</span><div><small>Registered equipment</small><strong>{nysPayload.summary.registered_equipment.toLocaleString()}</strong><span>Current registry extract</span></div></article><article><span className="reference-metric-icon">⌂</span><div><small>Unique properties</small><strong>{nysPayload.metadata.unique_property_count.toLocaleString()}</strong><span>Deterministic property keys</span></div></article><article><span className="reference-metric-icon urgent">!</span><div><small>Non-compliant</small><strong>{nysPayload.summary.non_compliant.toLocaleString()}</strong><span>Source-native status</span></div></article><article><span className="reference-metric-icon warning">◷</span><div><small>Sample required</small><strong>{nysPayload.summary.sample_required.toLocaleString()}</strong><span>Registry field</span></div></article><article><span className="reference-metric-icon success">⌖</span><div><small>Mapped equipment</small><strong>{nysPayload.summary.mapped_equipment.toLocaleString()}</strong><span>Usable source coordinates</span></div></article></div><NysRegistryView payload={nysPayload} selected={selectedNys} onSelect={row => row ? openNysAccount(row) : setSelectedNys(null)} /></section>}

      {mode === 'nys-changes' && <section className="product-page nys-reference-page"><div className="product-page-heading"><div><span className="page-kicker">New York State · preserved history</span><h1>NYS Changes</h1><p>Review newly observed equipment and source-native status, compliance, sample and operational changes.</p></div></div><div className="reference-metric-grid"><article><span className="reference-metric-icon urgent">↗</span><div><small>Total changes</small><strong>{nysChanges.new_event_count.toLocaleString()}</strong><span>Current history delta</span></div></article><article><span className="reference-metric-icon warning">+</span><div><small>New equipment</small><strong>{nysChanges.events.filter(event => event.event_type === 'NYS_EQUIPMENT_FIRST_SEEN').length.toLocaleString()}</strong><span>First observed in history</span></div></article><article><span className="reference-metric-icon success">✓</span><div><small>Compliance changes</small><strong>{nysChanges.events.filter(event => event.event_type === 'NYS_REG_COMPLIANCE_CHANGED').length.toLocaleString()}</strong><span>Source-native status change</span></div></article><article><span className="reference-metric-icon">◉</span><div><small>Sample result changes</small><strong>{nysChanges.events.filter(event => event.event_type === 'NYS_SAMPLE_RESULT_CHANGED').length.toLocaleString()}</strong><span>Observed registry change</span></div></article><article><span className="reference-metric-icon">↻</span><div><small>Operating status</small><strong>{nysChanges.events.filter(event => event.event_type === 'NYS_CT_STATUS_CHANGED').length.toLocaleString()}</strong><span>Tower status changes</span></div></article></div><NysChangesView payload={nysChanges} systems={nysPayload.systems} onSelect={row => row ? openNysAccount(row) : setSelectedNys(null)} /></section>}

      {mode === 'opportunities' && <OpportunitiesPage payload={payload} onOpenAccount={openAccount} />}
      {mode === 'companies' && <CompaniesPage onOpenCompany={openCompany} />}
      {mode === 'company' && selectedCompanyId && <CompanyProfilePage companyId={selectedCompanyId} onBack={() => navigate('companies')} onOpenCompany={openCompany} />}
      {mode === 'company' && !selectedCompanyId && <section className="product-page company-profile-page"><div className="reference-empty-state"><strong>Company ID is missing from this share link.</strong><button onClick={() => navigate('companies')}>Return to Companies</button></div></section>}
      {mode === 'water-quality' && <WaterQualityPage />}
      {mode === 'portfolios' && <PortfoliosPage payload={payload} watchedSystemIds={workflow.watchedSystemIds} onOpenAccount={openAccount} />}
      {mode === 'workflow' && <WorkflowWorkspacePage user={workflow.user} systems={payload.systems} accounts={workflow.accounts} watchlists={workflow.watchlists} memberships={workflow.memberships} savedViews={workflow.savedViews} onOpenAccount={openAccount} />}
      {mode === 'source-health' && <SourceHealthPage payload={payload} />}

      {mode === 'account' && <section className="product-page account-profile-page"><div className="account-profile-toolbar"><div><button className="breadcrumb-back" onClick={() => navigate(returnMode === 'account' || returnMode === 'nys-account' || returnMode === 'company' ? 'prospect' : returnMode)}>← Back</button><span>New York City · account profile</span></div><div className="page-actions"><ShareButton url={currentShareUrl} label="Copy account link" /><button onClick={() => exportCsv(selected ? [selected] : [], payload.metadata)} disabled={!selected}>Export account</button></div></div>{selected ? <DetailPanel row={selected} metadata={payload.metadata} historyEvents={changes.events.filter(event => event.system_id === selected.system_id)} historyStartedAt={changes.history_started_at} workflowSection={<WorkflowAccountSection signedIn={Boolean(workflow.user)} account={workflowAccount} watchlists={workflow.watchlists} membershipIds={workflowMembershipIds} busy={workflow.busy} onSave={patch => workflow.saveAccount(selected.system_id, patch)} onToggleMembership={(watchlistId, enabled) => workflow.toggleMembership(selected.system_id, watchlistId, enabled)} />} onClose={() => navigate(returnMode === 'account' || returnMode === 'nys-account' || returnMode === 'company' ? 'prospect' : returnMode)} /> : <div className="reference-empty-state"><strong>Account not found in the current public snapshot.</strong><span>The share link may refer to an account that is no longer present or whose ID changed upstream.</span><button onClick={() => navigate('prospect')}>Return to Prospect</button></div>}</section>}

      {mode === 'nys-account' && <section className="product-page account-profile-page"><div className="account-profile-toolbar"><div><button className="breadcrumb-back" onClick={() => navigate('nys')}>← Back to NYS Market</button><span>New York State · equipment profile</span></div><div className="page-actions"><ShareButton url={currentShareUrl} label="Copy equipment link" /></div></div>{selectedNys ? <NysDetailPanel row={selectedNys} metadata={nysPayload.metadata} onClose={() => navigate('nys')} /> : <div className="reference-empty-state"><strong>NYS equipment record not found in the current registry snapshot.</strong><button onClick={() => navigate('nys')}>Return to NYS Market</button></div>}</section>}

      <section className="responsible-use reference-responsible-use"><strong>Responsible use.</strong> Signals are commercial timing indicators derived from public records, not legal or health determinations. Verify current operating, testing, maintenance and compliance status before relying on a signal or contacting a property.</section>
      <footer id="data-provenance" className="reference-footer"><div><strong>Data provenance</strong><span>{registered.toLocaleString()} NYC systems · PLUTO {pct(payload.summary.systems_with_pluto_context ?? 0, registered)} · HPD contacts {pct(contactReady, registered)}{acrisAvailable ? ` · recent ACRIS ${pct(recentAcris, registered)}` : ''}</span></div><div><strong>Trust model</strong><span>Rules {payload.metadata.rules_version} · Priority {payload.metadata.priority_model_version} · NYC history {changes.history_schema_version} · NYS history {nysChanges.history_schema_version}</span><button className="link-button" onClick={() => navigate('source-health')}>Open Source Health &amp; Coverage</button></div></footer>
    </div>

    {(mode === 'prospect' || mode === 'monitor' || mode === 'map') && selected && <DetailPanel row={selected} metadata={payload.metadata} historyEvents={changes.events.filter(event => event.system_id === selected.system_id)} historyStartedAt={changes.history_started_at} workflowSection={<WorkflowAccountSection signedIn={Boolean(workflow.user)} account={workflowAccount} watchlists={workflow.watchlists} membershipIds={workflowMembershipIds} busy={workflow.busy} onSave={patch => workflow.saveAccount(selected.system_id, patch)} onToggleMembership={(watchlistId, enabled) => workflow.toggleMembership(selected.system_id, watchlistId, enabled)} />} onClose={() => setSelected(null)} />}
  </main>
}
