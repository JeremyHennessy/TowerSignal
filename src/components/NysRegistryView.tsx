import { useMemo, useState } from 'react'
import type { NysSystem, NysSystemsPayload } from '../types/nys'
import { formatTimestamp } from '../domain/labels'
import { NysTowerMap } from './NysTowerMap'
import { NysSystemTable } from './NysSystemTable'
import { NysDetailPanel } from './NysDetailPanel'

export interface NysFilterState {
  search: string
  compliance: string
  status: string
  result: string
  operation: string
  sourceCounty: string
  multiEquipmentOnly: boolean
}

const EMPTY_FILTERS: NysFilterState = {
  search: '', compliance: '', status: '', result: '', operation: '', sourceCounty: '', multiEquipmentOnly: false,
}

export function filterNysSystems(rows: NysSystem[], filters: NysFilterState): NysSystem[] {
  const term = filters.search.trim().toLowerCase()
  return rows.filter(row => {
    if (term) {
      const haystack = [row.address, row.city, row.zip, row.source_county, row.source_equipment_id, row.system_id]
        .filter(Boolean).join(' ').toLowerCase()
      if (!haystack.includes(term)) return false
    }
    if (filters.compliance && row.regulation_compliance !== filters.compliance) return false
    if (filters.status && row.ct_status !== filters.status) return false
    if (filters.result && row.latest_sample_result !== filters.result) return false
    if (filters.operation && row.operation_duration !== filters.operation) return false
    if (filters.sourceCounty && row.source_county !== filters.sourceCounty) return false
    if (filters.multiEquipmentOnly && row.property_equipment_count <= 1) return false
    return true
  })
}

export function NysRegistryView({ payload, selected, onSelect }: { payload: NysSystemsPayload; selected: NysSystem | null; onSelect: (row: NysSystem | null) => void }) {
  const [filters, setFilters] = useState<NysFilterState>(EMPTY_FILTERS)
  const filtered = useMemo(() => filterNysSystems(payload.systems, filters), [payload.systems, filters])
  const statuses = [...new Set(payload.systems.map(row => row.ct_status).filter(Boolean))].sort() as string[]
  const results = [...new Set(payload.systems.map(row => row.latest_sample_result).filter(Boolean))].sort() as string[]
  const operations = [...new Set(payload.systems.map(row => row.operation_duration).filter(Boolean))].sort() as string[]
  const counties = [...new Set(payload.systems.map(row => row.source_county).filter(Boolean))].sort() as string[]
  const sourceHealth = payload.metadata.source_health?.find(entry => entry.source_key === 'nys_registry')
  const set = (patch: Partial<NysFilterState>) => setFilters(current => ({ ...current, ...patch }))

  return <>
    <section className="hero"><div><span className="eyebrow">New York State source regime</span><h2>Statewide cooling-tower registry intelligence without projecting NYC rules.</h2><p>Explore current NYS Equipment_ID records, source-published compliance and operating status, Legionella sample/result context, and exact published-address equipment clusters.</p></div><div className="hero-actions"><strong>{sourceHealth ? `NYS source health ${sourceHealth.status}` : 'NYS source health unavailable'}</strong><span>Generated {formatTimestamp(payload.metadata.generated_at)}</span><span>{payload.metadata.source.source_record_count.toLocaleString()} source rows · {payload.summary.mapped_equipment.toLocaleString()} mapped</span></div></section>

    <div className="disclaimer"><strong>Separate evidence regime.</strong> NYS values are represented directly from the official weekly extract. NYC Priority Score, NYC Health inspections, OATH, PLUTO and HPD are not applied here. The source is a weekly snapshot; TowerSignal preserves separate NYS observations going forward. Published county is retained as provenance but is not used alone to identify NYC because the live source contains inconsistent county labels.</div>

    <section className="kpis">
      <article><span>Registered equipment</span><strong>{payload.summary.registered_equipment.toLocaleString()}</strong><small>Unique source Equipment_IDs</small></article>
      <article><span>Source non-compliant</span><strong>{payload.summary.non_compliant.toLocaleString()}</strong><small>Published Reg_Comp</small></article>
      <article><span>Sample required</span><strong>{payload.summary.sample_required.toLocaleString()}</strong><small>Published CT_Status</small></article>
      <article><span>Disinfection required</span><strong>{payload.summary.disinfection_required.toLocaleString()}</strong><small>Published CT_Status</small></article>
      <article><span>Multi-equipment properties</span><strong>{payload.summary.multi_equipment_properties.toLocaleString()}</strong><small>Exact address + city + ZIP key</small></article>
    </section>

    <section className="filters" aria-label="NYS registry filters">
      <div className="quick-filters"><button className="quick" onClick={() => set({ compliance: 'Non-compliant', status: '' })}>Non-compliant</button><button className="quick" onClick={() => set({ status: 'Sample_Required', compliance: '' })}>Sample required</button><button className="quick" onClick={() => set({ status: 'Disinfection Required', compliance: '' })}>Disinfection required</button><button className="quick" onClick={() => set({ status: 'Missing Legionella Result', compliance: '' })}>Missing result</button><button className="quick" onClick={() => set({ multiEquipmentOnly: true })}>Multi-equipment property</button><button className="quick subtle" onClick={() => setFilters(EMPTY_FILTERS)}>Clear filters</button></div>
      <div className="filter-grid nys-filter-grid">
        <label>Search<input value={filters.search} onChange={event => set({ search: event.target.value })} placeholder="Address, city, ZIP, equipment ID" /></label>
        <label>Compliance<select value={filters.compliance} onChange={event => set({ compliance: event.target.value })}><option value="">All</option><option>Compliant</option><option>Non-compliant</option></select></label>
        <label>Registry status<select value={filters.status} onChange={event => set({ status: event.target.value })}><option value="">All</option>{statuses.map(value => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select></label>
        <label>Legionella result<select value={filters.result} onChange={event => set({ result: event.target.value })}><option value="">All</option>{results.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Operation<select value={filters.operation} onChange={event => set({ operation: event.target.value })}><option value="">All</option>{operations.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Published county<select value={filters.sourceCounty} onChange={event => set({ sourceCounty: event.target.value })}><option value="">All</option>{counties.map(value => <option key={value}>{value}</option>)}</select></label>
        <label className="nys-checkbox-label"><input type="checkbox" checked={filters.multiEquipmentOnly} onChange={event => set({ multiEquipmentOnly: event.target.checked })} />Multi-equipment property</label>
      </div>
    </section>

    <main className="workspace"><NysTowerMap systems={filtered} selectedId={selected?.system_id ?? null} onSelect={id => onSelect(payload.systems.find(row => row.system_id === id) ?? null)} /><NysSystemTable rows={filtered} onSelect={onSelect} /></main>
    <NysDetailPanel row={selected} metadata={payload.metadata} onClose={() => onSelect(null)} />
  </>
}