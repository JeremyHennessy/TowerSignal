import type { SystemSummary } from '../types/data'
import type { AcrisSummaryFields } from '../types/acris'

export interface FilterState {
  search: string; borough: string; zip: string; signal: string; confirmed: string; violationType: string; oath: string; hpdContacts: string; acrisActivity: string;
  minSampleDays: string; minEquipment: string; minScore: string; maxScore: string
}

export const initialFilters: FilterState = { search:'', borough:'', zip:'', signal:'', confirmed:'', violationType:'', oath:'', hpdContacts:'', acrisActivity:'', minSampleDays:'', minEquipment:'', minScore:'', maxScore:'' }

export function filterSystems(rows: SystemSummary[], filters: FilterState): SystemSummary[] {
  const q = filters.search.trim().toLowerCase()
  return rows.filter((row) => {
    const acris = row as SystemSummary & AcrisSummaryFields
    if (q && ![row.address,row.system_id,row.bin,row.bbl,row.zip,row.borough].some((value) => String(value ?? '').toLowerCase().includes(q))) return false
    if (filters.borough && row.borough !== filters.borough) return false
    if (filters.zip && row.zip !== filters.zip) return false
    if (filters.signal && !row.signal_types.includes(filters.signal) && !(filters.signal === 'NO_CURRENT_SIGNAL' && row.primary_signal === 'NO_CURRENT_SIGNAL')) return false
    if (filters.confirmed && String(row.confirmed_violation) !== filters.confirmed) return false
    if (filters.violationType && !row.violation_types.includes(filters.violationType)) return false
    if (filters.oath === 'true' && (row.oath_case_count ?? 0) < 1) return false
    if (filters.oath === 'false' && (row.oath_case_count ?? 0) > 0) return false
    if (filters.hpdContacts === 'true' && (row.hpd_contact_count ?? 0) < 1) return false
    if (filters.hpdContacts === 'false' && (row.hpd_contact_count ?? 0) > 0) return false
    if (filters.acrisActivity === 'true' && (acris.acris_recent_document_count ?? 0) < 1) return false
    if (filters.minSampleDays && (row.days_since_latest_sample == null || row.days_since_latest_sample < Number(filters.minSampleDays))) return false
    if (filters.minEquipment && row.active_equipment < Number(filters.minEquipment)) return false
    if (filters.minScore && row.priority_score < Number(filters.minScore)) return false
    if (filters.maxScore && row.priority_score > Number(filters.maxScore)) return false
    return true
  })
}

const labels: Partial<Record<keyof FilterState, string>> = {
  borough: 'Borough', zip: 'ZIP', signal: 'Signal', confirmed: 'Violation', violationType: 'Violation type', oath: 'OATH', hpdContacts: 'Contacts', acrisActivity: 'ACRIS activity', minSampleDays: 'Sample age', minEquipment: 'Equipment', minScore: 'Min score', maxScore: 'Max score', search: 'Search',
}

export function Filters({ rows, value, onChange, onQuick, acrisAvailable = false }: { rows: SystemSummary[]; value: FilterState; onChange: (next: FilterState) => void; onQuick: (kind: string) => void; acrisAvailable?: boolean }) {
  const boroughs = [...new Set(rows.map(r => r.borough).filter(Boolean) as string[])].sort()
  const zips = [...new Set(rows.map(r => r.zip).filter(Boolean) as string[])].sort()
  const violationTypes = [...new Set(rows.flatMap(r => r.violation_types))].sort()
  const set = (key: keyof FilterState, next: string) => onChange({ ...value, [key]: next })
  const active = (Object.entries(value) as [keyof FilterState, string][]).filter(([, entry]) => entry !== '')
  const quickFilters = ['Highest priority','Sampling-gap signals','OATH cases',...(acrisAvailable ? ['Recent ACRIS activity'] : []),'Confirmed violations','No sample date','3+ active units','Manhattan']
  return <section className="filters filter-panel" aria-label="Lead filters">
    <div className="filter-panel-head"><div><span className="eyebrow">Account criteria</span><h3>Filter prospects</h3></div>{active.length > 0 && <button className="link-button" onClick={() => onChange(initialFilters)}>Clear all</button>}</div>
    <label className="search-field"><span>Search accounts</span><input value={value.search} onChange={e => set('search', e.target.value)} placeholder="Address, system ID, BIN…" /></label>
    {active.length > 0 && <div className="active-filter-chips" aria-label="Active filters">{active.filter(([key]) => key !== 'search').map(([key, entry]) => <button key={key} onClick={() => set(key, '')}><span>{labels[key]}:</span> {entry === 'true' ? 'Yes' : entry === 'false' ? 'No' : entry} ×</button>)}</div>}
    <div className="quick-filters" aria-label="Quick filters">
      {quickFilters.map(label => <button key={label} className="quick" onClick={() => onQuick(label)}>{label}</button>)}
    </div>
    <div className="filter-grid filter-stack">
      <label>Borough<select value={value.borough} onChange={e => set('borough', e.target.value)}><option value="">All boroughs</option>{boroughs.map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Timing signal<select value={value.signal} onChange={e => set('signal', e.target.value)}><option value="">All signals</option><option value="CONFIRMED_RECENT_VIOLATION">Confirmed violation</option><option value="POTENTIAL_SAMPLING_GAP">Potential sampling gap</option><option value="NO_PUBLIC_SAMPLE_DATE">No public sample date</option><option value="MULTIPLE_ACTIVE_EQUIPMENT">Multiple active equipment</option></select></label>
      <label>Contact availability<select value={value.hpdContacts} onChange={e => set('hpdContacts', e.target.value)}><option value="">Either</option><option value="true">HPD contacts present</option><option value="false">No HPD contacts matched</option></select></label>
      <label>OATH activity<select value={value.oath} onChange={e => set('oath', e.target.value)}><option value="">Either</option><option value="true">Exact case match</option><option value="false">No exact case match</option></select></label>
      <label>ACRIS recorded activity<select aria-label="ACRIS recorded activity" value={value.acrisActivity ?? ''} onChange={e => set('acrisActivity', e.target.value)} disabled={!acrisAvailable}><option value="">{acrisAvailable ? 'Any' : 'Verified cache unavailable'}</option>{acrisAvailable && <option value="true">Recent exact-BBL activity</option>}</select></label>
      <label>Confirmed violation<select value={value.confirmed} onChange={e => set('confirmed', e.target.value)}><option value="">Either</option><option value="true">Yes</option><option value="false">No</option></select></label>
      <label>ZIP<select value={value.zip} onChange={e => set('zip', e.target.value)}><option value="">All ZIPs</option>{zips.map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Violation type<select value={value.violationType} onChange={e => set('violationType', e.target.value)}><option value="">All types</option>{violationTypes.map(v => <option key={v}>{v}</option>)}</select></label>
      <label>Min days since sample<input type="number" min="0" value={value.minSampleDays} onChange={e => set('minSampleDays', e.target.value)} placeholder="Any" /></label>
      <label>Min active equipment<input type="number" min="0" value={value.minEquipment} onChange={e => set('minEquipment', e.target.value)} placeholder="Any" /></label>
      <label>Priority score<div className="range-pair"><input aria-label="Minimum priority score" type="number" min="0" max="100" placeholder="Min" value={value.minScore} onChange={e => set('minScore', e.target.value)} /><input aria-label="Maximum priority score" type="number" min="0" max="100" placeholder="Max" value={value.maxScore} onChange={e => set('maxScore', e.target.value)} /></div></label>
    </div>
  </section>
}
