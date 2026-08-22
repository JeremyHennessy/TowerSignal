import { useCallback, useEffect, useMemo, useState } from 'react'
import { loadChanges, loadSystems } from './data/api'
import type { SystemSummary, SystemsPayload } from './types/data'
import type { ChangesPayload } from './types/history'
import { formatTimestamp } from './domain/labels'
import { ChangesView } from './components/ChangesView'
import { DetailPanel } from './components/DetailPanel'
import { Filters, filterSystems, initialFilters, type FilterState } from './components/Filters'
import { SystemTable } from './components/SystemTable'
import { TowerMap } from './components/TowerMap'
import { exportCsv } from './utils/export'

type ProductMode = 'leads' | 'changes'

export default function App() {
  const [payload, setPayload] = useState<SystemsPayload | null>(null)
  const [changes, setChanges] = useState<ChangesPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<FilterState>(initialFilters)
  const [selected, setSelected] = useState<SystemSummary | null>(null)
  const [mode, setMode] = useState<ProductMode>('leads')

  useEffect(() => {
    Promise.all([loadSystems(), loadChanges()])
      .then(([systemsPayload, changesPayload]) => { setPayload(systemsPayload); setChanges(changesPayload) })
      .catch(err => setError(err instanceof Error ? err.message : 'Unable to load TowerSignal data'))
  }, [])
  const filtered = useMemo(() => payload ? filterSystems(payload.systems, filters) : [], [payload, filters])
  const selectById = useCallback((id: string) => { const row = payload?.systems.find(item => item.system_id === id); if (row) setSelected(row) }, [payload])
  const quick = (kind: string) => {
    if (kind === 'Confirmed violations') setFilters({ ...initialFilters, confirmed:'true' })
    if (kind === 'OATH cases') setFilters({ ...initialFilters, oath:'true' })
    if (kind === 'Sampling-gap signals') setFilters({ ...initialFilters, signal:'POTENTIAL_SAMPLING_GAP' })
    if (kind === 'No sample date') setFilters({ ...initialFilters, signal:'NO_PUBLIC_SAMPLE_DATE' })
    if (kind === '3+ active units') setFilters({ ...initialFilters, minEquipment:'3' })
    if (kind === 'Manhattan') setFilters({ ...initialFilters, borough:'Manhattan' })
    if (kind === 'Highest priority') setFilters({ ...initialFilters, minScore:'70' })
  }

  if (error) return <main className="app-shell"><div className="fatal-state"><h1>TowerSignal</h1><h2>Data unavailable</h2><p>{error}</p><p>The application will not substitute fixture or mock records for a failed production dataset.</p></div></main>
  if (!payload || !changes) return <main className="app-shell"><div className="loading-page"><div className="brand-mark">TS</div><h1>TowerSignal</h1><p>Loading current NYC public-record snapshot and preserved history…</p></div></main>

  const generatedAgeDays = Math.floor((Date.now() - new Date(payload.metadata.generated_at).getTime()) / 86400000)
  const oldestSourceUpdateDays = Math.max(0, ...payload.metadata.sources.map(source => source.source_last_updated_at ? Math.floor((Date.now() - new Date(source.source_last_updated_at).getTime()) / 86400000) : 0))
  const sourceHealth = payload.metadata.source_health ?? []
  const failedHealth = sourceHealth.filter(source => source.status === 'FAILED')
  const warningHealth = sourceHealth.filter(source => source.status === 'WARNING')
  const healthyHealth = sourceHealth.filter(source => source.status === 'HEALTHY')

  return <main className="app-shell">
    <header className="topbar"><div><div className="brand"><span className="brand-mark">TS</span><div><h1>TowerSignal</h1><p>NYC cooling-tower commercial intelligence</p></div></div></div><div className="freshness"><span>Data refreshed</span><strong>{formatTimestamp(payload.metadata.generated_at)}</strong>{sourceHealth.length > 0 && <span>Source health {healthyHealth.length}/{sourceHealth.length} healthy</span>}{failedHealth.length > 0 && <em>{failedHealth.length} source-health failure{failedHealth.length === 1 ? '' : 's'}</em>}{warningHealth.length > 0 && failedHealth.length === 0 && <em>{warningHealth.length} source-health warning{warningHealth.length === 1 ? '' : 's'}</em>}{generatedAgeDays > 2 && <em>Snapshot is older than expected</em>}{oldestSourceUpdateDays > 30 && <em>One source was last updated {oldestSourceUpdateDays} days ago</em>}</div></header>
    <nav className="product-nav" aria-label="TowerSignal product modes"><button className={mode === 'leads' ? 'active' : ''} onClick={() => setMode('leads')}>Leads</button><button className={mode === 'changes' ? 'active' : ''} onClick={() => setMode('changes')}>Changes</button></nav>
    {mode === 'leads' ? <>
      <section className="hero"><div><span className="eyebrow">Source-backed commercial intelligence</span><h2>Find cooling-tower systems worth investigating today.</h2><p>Turn public registration, sampling, NYC Health inspection and exact-matched OATH case records into transparent commercial intelligence — with evidence and uncertainty kept separate.</p></div><div className="hero-actions"><button className="primary" onClick={() => exportCsv(filtered, payload.metadata)}>Export filtered CSV</button><span>{filtered.length.toLocaleString()} records in current lead set</span></div></section>
      <section className="disclaimer"><strong>Responsible-use notice.</strong> TowerSignal provides commercial intelligence derived from public records. Signals are not legal advice, health advice, or definitive determinations of regulatory compliance. Public records may be incomplete or delayed. Verify current operating, testing, maintenance and compliance status before relying on a signal or contacting a property.</section>
      <section className="kpis"><article><span>Registered systems</span><strong>{payload.summary.registered_systems.toLocaleString()}</strong><small>Normalized public inventory</small></article><article><span>Active equipment</span><strong>{payload.summary.active_equipment.toLocaleString()}</strong><small>Published equipment count</small></article><article><span>Potential sampling gaps</span><strong>{payload.summary.potential_sampling_gaps.toLocaleString()}</strong><small>Verification signals, not violations</small></article><article><span>Recent confirmed violations</span><strong>{payload.summary.recent_confirmed_violations.toLocaleString()}</strong><small>Official NYC Health records</small></article><article><span>Systems with OATH cases</span><strong>{(payload.summary.systems_with_oath_cases ?? 0).toLocaleString()}</strong><small>Exact summons/ticket matches</small></article><article><span>Source duplicate rows</span><strong>{payload.metadata.source_duplicate_registration_rows.toLocaleString()}</strong><small>Removed by system ID</small></article></section>
      <Filters rows={payload.systems} value={filters} onChange={setFilters} onQuick={quick} />
      <section className="workspace"><TowerMap systems={filtered} selectedId={selected?.system_id ?? null} onSelect={selectById} /><SystemTable rows={filtered} onSelect={setSelected} /></section>
    </> : <ChangesView payload={changes} onSelectSystem={selectById} />}
    <footer><div><strong>Source health</strong>{sourceHealth.length === 0 ? <span>Source-health metrics unavailable for this snapshot.</span> : sourceHealth.map(source => <span key={source.source_key}>{source.name} · {source.status} · {source.coverage_percentage == null ? 'coverage n/a' : `${source.coverage_percentage.toFixed(1)}% coverage`} · {source.attached_entity_count.toLocaleString()} attached · {source.displayed_entity_count.toLocaleString()} represented</span>)}</div><div><strong>Source snapshot</strong>{payload.metadata.sources.map(source => <span key={source.dataset_id}>{source.name} · {source.dataset_id} · {source.source_record_count.toLocaleString()} {source.source_query_scope ? 'rows returned by scoped query' : 'source rows'}{source.matched_record_count != null ? ` · ${source.matched_record_count.toLocaleString()} exact-matched cases` : ''}</span>)}</div><div>Rules {payload.metadata.rules_version} · Priority model {payload.metadata.priority_model_version} · History {changes.history_schema_version}</div></footer>
    <DetailPanel row={selected} metadata={payload.metadata} historyEvents={selected ? changes.events.filter(event => event.system_id === selected.system_id) : []} historyStartedAt={changes.history_started_at} onClose={() => setSelected(null)} />
  </main>
}
