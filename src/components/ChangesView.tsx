import { useMemo, useState } from 'react'
import type { ChangeEventType, ChangesPayload } from '../types/history'
import { formatTimestamp } from '../domain/labels'

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

export function ChangesView({ payload }: { payload: ChangesPayload; onSelectSystem: (systemId: string) => void }) {
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
    <div className="empty-changes" data-diagnostic-cards-omitted><strong>Diagnostic: change cards omitted.</strong><span>The real intro, filters, derived filter computation, and count are rendered.</span></div>
  </section>
}
