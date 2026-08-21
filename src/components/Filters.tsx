import type { SystemSummary } from '../types/data'

export interface FilterState {
  search: string; borough: string; zip: string; signal: string; confirmed: string; violationType: string; oath: string;
  minSampleDays: string; minEquipment: string; minScore: string; maxScore: string
}

export const initialFilters: FilterState = { search:'', borough:'', zip:'', signal:'', confirmed:'', violationType:'', oath:'', minSampleDays:'', minEquipment:'', minScore:'', maxScore:'' }

export function filterSystems(rows: SystemSummary[], filters: FilterState): SystemSummary[] {
  const q = filters.search.trim().toLowerCase()
  return rows.filter((row) => {
    if (q && ![row.address,row.system_id,row.bin,row.bbl,row.zip,row.borough].some((value) => String(value ?? '').toLowerCase().includes(q))) return false
    if (filters.borough && row.borough !== filters.borough) return false
    if (filters.zip && row.zip !== filters.zip) return false
    if (filters.signal && !row.signal_types.includes(filters.signal) && !(filters.signal === 'NO_CURRENT_SIGNAL' && row.primary_signal === 'NO_CURRENT_SIGNAL')) return false
    if (filters.confirmed && String(row.confirmed_violation) !== filters.confirmed) return false
    if (filters.violationType && !row.violation_types.includes(filters.violationType)) return false
    if (filters.oath === 'true' && (row.oath_case_count ?? 0) < 1) return false
    if (filters.oath === 'false' && (row.oath_case_count ?? 0) > 0) return false
    if (filters.minSampleDays && (row.days_since_latest_sample == null || row.days_since_latest_sample < Number(filters.minSampleDays))) return false
    if (filters.minEquipment && row.active_equipment < Number(filters.minEquipment)) return false
    if (filters.minScore && row.priority_score < Number(filters.minScore)) return false
    if (filters.maxScore && row.priority_score > Number(filters.maxScore)) return false
    return true
  })
}

export function Filters({ rows, value, onChange, onQuick }: { rows: SystemSummary[]; value: FilterState; onChange: (next: FilterState) => void; onQuick: (kind: string) => void }) {
  const boroughs = [...new Set(rows.map(r => r.borough).filter(Boolean) as string[])].sort()
  const zips = [...new Set(rows.map(r => r.zip).filter(Boolean) as string[])].sort()
  const violationTypes = [...new Set(rows.flatMap(r => r.violation_types))].sort()
  const set = (key: keyof FilterState, next: string) => onChange({ ...value, [key]: next })
  return <section className="filters" aria-label="Lead filters">
    <div className="quick-filters" aria-label="Quick filters">
      {['Confirmed violations','OATH cases','Sampling-gap signals','No sample date','3+ active units','Manhattan','Highest priority'].map(label => <button key={label} className="quick" onClick={() => onQuick(label)}>{label}</button>)}
      <button className="quick subtle" onClick={() => onChange(initialFilters)}>Clear</button>
    </div>
    <div className="filter-grid">
      <label>Search<input value={value.search} onChange={e => set('search', e.target.value)} placeholder="Address, system ID, BIN…" /></label>
      <label>Borough<select value={value.borough} onChange={e => set('borough', e.target.value)}><option value="">All boroughs</option>{boroughs.map(v => <option key={v}>{v}</option>)}</select></label>
      <label>ZIP<select value={value.zip} onChange={e => set('zip', e.target.value)}><option value="">All ZIPs</option>{zips.map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Signal<select value={value.signal} onChange={e => set('signal', e.target.value)}><option value="">All signals</option><option value="CONFIRMED_RECENT_VIOLATION">Confirmed violation</option><option value="POTENTIAL_SAMPLING_GAP">Potential sampling gap</option><option value="NO_PUBLIC_SAMPLE_DATE">No public sample date</option><option value="MULTIPLE_ACTIVE_EQUIPMENT">Multiple active equipment</option></select></label>
      <label>Confirmed violation<select value={value.confirmed} onChange={e => set('confirmed', e.target.value)}><option value="">Either</option><option value="true">Yes</option><option value="false">No</option></select></label>
      <label>OATH case match<select value={value.oath} onChange={e => set('oath', e.target.value)}><option value="">Either</option><option value="true">Exact match present</option><option value="false">No exact match</option></select></label>
      <label>Violation type<select value={value.violationType} onChange={e => set('violationType', e.target.value)}><option value="">All types</option>{violationTypes.map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Min days since sample<input type="number" min="0" value={value.minSampleDays} onChange={e => set('minSampleDays', e.target.value)} /></label>
      <label>Min active equipment<input type="number" min="0" value={value.minEquipment} onChange={e => set('minEquipment', e.target.value)} /></label>
      <label>Score range<div className="range-pair"><input aria-label="Minimum priority score" type="number" min="0" max="100" placeholder="0" value={value.minScore} onChange={e => set('minScore', e.target.value)} /><input aria-label="Maximum priority score" type="number" min="0" max="100" placeholder="100" value={value.maxScore} onChange={e => set('maxScore', e.target.value)} /></div></label>
    </div>
  </section>
}
