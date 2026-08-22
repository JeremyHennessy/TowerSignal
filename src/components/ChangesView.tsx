import { useMemo, useState } from 'react'
import type { ChangeEventType, ChangesPayload } from '../types/history'
import { formatTimestamp } from '../domain/labels'

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
  const [borough] = useState('')
  const [eventType, setEventType] = useState('')
  const [minimumPriority] = useState('')
  const [confidence] = useState('')
  const [contactOnly] = useState(false)
  const [quickTypes, setQuickTypes] = useState<ChangeEventType[] | null>(null)
  const [customStart] = useState('')
  const [customEnd] = useState('')

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
    <div className="change-count">{filtered.length.toLocaleString()} change{filtered.length === 1 ? '' : 's'} in current view</div>
    <div className="empty-changes" data-diagnostic-form-cards-omitted><strong>Diagnostic: quick buttons restored; form controls and cards omitted.</strong><span>{boroughs.length} borough values and {eventTypes.length} event types derived; filter computation remains active.</span></div>
  </section>
}
