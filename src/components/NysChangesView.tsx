import { useMemo, useState } from 'react'
import type { NysChangeEvent, NysChangeEventType, NysChangesPayload, NysSystem } from '../types/nys'
import { formatDate, formatTimestamp } from '../domain/labels'

const EVENT_LABELS: Record<NysChangeEventType, string> = {
  NYS_EQUIPMENT_FIRST_SEEN: 'New equipment observed',
  NYS_EQUIPMENT_NO_LONGER_PRESENT: 'Equipment no longer present',
  NYS_REG_COMPLIANCE_CHANGED: 'Compliance status changed',
  NYS_CT_STATUS_CHANGED: 'NYS cooling-tower status changed',
  NYS_SAMPLE_DATE_CHANGED: 'Sample date changed',
  NYS_SAMPLE_RESULT_CHANGED: 'Sample result changed',
  NYS_OPERATION_DURATION_CHANGED: 'Operating status changed',
}

const QUICK_GROUPS: Array<{ label: string; types: NysChangeEventType[] | null }> = [
  { label: 'All changes', types: null },
  { label: 'New equipment', types: ['NYS_EQUIPMENT_FIRST_SEEN'] },
  { label: 'Compliance', types: ['NYS_REG_COMPLIANCE_CHANGED'] },
  { label: 'Tower status', types: ['NYS_CT_STATUS_CHANGED'] },
  { label: 'Sampling', types: ['NYS_SAMPLE_DATE_CHANGED', 'NYS_SAMPLE_RESULT_CHANGED'] },
  { label: 'Operation', types: ['NYS_OPERATION_DURATION_CHANGED'] },
]

function compactValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

function tone(type: NysChangeEventType): string {
  if (type === 'NYS_REG_COMPLIANCE_CHANGED') return 'warning'
  if (type.includes('SAMPLE')) return 'blue'
  if (type === 'NYS_EQUIPMENT_NO_LONGER_PRESENT') return 'urgent'
  if (type === 'NYS_EQUIPMENT_FIRST_SEEN') return 'success'
  return 'neutral'
}

export function NysChangesView({ payload, systems, onSelect }: { payload: NysChangesPayload; systems: NysSystem[]; onSelect: (row: NysSystem | null) => void }) {
  const [days, setDays] = useState('30')
  const [eventType, setEventType] = useState('')
  const [sourceCounty, setSourceCounty] = useState('')
  const [city, setCity] = useState('')
  const [compliance, setCompliance] = useState('')
  const [status, setStatus] = useState('')
  const [quickLabel, setQuickLabel] = useState('All changes')
  const [quickTypes, setQuickTypes] = useState<NysChangeEventType[] | null>(null)
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')
  const [page, setPage] = useState(0)

  const systemsById = useMemo(() => new Map(systems.map(row => [row.system_id, row])), [systems])
  const filtered = useMemo(() => payload.events.filter(event => {
    const detected = new Date(event.detected_at).getTime()
    const now = Date.now()
    const current = systemsById.get(event.system_id)
    if (days === 'custom') {
      if (customStart && detected < new Date(`${customStart}T00:00:00`).getTime()) return false
      if (customEnd && detected > new Date(`${customEnd}T23:59:59`).getTime()) return false
    } else if (Number(days) > 0 && detected < now - Number(days) * 86400000) return false
    if (eventType && event.event_type !== eventType) return false
    if (sourceCounty && event.source_county !== sourceCounty) return false
    if (city && event.city !== city) return false
    if (quickTypes && !quickTypes.includes(event.event_type)) return false
    if (compliance && current?.regulation_compliance !== compliance) return false
    if (status && current?.ct_status !== status) return false
    return true
  }), [payload.events, systemsById, days, eventType, sourceCounty, city, quickTypes, compliance, status, customStart, customEnd])

  const eventTypes = [...new Set(payload.events.map(event => event.event_type))]
  const counties = [...new Set(payload.events.map(event => event.source_county).filter(Boolean))].sort() as string[]
  const cities = [...new Set(payload.events.map(event => event.city).filter(Boolean))].sort() as string[]
  const complianceValues = [...new Set(systems.map(row => row.regulation_compliance).filter(Boolean))].sort() as string[]
  const statusValues = [...new Set(systems.map(row => row.ct_status).filter(Boolean))].sort() as string[]
  const pageSize = 50
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const pageRows = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize)

  const clear = () => {
    setDays('30'); setEventType(''); setSourceCounty(''); setCity(''); setCompliance(''); setStatus('');
    setQuickLabel('All changes'); setQuickTypes(null); setPage(0)
  }

  return <section className="changes-view changes-table-view nys-dense-changes" aria-label="TowerSignal NYS changes">
    {payload.baseline_initialized && <div className="disclaimer"><strong>NYS historical baseline initialized.</strong> Existing Equipment_ID records are not being mislabeled as new. Later weekly snapshots are compared with this preserved statewide baseline.</div>}

    <div className="change-workspace-grid">
      <aside className="change-filter-rail" aria-label="NYS change filters">
        <div className="change-filter-heading"><span className="page-kicker">Filters</span><button onClick={clear}>Clear all</button></div>
        <label>Time range<select value={days} onChange={event => { setDays(event.target.value); setPage(0) }}><option value="7">Past 7 days</option><option value="30">Past 30 days</option><option value="90">Past 90 days</option><option value="custom">Custom dates</option><option value="0">All retained</option></select></label>
        {days === 'custom' && <><label>From<input type="date" value={customStart} onChange={event => setCustomStart(event.target.value)} /></label><label>To<input type="date" value={customEnd} onChange={event => setCustomEnd(event.target.value)} /></label></>}
        <label>Change type<select value={eventType} onChange={event => { setEventType(event.target.value); setQuickLabel('All changes'); setQuickTypes(null); setPage(0) }}><option value="">All change types</option>{eventTypes.map(value => <option key={value} value={value}>{EVENT_LABELS[value]}</option>)}</select></label>
        <label>Current compliance<select value={compliance} onChange={event => { setCompliance(event.target.value); setPage(0) }}><option value="">All compliance statuses</option>{complianceValues.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Current tower status<select value={status} onChange={event => { setStatus(event.target.value); setPage(0) }}><option value="">All statuses</option>{statusValues.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Published county<select value={sourceCounty} onChange={event => { setSourceCounty(event.target.value); setPage(0) }}><option value="">All counties</option>{counties.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>City<select value={city} onChange={event => { setCity(event.target.value); setPage(0) }}><option value="">All cities</option>{cities.map(value => <option key={value}>{value}</option>)}</select></label>
      </aside>

      <div className="change-table-workspace">
        <div className="change-table-topline"><div><span className="page-kicker">NYS historical intelligence</span><h2>What changed in the statewide registry?</h2><p>Official weekly NYS snapshots remain separate from NYC scoring and regulatory history. Changes are keyed to source Equipment_ID records.</p></div><div className="history-status compact"><span>NYS history collection began</span><strong>{formatTimestamp(payload.history_started_at)}</strong><small>Latest observation {formatTimestamp(payload.observed_at)}</small></div></div>

        <div className="change-tabs" role="tablist" aria-label="NYS change categories">{QUICK_GROUPS.map(group => <button key={group.label} className={quickLabel === group.label ? 'active' : ''} onClick={() => { setQuickLabel(group.label); setQuickTypes(group.types); setEventType(''); setPage(0) }}>{group.label}<span>{group.label === 'All changes' ? payload.events.length : ''}</span></button>)}</div>

        <div className="reference-table-card monitor-change-table-card">
          <div className="reference-table-heading"><div><strong>{filtered.length.toLocaleString()} NYS changes</strong><span>{pageRows.length ? `Showing ${safePage * pageSize + 1}–${safePage * pageSize + pageRows.length}` : 'No matching changes'} · source-native statewide history</span></div></div>
          {pageRows.length === 0 ? <div className="reference-empty-state compact"><strong>No observed NYS changes match these filters.</strong><span>Adjust the period or source-native status filters to inspect retained NYS history.</span></div> : <div className="reference-table-scroll"><table className="reference-table nys-change-reference-table"><thead><tr><th>Facility / equipment</th><th>City</th><th>County</th><th>Change</th><th>Prior value</th><th>New value</th><th>Date observed</th><th>Current tower status</th><th>Current compliance</th><th>Evidence</th><th>Action</th></tr></thead><tbody>{pageRows.map((event, index) => <NysChangeRow key={`${event.detected_at}-${event.system_id}-${event.event_type}-${index}`} event={event} current={systemsById.get(event.system_id) ?? null} onSelect={onSelect} />)}</tbody></table></div>}
          {pageCount > 1 && <div className="reference-pagination"><span>Page {safePage + 1} of {pageCount}</span><div><button disabled={safePage === 0} onClick={() => setPage(Math.max(0, safePage - 1))}>Previous</button><button disabled={safePage >= pageCount - 1} onClick={() => setPage(Math.min(pageCount - 1, safePage + 1))}>Next</button></div></div>}
        </div>
      </div>
    </div>
  </section>
}

function NysChangeRow({ event, current, onSelect }: { event: NysChangeEvent; current: NysSystem | null; onSelect: (row: NysSystem | null) => void }) {
  return <tr className="change-reference-row" onClick={() => current && onSelect(current)}>
    <td><strong>{event.address ?? event.system_id}</strong><small>Equipment {event.source_equipment_id ?? event.system_id}</small></td>
    <td>{event.city ?? '—'}</td>
    <td>{event.source_county ?? '—'}</td>
    <td><span className={`change-kind change-kind-${tone(event.event_type)}`}>{EVENT_LABELS[event.event_type]}</span></td>
    <td><span className="change-old-value">{compactValue(event.previous_value)}</span></td>
    <td><strong>{compactValue(event.new_value)}</strong></td>
    <td><strong>{formatTimestamp(event.detected_at)}</strong>{event.source_observation_date && <small>source {formatDate(event.source_observation_date)}</small>}</td>
    <td>{current?.ct_status ?? '—'}</td>
    <td>{current?.regulation_compliance ? <span className={`nys-current-status ${current.regulation_compliance.toLowerCase().includes('non') ? 'noncompliant' : 'compliant'}`}>{current.regulation_compliance}</span> : '—'}</td>
    <td><strong>Evidence: {event.evidence_basis}</strong><small>NYS weekly registry</small></td>
    <td>{current ? <button className="table-link" onClick={click => { click.stopPropagation(); onSelect(current) }}>Open →</button> : <span className="muted-label">Not current</span>}</td>
  </tr>
}
