import { useCallback, useEffect, useMemo, useState } from 'react'
import { loadSystems } from './data/api'
import type { SystemSummary, SystemsPayload } from './types/data'
import { formatTimestamp } from './domain/labels'
import { DetailPanel } from './components/DetailPanel'
import { Filters, filterSystems, initialFilters, type FilterState } from './components/Filters'
import { SystemTable } from './components/SystemTable'
import { TowerMap } from './components/TowerMap'
import { exportCsv } from './utils/export'

export default function App() {
  const [payload, setPayload] = useState<SystemsPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [filters, setFilters] = useState<FilterState>(initialFilters)
  const [selected, setSelected] = useState<SystemSummary | null>(null)

  useEffect(() => { loadSystems().then(setPayload).catch(err => setError(err instanceof Error ? err.message : 'Unable to load TowerSignal data')) }, [])
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
  if (!payload) return <main className="app-shell"><div className="loading-page"><div className="brand-mark">TS</div><h1>TowerSignal</h1><p>Loading current NYC public-record snapshot…</p></div></main>

  const generatedAgeDays = Math.floor((Date.now() - new Date(payload.metadata.generated_at).getTime()) / 86400000)
  const oldestSourceUpdateDays = Math.max(0, ...payload.metadata.sources.map(source => source.source_last_updated_at ? Math.floor((Date.now() - new Date(source.source_last_updated_at).getTime()) / 86400000) : 0))
  return <main className="app-shell">
    <header className="topbar"><div><div className="brand"><span className="brand-mark">TS</span><div><h1>TowerSignal</h1><p>NYC cooling-tower compliance intelligence</p></div></div></div><div className="freshness"><span>Data refreshed</span><strong>{formatTimestamp(payload.metadata.generated_at)}</strong>{generatedAgeDays > 2 && <em>Snapshot is older than expected</em>}{oldestSourceUpdateDays > 30 && <em>One source was last updated {oldestSourceUpdateDays} days ago</em>}</div></header>
    <section className="hero"><div><span className="eyebrow">Source-backed commercial intelligence</span><h2>Find cooling-tower systems worth investigating today.</h2><p>Turn public registration, sampling, NYC Health inspection and exact-matched OATH case records into transparent commercial intelligence — with evidence and uncertainty kept separate.</p></div><div className="hero-actions"><button className="primary" onClick={() => exportCsv(filtered, payload.metadata)}>Export filtered CSV</button><span>{filtered.length.toLocaleString()} records in current lead set</span></div></section>
    <section className="disclaimer"><strong>Responsible-use notice.</strong> TowerSignal provides commercial intelligence derived from public records. Signals are not legal advice, health advice, or definitive determinations of regulatory compliance. Public records may be incomplete or delayed. Verify current operating, testing, maintenance and compliance status before relying on a signal or contacting a property.</section>
    <section className="kpis"><article><span>Registered systems</span><strong>{payload.summary.registered_systems.toLocaleString()}</strong><small>Normalized public inventory</small></article><article><span>Active equipment</span><strong>{payload.summary.active_equipment.toLocaleString()}</strong><small>Published equipment count</small></article><article><span>Potential sampling gaps</span><strong>{payload.summary.potential_sampling_gaps.toLocaleString()}</strong><small>Verification signals, not violations</small></article><article><span>Recent confirmed violations</span><strong>{payload.summary.recent_confirmed_violations.toLocaleString()}</strong><small>Official NYC Health records</small></article><article><span>Systems with OATH cases</span><strong>{(payload.summary.systems_with_oath_cases ?? 0).toLocaleString()}</strong><small>Exact summons/ticket matches</small></article><article><span>Source duplicate rows</span><strong>{payload.metadata.source_duplicate_registration_rows.toLocaleString()}</strong><small>Removed by system ID</small></article></section>
    <Filters rows={payload.systems} value={filters} onChange={setFilters} onQuick={quick} />
    <section className="workspace"><TowerMap systems={filtered} selectedId={selected?.system_id ?? null} onSelect={selectById} /><SystemTable rows={filtered} onSelect={setSelected} /></section>
    <footer><div><strong>Source snapshot</strong>{payload.metadata.sources.map(source => <span key={source.dataset_id}>{source.name} · {source.dataset_id} · {source.source_record_count.toLocaleString()} rows{source.matched_record_count != null ? ` · ${source.matched_record_count.toLocaleString()} matched cases` : ''}</span>)}</div><div>Rules {payload.metadata.rules_version} · Priority model {payload.metadata.priority_model_version}</div></footer>
    <DetailPanel row={selected} metadata={payload.metadata} onClose={() => setSelected(null)} />
  </main>
}
