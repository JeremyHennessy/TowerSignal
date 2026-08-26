import { useMemo, useState } from 'react'
import type { ChangeEvent, ChangeEventType, ChangesPayload } from '../types/history'
import { formatDate, formatTimestamp } from '../domain/labels'
import { StatusBadge } from './StatusBadge'

const EVENT_LABELS: Record<string, string> = {
  SYSTEM_FIRST_SEEN: 'New system observed',
  SYSTEM_NO_LONGER_PRESENT: 'No longer present',
  ACTIVE_EQUIPMENT_CHANGED: 'Active equipment changed',
  SAMPLE_REPORTED: 'New public sample reported',
  LATEST_SAMPLE_CHANGED: 'Latest public sample changed',
  SAMPLING_GAP_ENTERED: 'Sampling-gap signal entered',
  SAMPLING_GAP_RESOLVED: 'Sampling-gap signal resolved',
  INSPECTION_ADDED: 'New NYC Health inspection',
  VIOLATION_ADDED: 'New confirmed violation',
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
  HPD_MANAGING_AGENT_CHANGED: 'Managing-agent record changed',
  DOB_JOB_FILED: 'DOB job filed',
  DOB_STATUS_CHANGED: 'DOB filing status changed',
  DOB_PERMIT_ISSUED: 'DOB permit issued',
  DOB_JOB_APPROVED: 'DOB job approved',
  DOB_JOB_SIGNED_OFF: 'DOB job signed off',
  DOB_COOLING_TOWER_MENTION_ADDED: 'Cooling tower mentioned in DOB filing',
}

const QUICK_GROUPS: Array<{ label: string; types: ChangeEventType[] | null }> = [
  { label: 'All changes', types: null },
  { label: 'High priority', types: null },
  { label: 'New violations', types: ['VIOLATION_ADDED'] },
  { label: 'OATH activity', types: ['OATH_CASE_ADDED', 'OATH_STATUS_CHANGED', 'OATH_DECISION_CHANGED', 'OATH_PENALTY_CHANGED', 'OATH_BALANCE_CHANGED'] },
  { label: 'DOB / permits', types: ['DOB_JOB_FILED', 'DOB_STATUS_CHANGED', 'DOB_PERMIT_ISSUED', 'DOB_JOB_APPROVED', 'DOB_JOB_SIGNED_OFF', 'DOB_COOLING_TOWER_MENTION_ADDED'] },
  { label: 'Sampling', types: ['SAMPLE_REPORTED', 'LATEST_SAMPLE_CHANGED', 'SAMPLING_GAP_ENTERED', 'SAMPLING_GAP_RESOLVED'] },
  { label: 'Property / contact', types: ['PLUTO_OWNER_CHANGED', 'HPD_REGISTRATION_CHANGED', 'HPD_CONTACT_ADDED', 'HPD_CONTACT_REMOVED', 'HPD_MANAGING_AGENT_CHANGED'] },
]

function compactValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

function eventTone(event: ChangeEvent): string {
  if (event.event_type.includes('VIOLATION') || event.event_type.includes('OATH')) return 'urgent'
  if (event.event_type.includes('SAMPLE') || event.event_type.includes('SAMPLING')) return 'warning'
  if (event.event_type.startsWith('DOB_')) return 'blue'
  if (event.event_type.startsWith('HPD_') || event.event_type === 'PLUTO_OWNER_CHANGED') return 'success'
  return 'neutral'
}

export function ChangesView({ payload, onSelectSystem }: { payload: ChangesPayload; onSelectSystem: (systemId: string) => void }) {
  const [days, setDays] = useState('7')
  const [borough, setBorough] = useState('')
  const [eventType, setEventType] = useState('')
  const [minimumPriority, setMinimumPriority] = useState('')
  const [confidence, setConfidence] = useState('')
  const [contactOnly, setContactOnly] = useState(false)
  const [quickLabel, setQuickLabel] = useState('All changes')
  const [quickTypes, setQuickTypes] = useState<ChangeEventType[] | null>(null)
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')
  const [page, setPage] = useState(0)

  const filtered = useMemo(() => payload.events.filter(event => {
    const detected = new Date(event.detected_at).getTime()
    const now = Date.now()
    if (days === 'custom') {
      if (customStart && detected < new Date(`${customStart}T00:00:00`).getTime()) return false
      if (customEnd && detected > new Date(`${customEnd}T23:59:59`).getTime()) return false
    } else if (Number(days) > 0 && detected < now - Number(days) * 86400000) return false
    if (borough && event.borough !== borough) return false
    if (eventType && event.event_type !== eventType) return false
    if (quickLabel === 'High priority' && (event.priority_score ?? 0) < 70) return false
    if (quickTypes && !quickTypes.includes(event.event_type)) return false
    if (minimumPriority && (event.priority_score ?? 0) < Number(minimumPriority)) return false
    if (confidence && event.evidence_confidence !== confidence) return false
    if (contactOnly && !event.contact_available) return false
    return true
  }), [payload.events, days, borough, eventType, quickLabel, quickTypes, minimumPriority, confidence, contactOnly, customStart, customEnd])

  const boroughs = [...new Set(payload.events.map(event => event.borough).filter(Boolean))] as string[]
  const eventTypes = [...new Set(payload.events.map(event => event.event_type))]
  const pageSize = 50
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const pageRows = filtered.slice(safePage * pageSize, safePage * pageSize + pageSize)

  const chooseQuick = (label: string, types: ChangeEventType[] | null) => {
    setQuickLabel(label)
    setQuickTypes(types)
    if (label === 'High priority') setMinimumPriority('70')
    else if (minimumPriority === '70') setMinimumPriority('')
    setEventType('')
    setPage(0)
  }

  return <section className="changes-view changes-table-view" aria-label="TowerSignal changes">
    {payload.baseline_initialized && <div className="disclaimer"><strong>Historical baseline initialized.</strong> Existing systems are not being mislabeled as newly registered. Later source snapshots are compared with this preserved baseline.</div>}

    <div className="change-workspace-grid">
      <aside className="change-filter-rail" aria-label="Monitor filters">
        <div className="change-filter-heading"><span className="page-kicker">Filters</span><button onClick={() => { setDays('7'); setBorough(''); setEventType(''); setMinimumPriority(''); setConfidence(''); setContactOnly(false); setQuickLabel('All changes'); setQuickTypes(null); setPage(0) }}>Clear all</button></div>
        <label>Time range<select value={days} onChange={event => { setDays(event.target.value); setPage(0) }}><option value="1">Past 24 hours</option><option value="7">Past 7 days</option><option value="30">Past 30 days</option><option value="custom">Custom dates</option><option value="0">All retained</option></select></label>
        {days === 'custom' && <><label>From<input type="date" value={customStart} onChange={event => setCustomStart(event.target.value)} /></label><label>To<input type="date" value={customEnd} onChange={event => setCustomEnd(event.target.value)} /></label></>}
        <label>Borough<select value={borough} onChange={event => { setBorough(event.target.value); setPage(0) }}><option value="">All boroughs</option>{boroughs.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Change type<select value={eventType} onChange={event => { setEventType(event.target.value); setQuickLabel('All changes'); setQuickTypes(null); setPage(0) }}><option value="">All change types</option>{eventTypes.map(value => <option key={value} value={value}>{EVENT_LABELS[value] ?? value}</option>)}</select></label>
        <label>Minimum priority<input type="number" min="0" max="100" value={minimumPriority} onChange={event => { setMinimumPriority(event.target.value); setQuickLabel('All changes'); setPage(0) }} placeholder="Any score" /></label>
        <label>Evidence<select value={confidence} onChange={event => { setConfidence(event.target.value); setPage(0) }}><option value="">All evidence</option><option value="CONFIRMED">Confirmed</option><option value="STRONG_SIGNAL">Strong signal</option><option value="VERIFY">Verify</option></select></label>
        <label className="change-check"><input type="checkbox" checked={contactOnly} onChange={event => { setContactOnly(event.target.checked); setPage(0) }} /><span>Contact-ready only</span></label>
      </aside>

      <div className="change-table-workspace">
        <div className="change-table-topline"><div><span className="page-kicker">Historical intelligence</span><h2>What changed?</h2><p>Detection time is when TowerSignal first observed a difference between preserved public-source snapshots.</p></div><div className="history-status compact"><span>History began</span><strong>{formatTimestamp(payload.history_started_at)}</strong><small>Latest observation {formatTimestamp(payload.observed_at)}</small></div></div>

        <div className="change-tabs" role="tablist" aria-label="Change categories">{QUICK_GROUPS.map(group => <button key={group.label} className={quickLabel === group.label ? 'active' : ''} onClick={() => chooseQuick(group.label, group.types)}>{group.label}<span>{group.label === 'All changes' ? payload.events.length : ''}</span></button>)}</div>

        <div className="reference-table-card monitor-change-table-card">
          <div className="reference-table-heading"><div><strong>{filtered.length.toLocaleString()} new events</strong><span>{pageRows.length ? `Showing ${safePage * pageSize + 1}–${safePage * pageSize + pageRows.length}` : 'No matching events'} · preserved source-backed history</span></div></div>
          {pageRows.length === 0 ? <div className="reference-empty-state compact"><strong>No observed changes match these filters.</strong><span>Adjust the period or evidence filters to inspect retained history.</span></div> : <div className="reference-table-scroll"><table className="reference-table change-reference-table"><thead><tr><th>Time</th><th>Account</th><th>Change</th><th>Previous → New</th><th>Priority</th><th>Source</th><th>Evidence</th><th>Action</th></tr></thead><tbody>{pageRows.map((event, index) => <ChangeRow key={`${event.detected_at}-${event.system_id}-${event.event_type}-${index}`} event={event} onSelectSystem={onSelectSystem} />)}</tbody></table></div>}
          {pageCount > 1 && <div className="reference-pagination"><span>Page {safePage + 1} of {pageCount}</span><div><button disabled={safePage === 0} onClick={() => setPage(Math.max(0, safePage - 1))}>Previous</button><button disabled={safePage >= pageCount - 1} onClick={() => setPage(Math.min(pageCount - 1, safePage + 1))}>Next</button></div></div>}
        </div>
      </div>
    </div>
  </section>
}

function ChangeRow({ event, onSelectSystem }: { event: ChangeEvent; onSelectSystem: (systemId: string) => void }) {
  return <tr className="change-reference-row" onClick={() => onSelectSystem(event.system_id)}>
    <td><strong>{formatTimestamp(event.detected_at)}</strong>{event.source_observation_date && <small>source {formatDate(event.source_observation_date)}</small>}</td>
    <td><strong>{event.address ?? event.system_id}</strong><small>{event.borough ? `${event.borough} · ` : ''}{event.system_id}</small></td>
    <td><span className={`change-kind change-kind-${eventTone(event)}`}>{EVENT_LABELS[event.event_type] ?? event.event_type}</span></td>
    <td><div className="change-inline-values"><span>{compactValue(event.previous_value)}</span><b>→</b><strong>{compactValue(event.new_value)}</strong></div></td>
    <td>{event.priority_score == null ? '—' : <strong className={event.priority_score >= 70 ? 'priority-text-high' : ''}>{event.priority_score}</strong>}</td>
    <td><strong>Source: {event.source}</strong>{event.contact_available && <small>contact-ready</small>}</td>
    <td>{event.evidence_confidence ? <StatusBadge value={event.evidence_confidence} /> : <span className="muted-label">—</span>}<small>Evidence: {event.evidence_basis}</small></td>
    <td><button className="table-link" onClick={click => { click.stopPropagation(); onSelectSystem(event.system_id) }}>Open →</button></td>
  </tr>
}
