import { useMemo, useState } from 'react'
import type { NysChangeEvent, NysChangeEventType, NysChangesPayload, NysSystem } from '../types/nys'
import { formatDate, formatTimestamp } from '../domain/labels'

const INITIAL_VISIBLE_EVENTS = 1

const EVENT_LABELS: Record<NysChangeEventType, string> = {
  NYS_EQUIPMENT_FIRST_SEEN: 'New NYS equipment observed',
  NYS_EQUIPMENT_NO_LONGER_PRESENT: 'No longer present in current NYS snapshot',
  NYS_REG_COMPLIANCE_CHANGED: 'NYS registration compliance changed',
  NYS_CT_STATUS_CHANGED: 'NYS cooling-tower status changed',
  NYS_SAMPLE_DATE_CHANGED: 'NYS latest sample date changed',
  NYS_SAMPLE_RESULT_CHANGED: 'NYS latest sample result changed',
  NYS_OPERATION_DURATION_CHANGED: 'NYS operation duration changed',
}

const QUICK_GROUPS: Record<string, NysChangeEventType[]> = {
  'New equipment': ['NYS_EQUIPMENT_FIRST_SEEN'],
  'Compliance': ['NYS_REG_COMPLIANCE_CHANGED'],
  'Registry status': ['NYS_CT_STATUS_CHANGED'],
  'Sampling': ['NYS_SAMPLE_DATE_CHANGED', 'NYS_SAMPLE_RESULT_CHANGED'],
}

function compactValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

function relativeTime(timestamp: string): string {
  const ms = Date.now() - new Date(timestamp).getTime()
  const hours = Math.max(0, Math.floor(ms / 3600000))
  if (hours < 1) return 'less than 1 hour ago'
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
  const days = Math.floor(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

export function NysChangesView({ payload, systems, onSelect }: { payload: NysChangesPayload; systems: NysSystem[]; onSelect: (row: NysSystem | null) => void }) {
  const [days, setDays] = useState('7')
  const [eventType, setEventType] = useState('')
  const [sourceCounty, setSourceCounty] = useState('')
  const [quickTypes, setQuickTypes] = useState<NysChangeEventType[] | null>(null)
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')
  const [visibleLimit, setVisibleLimit] = useState(INITIAL_VISIBLE_EVENTS)

  const filtered = useMemo(() => payload.events.filter(event => {
    const detected = new Date(event.detected_at).getTime()
    const now = Date.now()
    if (days === 'custom') {
      if (customStart && detected < new Date(`${customStart}T00:00:00`).getTime()) return false
      if (customEnd && detected > new Date(`${customEnd}T23:59:59`).getTime()) return false
    } else if (Number(days) > 0 && detected < now - Number(days) * 86400000) return false
    if (eventType && event.event_type !== eventType) return false
    if (sourceCounty && event.source_county !== sourceCounty) return false
    if (quickTypes && !quickTypes.includes(event.event_type)) return false
    return true
  }), [payload.events, days, eventType, sourceCounty, quickTypes, customStart, customEnd])

  const eventTypes = [...new Set(payload.events.map(event => event.event_type))]
  const counties = [...new Set(payload.events.map(event => event.source_county).filter(Boolean))].sort() as string[]
  const systemById = useMemo(() => new Map(systems.map(row => [row.system_id, row])), [systems])
  const visibleEvents = filtered.slice(0, 0)
  const resetVisible = () => setVisibleLimit(INITIAL_VISIBLE_EVENTS)

  return <section className="changes-view" aria-label="TowerSignal NYS changes">
    <div className="changes-intro"><div><span className="eyebrow">NYS historical intelligence</span><h2>What changed in the statewide registry?</h2><p>TowerSignal preserves the official weekly NYS snapshot separately from NYC history. Detection time is when TowerSignal first observed a difference; a source sample date is shown only when the source publishes one for that field.</p></div><div className="history-status"><span>NYS history collection began</span><strong>{formatTimestamp(payload.history_started_at)}</strong><small>Latest observation {formatTimestamp(payload.observed_at)}</small></div></div>

    {payload.baseline_initialized && <div className="disclaimer"><strong>NYS historical baseline initialized.</strong> Existing Equipment_ID records are not being mislabeled as new. Future weekly snapshots can now produce deterministic source-status changes.</div>}

    <div className="quick-change-filters"><strong>New this week</strong>{Object.entries(QUICK_GROUPS).map(([label, types]) => <button key={label} onClick={() => { setDays('7'); setEventType(''); setQuickTypes(types); resetVisible() }}>{label}</button>)}<button onClick={() => { setQuickTypes(null); resetVisible() }}>All changes</button></div>

    <div className="change-filters nys-change-filters">
      <label>Period<select value={days} onChange={event => { setDays(event.target.value); setQuickTypes(null); resetVisible() }}><option value="1">Today</option><option value="7">7 days</option><option value="30">30 days</option><option value="custom">Custom</option><option value="0">All retained</option></select></label>
      {days === 'custom' && <><label>From<input type="date" value={customStart} onChange={event => { setCustomStart(event.target.value); resetVisible() }} /></label><label>To<input type="date" value={customEnd} onChange={event => { setCustomEnd(event.target.value); resetVisible() }} /></label></>}
      <label>Event type<select value={eventType} onChange={event => { setEventType(event.target.value); setQuickTypes(null); resetVisible() }}><option value="">All</option>{eventTypes.map(value => <option key={value} value={value}>{EVENT_LABELS[value]}</option>)}</select></label>
      <label>Published county<select value={sourceCounty} onChange={event => { setSourceCounty(event.target.value); resetVisible() }}><option value="">All</option>{counties.map(value => <option key={value}>{value}</option>)}</select></label>
    </div>

    <div className="change-count">{filtered.length.toLocaleString()} NYS change{filtered.length === 1 ? '' : 's'} in current view</div>
    {filtered.length === 0 ? <div className="empty-changes"><strong>No observed NYS changes match these filters.</strong><span>{payload.baseline_initialized ? 'TowerSignal has established the first statewide baseline; later weekly snapshots will be compared against it.' : 'Adjust the period or filters to inspect retained NYS history.'}</span></div> : <>
      <div className="change-list">{visibleEvents.map((event, index) => <NysChangeCard key={`${event.detected_at}-${event.system_id}-${event.event_type}-${index}`} event={event} current={systemById.get(event.system_id) ?? null} onSelect={onSelect} />)}</div>
      {visibleEvents.length < filtered.length && <div className="change-count"><span>Showing {visibleEvents.length.toLocaleString()} of {filtered.length.toLocaleString()} changes</span><button className="link-button" onClick={() => setVisibleLimit(limit => Math.min(limit + INITIAL_VISIBLE_EVENTS, filtered.length))}>Show {Math.min(INITIAL_VISIBLE_EVENTS, filtered.length - visibleEvents.length).toLocaleString()} more</button></div>}
    </>}
  </section>
}

function NysChangeCard({ event, current, onSelect }: { event: NysChangeEvent; current: NysSystem | null; onSelect: (row: NysSystem | null) => void }) {
  return <article className="change-card">
    <div className="change-card-head"><div><span className="change-type">{EVENT_LABELS[event.event_type]}</span><strong>{event.address ?? event.system_id}</strong><small>Equipment {event.source_equipment_id ?? event.system_id}{event.city ? ` · ${event.city}` : ''}</small></div><div className="change-meta"><strong>{relativeTime(event.detected_at)}</strong><small>{formatTimestamp(event.detected_at)}</small></div></div>
    <div className="change-values"><div><span>Previous</span><code>{compactValue(event.previous_value)}</code></div><div><span>New</span><code>{compactValue(event.new_value)}</code></div></div>
    <div className="change-source"><span>Source: NYS Cooling Tower Registry Weekly Extract</span><span>Evidence: {event.evidence_basis}</span>{event.source_observation_date && <span>Source observation: {formatDate(event.source_observation_date)}</span>}{event.source_county && <span>Published county: {event.source_county}</span>}</div>
    {current && <button onClick={() => onSelect(current)}>Open equipment detail</button>}
  </article>
}
