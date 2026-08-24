import { useCallback, useEffect, useMemo, useState } from 'react'
import { loadChanges, loadNysChanges, loadNysSystems, loadSystems } from './data/api'
import type { SystemSummary, SystemsPayload } from './types/data'
import type { AcrisMetadataFields, AcrisPayloadSummaryFields, AcrisSummaryFields } from './types/acris'
import type { ChangesPayload } from './types/history'
import type { NysChangesPayload, NysSystem, NysSystemsPayload } from './types/nys'
import { formatTimestamp } from './domain/labels'
import { ChangesView } from './components/ChangesView'
import { DetailPanel } from './components/DetailPanel'
import { Filters, filterSystems, initialFilters, type FilterState } from './components/Filters'
import { NysChangesView } from './components/NysChangesView'
import { NysDetailPanel } from './components/NysDetailPanel'
import { NysRegistryView } from './components/NysRegistryView'
import { SystemTable } from './components/SystemTable'
import { TowerMap } from './components/TowerMap'
import { exportCsv } from './utils/export'

type ProductMode = 'prospect' | 'monitor' | 'map' | 'nys' | 'nys-changes'
interface SavedView { id: string; name: string; filters: FilterState }
const SAVED_VIEWS_KEY = 'towersignal.savedViews.v1'

function loadSavedViews(): SavedView[] {
  try {
    const raw = window.localStorage.getItem(SAVED_VIEWS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as SavedView[]
    if (!Array.isArray(parsed)) return []
    return parsed.map(view => ({ ...view, filters: { ...initialFilters, ...(view.filters ?? {}) } }))
  } catch {
    return []
  }
}

function pct(value: number, total: number): string {
  return total > 0 ? `${Math.round((value / total) * 100)}%` : '—'
}

export default function App() {
  const [payload, setPayload] = useState<SystemsPayload | null>(null)
  const [changes, setChanges] = useState<ChangesPayload | null>(null)
  const [nysPayload, setNysPayload] = useState<NysSystemsPayload | null>(null)
  const [nysChanges, setNysChanges] = useState<NysChangesPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<FilterState>(initialFilters)
  const [selected, setSelected] = useState<SystemSummary | null>(null)
  const [selectedNys, setSelectedNys] = useState<NysSystem | null>(null)
  const [mode, setMode] = useState<ProductMode>('prospect')
  const [savedViews, setSavedViews] = useState<SavedView[]>(loadSavedViews)
  const [viewName, setViewName] = useState('')

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

  const filtered = useMemo(() => payload ? filterSystems(payload.systems, filters) : [], [payload, filters])
  const selectById = useCallback((id: string) => {
    const row = payload?.systems.find(item => item.system_id === id)
    if (row) setSelected(row)
  }, [payload])

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

  const saveView = () => {
    const name = viewName.trim()
    if (!name) return
    const next = [...savedViews.filter(view => view.name.toLowerCase() !== name.toLowerCase()), {
      id: `${Date.now()}-${name}`,
      name,
      filters: { ...filters },
    }]
    setSavedViews(next)
    window.localStorage.setItem(SAVED_VIEWS_KEY, JSON.stringify(next))
    setViewName('')
  }

  const deleteView = (id: string) => {
    const next = savedViews.filter(view => view.id !== id)
    setSavedViews(next)
    window.localStorage.setItem(SAVED_VIEWS_KEY, JSON.stringify(next))
  }

  if (error) return <main className="app-shell"><div className="fatal-state"><div className="brand-lockup"><span className="brand-mark">TS</span><strong>TowerSignal</strong></div><h2>Intelligence workspace unavailable</h2><p>{error}</p><p>The application will not substitute fixture or mock records for a failed production dataset.</p></div></main>
  if (!payload || !changes || !nysPayload || !nysChanges) return <main className="app-shell"><div className="loading-page"><div className="brand-mark">TS</div><h1>TowerSignal</h1><p>Building the latest account-intelligence workspace…</p></div></main>

  const sourceHealth = payload.metadata.source_health ?? []
  const healthyHealth = sourceHealth.filter(source => source.status === 'HEALTHY')
  const nysMode = mode === 'nys' || mode === 'nys-changes'
  const registered = payload.summary.registered_systems
  const outreachReady = payload.systems.filter(row => row.priority_score >= 70).length
  const contactReady = payload.systems.filter(row => (row.hpd_contact_count ?? 0) > 0).length
  const samplingFollowUp = payload.systems.filter(row => row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE')).length
  const newOathCases = changes.events.filter(event => event.event_type === 'OATH_CASE_ADDED').length
  const recentDob = payload.summary.systems_with_recent_dob_activity ?? 0
  const plutoMatches = payload.summary.systems_with_pluto_context ?? 0
  const oathMatches = payload.summary.systems_with_oath_cases ?? 0
  const acrisMetadata = payload.metadata as SystemsPayload['metadata'] & AcrisMetadataFields
  const acrisSummary = payload.summary as SystemsPayload['summary'] & AcrisPayloadSummaryFields
  const acrisAvailable = acrisMetadata.acris_cache_available === true
  const recentAcris = acrisSummary.systems_with_recent_acris_activity ?? 0
  const filteredAcris = acrisAvailable ? filtered.filter(row => ((row as SystemSummary & AcrisSummaryFields).acris_recent_document_count ?? 0) > 0).length : 0

  return <main className="app-shell saas-shell">
    <aside className="side-nav">
      <div className="brand-lockup"><span className="brand-mark">TS</span><div><strong>TowerSignal</strong><small>Account intelligence</small></div></div>
      <nav aria-label="TowerSignal workspace">
        <span className="nav-label">Workspace</span>
        <button className={mode === 'prospect' ? 'active' : ''} onClick={() => setMode('prospect')}><span aria-hidden="true">◎</span> Prospect</button>
        <button className={mode === 'monitor' ? 'active' : ''} onClick={() => setMode('monitor')}><span aria-hidden="true">◫</span> Monitor</button>
        <button className={mode === 'map' ? 'active' : ''} onClick={() => setMode('map')}><span aria-hidden="true">◇</span> Map</button>
        <span className="nav-label">Market intelligence</span>
        <button className={mode === 'nys' ? 'active' : ''} onClick={() => setMode('nys')}><span aria-hidden="true">↗</span> NYS Market</button>
        <button className={mode === 'nys-changes' ? 'active' : ''} onClick={() => setMode('nys-changes')}><span aria-hidden="true">↻</span> NYS Changes</button>
      </nav>
      <div className="side-trust"><span className="status-dot" />{healthyHealth.length}/{sourceHealth.length || '—'} sources healthy<small>Updated {formatTimestamp(payload.metadata.generated_at)}</small></div>
    </aside>

    <div className="main-stage">
      <header className="utility-bar">
        <div><span className="utility-kicker">{nysMode ? 'New York State' : 'New York City'}</span><strong>{mode === 'prospect' ? 'Find accounts' : mode === 'monitor' ? 'Monitor changes' : mode === 'map' ? 'Territory map' : mode === 'nys' ? 'NYS market map' : 'NYS market changes'}</strong></div>
        <div className="utility-actions"><span className="coverage-chip">Data refreshed {formatTimestamp(nysMode ? nysPayload.metadata.generated_at : payload.metadata.generated_at)}</span>{!nysMode && <span className="coverage-chip">{acrisAvailable && acrisMetadata.acris_cache_generated_at ? `ACRIS verified ${formatTimestamp(acrisMetadata.acris_cache_generated_at)}` : 'ACRIS timing unavailable'}</span>}{!nysMode && <button className="primary" onClick={() => exportCsv(filtered, payload.metadata)}>Export {filtered.length.toLocaleString()} accounts</button>}</div>
      </header>

      {mode === 'prospect' && <>
        <section className="value-hero">
          <div><span className="eyebrow">Commercial timing intelligence</span><h1>Know which cooling-tower accounts deserve attention now.</h1><p>TowerSignal combines public registration, sampling, inspection, OATH, DOB, ACRIS property-recording, property and contact evidence into a prioritized workspace for water-treatment, Legionella, HVAC and environmental sales teams.</p></div>
          <div className="hero-proof"><strong>{outreachReady.toLocaleString()}</strong><span>high-priority accounts</span><small>Score 70+ in the current NYC snapshot</small></div>
        </section>

        <section className="signal-grid" aria-label="Commercial signal summary">
          <article><span className="metric-icon urgent">↗</span><div><small>Outreach-ready</small><strong>{outreachReady.toLocaleString()}</strong><span>High-priority accounts</span></div></article>
          <article><span className="metric-icon warning">◷</span><div><small>Sampling follow-up</small><strong>{samplingFollowUp.toLocaleString()}</strong><span>Gap or missing-date signals</span></div></article>
          <article><span className="metric-icon">§</span><div><small>New OATH activity</small><strong>{newOathCases.toLocaleString()}</strong><span>New cases in preserved history</span></div></article>
          <article><span className="metric-icon success">✓</span><div><small>Contact-ready</small><strong>{contactReady.toLocaleString()}</strong><span>HPD contacts matched</span></div></article>
          <article><span className="metric-icon">⌁</span><div><small>Recent DOB activity</small><strong>{recentDob.toLocaleString()}</strong><span>{acrisAvailable ? `${recentAcris.toLocaleString()} systems also have recent ACRIS timing` : 'Commercial timing context'}</span></div></article>
        </section>

        <section className="coverage-strip"><strong>Data coverage</strong><span>{registered.toLocaleString()} NYC systems</span><span>PLUTO {pct(plutoMatches, registered)}</span><span>OATH history {pct(oathMatches, registered)}</span><span>HPD contacts {pct(contactReady, registered)}</span><button className="link-button" onClick={() => document.getElementById('data-provenance')?.scrollIntoView({ behavior:'smooth' })}>View provenance</button></section>

        <div className="prospect-layout">
          <aside className="filter-rail">
            <Filters rows={payload.systems} value={filters} onChange={setFilters} onQuick={quick} acrisAvailable={acrisAvailable} />
            <section className="saved-views"><div className="section-title"><div><span className="eyebrow">Monitor</span><h3>Saved views</h3></div><span>{savedViews.length}</span></div><div className="save-view-row"><input aria-label="Saved view name" value={viewName} onChange={event => setViewName(event.target.value)} placeholder="e.g. Manhattan follow-up" /><button onClick={saveView} disabled={!viewName.trim()}>Save</button></div>{savedViews.length === 0 ? <p>No saved views yet. Save this filter set for repeat prospecting.</p> : <div className="saved-view-list">{savedViews.map(view => <div key={view.id}><button onClick={() => setFilters({ ...initialFilters, ...view.filters })}>{view.name}</button><button className="icon-button-small" aria-label={`Delete ${view.name}`} onClick={() => deleteView(view.id)}>×</button></div>)}</div>}</section>
          </aside>
          <section className="account-workspace"><div className="workspace-heading"><div><span className="eyebrow">Prospect workspace</span><h2>Sales-ready accounts</h2><p>Prioritized by timing signal, evidence, contact context and recent activity.</p></div><button onClick={() => setMode('map')}>View on map</button></div><SystemTable rows={filtered} onSelect={setSelected} /></section>
        </div>
      </>}

      {mode === 'monitor' && <section className="page-section"><div className="page-heading"><div><span className="eyebrow">Account monitoring</span><h1>What changed since the last observation?</h1><p>Use preserved public-record changes to spot new reasons to investigate or re-engage an account.</p></div><span className="page-count">{changes.new_event_count.toLocaleString()} new events</span></div><ChangesView payload={changes} onSelectSystem={selectById} /></section>}

      {mode === 'map' && <section className="page-section"><div className="page-heading"><div><span className="eyebrow">Territory intelligence</span><h1>Explore the current opportunity set geographically.</h1><p>Map the same filtered prospect set, then open any system to inspect its evidence and account context.</p></div><button className="primary" onClick={() => setMode('prospect')}>Back to prospect list</button></div><Filters rows={payload.systems} value={filters} onChange={setFilters} onQuick={quick} acrisAvailable={acrisAvailable} /><div className="map-workspace"><TowerMap systems={filtered} selectedId={selected?.system_id ?? null} onSelect={selectById} /><aside className="map-summary"><span className="eyebrow">Current territory</span><strong>{filtered.length.toLocaleString()}</strong><span>matching accounts</span><dl><div><dt>High priority</dt><dd>{filtered.filter(row => row.priority_score >= 70).length.toLocaleString()}</dd></div><div><dt>Contact-ready</dt><dd>{filtered.filter(row => (row.hpd_contact_count ?? 0) > 0).length.toLocaleString()}</dd></div><div><dt>Confirmed violation</dt><dd>{filtered.filter(row => row.confirmed_violation).length.toLocaleString()}</dd></div>{acrisAvailable && <div><dt>Recent ACRIS</dt><dd>{filteredAcris.toLocaleString()}</dd></div>}</dl></aside></div></section>}

      {mode === 'nys' && <section className="page-section"><div className="page-heading"><div><span className="eyebrow">Market expansion</span><h1>New York State registry intelligence</h1><p>Explore the official NYS cooling-tower registry outside NYC without losing the account-intelligence workflow.</p></div></div><NysRegistryView payload={nysPayload} selected={selectedNys} onSelect={setSelectedNys} /></section>}
      {mode === 'nys-changes' && <section className="page-section"><div className="page-heading"><div><span className="eyebrow">Market monitoring</span><h1>New York State registry changes</h1><p>See newly observed equipment, status and compliance changes in the preserved NYS history.</p></div></div><NysChangesView payload={nysChanges} systems={nysPayload.systems} onSelect={setSelectedNys} /></section>}

      <section className="responsible-use"><strong>Responsible use.</strong> Signals are commercial timing indicators derived from public records, not legal or health determinations. Verify current operating, testing, maintenance and compliance status before relying on a signal or contacting a property.</section>
      <footer id="data-provenance"><div><strong>Data provenance</strong>{sourceHealth.length === 0 ? <span>Source-health metrics unavailable.</span> : sourceHealth.map(source => <span key={source.source_key}>{source.name} · {source.status} · {source.coverage_percentage == null ? 'coverage n/a' : `${source.coverage_percentage.toFixed(1)}% coverage`} · {source.displayed_entity_count.toLocaleString()} represented</span>)}</div><div><strong>Trust model</strong><span>Rules {payload.metadata.rules_version}</span><span>Priority model {payload.metadata.priority_model_version}</span><span>NYC history {changes.history_schema_version} · NYS history {nysChanges.history_schema_version}</span></div></footer>
    </div>

    {(mode === 'prospect' || mode === 'monitor' || mode === 'map') && <DetailPanel row={selected} metadata={payload.metadata} historyEvents={selected ? changes.events.filter(event => event.system_id === selected.system_id) : []} historyStartedAt={changes.history_started_at} onClose={() => setSelected(null)} />}
    {nysMode && <NysDetailPanel row={selectedNys} metadata={nysPayload.metadata} onClose={() => setSelectedNys(null)} />}
  </main>
}
