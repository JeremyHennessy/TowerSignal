import { useMemo, useState } from 'react'
import type { ChangeEvent, ChangeEventType, ChangesPayload } from '../types/history'
import { formatDate, formatTimestamp } from '../domain/labels'
import { StatusBadge } from './StatusBadge'

const EVENT_LABELS: Record<string, string> = {
  SYSTEM_FIRST_SEEN: 'New system observed',
  SYSTEM_NO_LONGER_PRESENT: 'No longer present in current registration snapshot',
  ACTIVE_EQUIPMENT_CHANGED: 'Active equipment changed',
  SAMPLE_REPORTED: 'New public sample reported',
  LATEST_SAMPLE_CHANGED: 'Latest public sample changed',
  SAMPLING_GAP_ENTERED: 'Sampling-gap signal entered',
  SAMPLING_GAP_RESOLVED: 'Sampling-gap signal resolved',
  INSPECTION_ADDED: 'New NYC Health inspection',
  VIOLATION_ADDED: 'New confirmed NYC Health violation',
  VIOLATION_STATUS_CHANGED: 'Violation status changed',
  OATH_CASE_ADDED: 'New OATH case activity',
  OATH_STATUS_CHANGED: 'OATH status changed',
  OATH_DECISION_CHANGED: 'OATH decision changed',
  OATH_PENALTY_CHANGED: 'OATH penalty changed',
  OATH_BALANCE_CHANGED: 'OATH balance changed',
  PLUTO_OWNER_CHANGED: 'PLUTO owner changed',
  HPD_REGISTRATION_CHANGED: 'HPD registration changed',
  HPD_CONTACT_ADDED: 'HPD contact added',
  HPD_CONTACT_REMOVED: 'HPD contact removed',
  HPD_MANAGING_AGENT_CHANGED: 'HPD managing-agent record changed',
}

const QUICK_GROUPS: Record<string, ChangeEventType[]> = {
  'New systems': ['SYSTEM_FIRST_SEEN'],
  'New violations': ['VIOLATION_ADDED'],
  'New OATH activity': ['OATH_CASE_ADDED', 'OATH_STATUS_CHANGED', 'OATH_DECISION_CHANGED', 'OATH_PENALTY_CHANGED', 'OATH_BALANCE_CHANGED'],
  'New samples': ['SAMPLE_REPORTED', 'LATEST_SAMPLE_CHANGED'],
  'Property/contact changes': ['PLUTO_OWNER_CHANGED', 'HPD_REGISTRATION_CHANGED', 'HPD_CONTACT_ADDED', 'HPD_CONTACT_REMOVED', 'HPD_MANAGING_AGENT_CHANGED'],
  'Signals entered': ['SAMPLING_GAP_ENTERED'],
  'Signals resolved': ['SAMPLING_GAP_RESOLVED'],
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

export function ChangesView({ payload, onSelectSystem }: { payload: ChangesPayload; onSelectSystem: (systemId: string) => void }) {
  const [days, setDays] = useState('7')
  const [borough, setBorough] = useState('')
  const [eventType, setEventType] = useState('')
  const [minimumPriority, setMinimumPriority] = useState('')
  const [confidence, setConfidence] = useState('')
  const [contactOnly, setContactOnly] = useState(false)
  const [quickTypes, setQuickTypes] = useState<ChangeEventType[] | null>(null)
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')

  const filtered = useMemo(() => payload.events.filter(event => {
    const detected = new Date(event.detected_at).getTime()
    const now = Date.now()
    if (days === 'custom') {
      if (customStart && detected < new Date(`${customStart}T00:00:00`).getTime()) return false
      if (customEnd && detected > new Date(`${customEnd}T23:59:59`).getTime()) return false
    } else if (Number(days) > 0 && detected < now - Number(days) * 86400000) return false
    if (borough && event.borough !== borough) return false
    if (eventType && event.event_type !== eventType) return false
    if (quickTypes && !quickTypes.includes(event.event_type)) return false
    if (minimumPriority && (event.priority_score ?? 0) < Number(minimumPriority)) return false
    if (confidence && event.evidence_confidence !== confidence) return false
    if (contactOnly && !event.contact_available) return false
    return true
  }), [payload.events, days, borough, eventType, minimumPriority, confidence, contactOnly, quickTypes, customStart, customEnd])

  const boroughs = [...new Set(payload.events.map(event => event.borough).filter(Boolean))] as string[]
  const eventTypes = [...new Set(payload.events.map(event => event.event_type))]

  return <section className="changes-view" aria-label="TowerSignal changes">
    <div className="changes-intro"><div><span className="eyebrow">Historical intelligence</span><h2>What changed?</h2><p>TowerSignal compares preserved source-backed observations. Detection time is when TowerSignal first observed a difference; source dates are shown separately when available.</p></div><div className="history-status"><span>History collection began</span><strong>{formatTimestamp(payload.history_started_at)}</strong><small>Latest observation {formatTimestamp(payload.observed_at)}</small></div></div>

    {payload.baseline_initialized && <div className="disclaimer"><strong>Historical baseline initialized.</strong> This is TowerSignal's first preserved observation. Existing systems are not being mislabeled as newly registered. Change events will accumulate as later refreshes differ from this baseline.</div>}

    <div className="quick-change-filters"><strong>New this week</strong>{Object.entries(QUICK_GROUPS).map(([label, types]) => <button key={label} className={quickTypes === types ? 'active' : ''} onClick={() => { setDays('7'); setEventType(''); setQuickTypes(types) }}>{label}</button>)}<button onClick={() => setQuickTypes(null)}>All changes</button></div>

    <div className="change-filters">
      <label>Period<select value={days} onChange={event => { setDays(event.target.value); setQuickTypes(null) }}><option value="1">Today</option><option value="7">7 days</option><option value="30">30 days</option><option value="custom">Custom</option><option value="0">All retained</option></select></label>
      {days === 'custom' && <><label>From<input type="date" value={customStart} onChange={event => setCustomStart(event.target.value)} /></label><label>To<input type="date" value={customEnd} onChange={event => setCustomEnd(event.target.value)} /></label></>}
      <label>Borough<select value={borough} onChange={event => setBorough(event.target.value)}><option value="">All</option>{boroughs.map(value => <option key={value}>{value}</option>)}</select></label>
      <label>Event type<select value={eventType} onChange={event => { setEventType(event.target.value); setQuickTypes(null) }}><option value="">All</option>{eventTypes.map(value => <option key={value} value={value}>{EVENT_LABELS[value] ?? value}</option>)}</select></label>
      <label>Minimum priority<input type="number" min="0" max="100" value={minimumPriority} onChange={event => setMinimumPriority(event.target.value)} placeholder="0" /></label>
      <label>Evidence<select value={confidence} onChange={event => setConfidence(event.target.value)}><option value="">All</option><option value="CONFIRMED">Confirmed</option><option value="STRONG_SIGNAL">Strong signal</option><option value="VERIFY">Verify</option></select></label>
      <label className="checkbox-label"><input type="checkbox" checked={contactOnly} onChange={event => setContactOnly(event.target.checked)} />Contact available</label>
    </div>

    <div className="change-count">{filtered.length.toLocaleString()} change{filtered.length === 1 ? '' : 's'} in current view</div>
    {filtered.length === 0 ? <div className="empty-changes"><strong>No observed changes match these filters.</strong><span>{payload.baseline_initialized ? 'TowerSignal has established the first historical baseline; future refreshes will be compared against it.' : 'Adjust the period or filters to inspect retained history.'}</span></div> : <div className="change-list">{filtered.map((event, index) => <ChangeCard key={`${event.detected_at}-${event.system_id}-${event.event_type}-${index}`} event={event} onSelectSystem={onSelectSystem} />)}</div>}
  </section>
}

function ChangeCard({ event, onSelectSystem }: { event: ChangeEvent; onSelectSystem: (systemId: string) => void }) {
  return <article className="change-card">
    <div className="change-card-head"><div><span className="change-type">{EVENT_LABELS[event.event_type] ?? event.event_type}</span><strong>{event.address ?? event.system_id}</strong><small>System {event.system_id}{event.borough ? ` · ${event.borough}` : ''}</small></div><div className="change-meta"><strong>{relativeTime(event.detected_at)}</strong><small>{formatTimestamp(event.detected_at)}</small>{event.evidence_confidence && <StatusBadge value={event.evidence_confidence} />}</div></div>
    <div className="change-values"><div><span>Previous</span><code>{compactValue(event.previous_value)}</code></div><div><span>New</span><code>{compactValue(event.new_value)}</code></div></div>
    <div className="change-source"><span>Source: {event.source}</span><span>Evidence: {event.evidence_basis}</span>{event.source_observation_date && <span>Source observation: {formatDate(event.source_observation_date)}</span>}{event.priority_score != null && <span>Priority {event.priority_score}</span>}{event.contact_available && <span>HPD contact data available</span>}</div>
    <button onClick={() => onSelectSystem(event.system_id)}>Open account detail</button>
  </article>
}
