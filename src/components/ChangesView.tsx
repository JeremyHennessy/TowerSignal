import { useMemo, useState } from 'react'
import type { ChangeEvent, ChangeEventType, ChangesPayload } from '../types/history'
import { formatDate, formatTimestamp } from '../domain/labels'
import { compareEventDates, eventDate, evidenceLabel, inSourceRange, readableValue, recordValue, sourceLabel } from '../domain/changePresentation'
import { StatusBadge } from './StatusBadge'
import '../styles/monitor-event-table.css'

const EVENT_LABELS: Record<string, string> = {
  SYSTEM_FIRST_SEEN: 'New system observed',
  SYSTEM_NO_LONGER_PRESENT: 'No longer present',
  ACTIVE_EQUIPMENT_CHANGED: 'Active equipment changed',
  SAMPLE_REPORTED: 'Public sample reported',
  LATEST_SAMPLE_CHANGED: 'Latest public sample changed',
  SAMPLING_GAP_ENTERED: 'Sampling-gap signal entered',
  SAMPLING_GAP_RESOLVED: 'Sampling-gap signal resolved',
  INSPECTION_ADDED: 'NYC Health inspection',
  VIOLATION_ADDED: 'Recorded violation',
  VIOLATION_STATUS_CHANGED: 'Violation status changed',
  OATH_CASE_ADDED: 'OATH case activity',
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
  { label: 'Violations', types: ['VIOLATION_ADDED'] },
  { label: 'OATH activity', types: ['OATH_CASE_ADDED', 'OATH_STATUS_CHANGED', 'OATH_DECISION_CHANGED', 'OATH_PENALTY_CHANGED', 'OATH_BALANCE_CHANGED'] },
  { label: 'DOB / permits', types: ['DOB_JOB_FILED', 'DOB_STATUS_CHANGED', 'DOB_PERMIT_ISSUED', 'DOB_JOB_APPROVED', 'DOB_JOB_SIGNED_OFF', 'DOB_COOLING_TOWER_MENTION_ADDED'] },
  { label: 'Sampling', types: ['SAMPLE_REPORTED', 'LATEST_SAMPLE_CHANGED', 'SAMPLING_GAP_ENTERED', 'SAMPLING_GAP_RESOLVED'] },
  { label: 'Property / contact', types: ['PLUTO_OWNER_CHANGED', 'HPD_REGISTRATION_CHANGED', 'HPD_CONTACT_ADDED', 'HPD_CONTACT_REMOVED', 'HPD_MANAGING_AGENT_CHANGED'] },
]

type SortKey = 'event_date' | 'address' | 'event_type' | 'priority_score' | 'source'
type SortDirection = 'asc' | 'desc'

function eventTone(event: ChangeEvent): string {
  if (event.event_type.includes('VIOLATION') || event.event_type.includes('OATH')) return 'urgent'
  if (event.event_type.includes('SAMPLE') || event.event_type.includes('SAMPLING')) return 'warning'
  if (event.event_type.startsWith('DOB_')) return 'blue'
  if (event.event_type.startsWith('HPD_') || event.event_type === 'PLUTO_OWNER_CHANGED') return 'success'
  return 'neutral'
}

export function ChangesView({ payload, onSelectSystem }: { payload: ChangesPayload; onSelectSystem: (systemId: string) => void }) {
  const [days, setDays] = useState('0')
  const [borough, setBorough] = useState('')
  const [eventType, setEventType] = useState('')
  const [minimumPriority, setMinimumPriority] = useState('')
  const [confidence, setConfidence] = useState('')
  const [contactOnly, setContactOnly] = useState(false)
  const [quickLabel, setQuickLabel] = useState('All changes')
  const [quickTypes, setQuickTypes] = useState<ChangeEventType[] | null>(null)
  const [customStart, setCustomStart] = useState('')
  const [customEnd, setCustomEnd] = useState('')
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({ key: 'event_date', direction: 'desc' })
  const [page, setPage] = useState(0)
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
  const invalidRange = days === 'custom' && Boolean(customStart && customEnd && customStart > customEnd)

  const baseFiltered = useMemo(() => payload.events.filter(event => {
    if (invalidRange || !inSourceRange(event, days, customStart, customEnd, today)) return false
    if (borough && event.borough !== borough) return false
    if (eventType && event.event_type !== eventType) return false
    if (minimumPriority && (event.priority_score ?? 0) < Number(minimumPriority)) return false
    if (confidence && event.evidence_confidence !== confidence) return false
    return !contactOnly || event.contact_available
  }), [payload.events, days, borough, eventType, minimumPriority, confidence, contactOnly, customStart, customEnd, today, invalidRange])

  const filtered = useMemo(() => baseFiltered.filter(event => {
    if (quickLabel === 'High priority' && (event.priority_score ?? 0) < 70) return false
    return !quickTypes || quickTypes.includes(event.event_type)
  }), [baseFiltered, quickLabel, quickTypes])
  const sorted = useMemo(() => [...filtered].sort((a, b) => {
    if (sort.key === 'event_date') return compareEventDates(a, b, sort.direction) || a.system_id.localeCompare(b.system_id)
    const left = a[sort.key], right = b[sort.key]
    const result = typeof left === 'number' && typeof right === 'number' ? left - right : String(left ?? '').localeCompare(String(right ?? ''))
    return result * (sort.direction === 'asc' ? 1 : -1) || compareEventDates(a, b, 'desc')
  }), [filtered, sort])
  const counts = useMemo(() => QUICK_GROUPS.map(group => baseFiltered.filter(event => group.label === 'High priority' ? (event.priority_score ?? 0) >= 70 : !group.types || group.types.includes(event.event_type)).length), [baseFiltered])
  const boroughs = [...new Set(payload.events.map(event => event.borough).filter(Boolean))] as string[]
  const eventTypes = [...new Set(payload.events.map(event => event.event_type))]
  const pageSize = 50
  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize))
  const safePage = Math.min(page, pageCount - 1)
  const pageRows = sorted.slice(safePage * pageSize, safePage * pageSize + pageSize)
  const undatedCount = filtered.filter(event => !eventDate(event).value).length

  const chooseQuick = (label: string, types: ChangeEventType[] | null) => {
    setQuickLabel(label); setQuickTypes(types); setEventType(''); setPage(0)
  }
  const changeSort = (key: SortKey) => {
    setSort(current => current.key === key
      ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
      : { key, direction: key === 'event_date' || key === 'priority_score' ? 'desc' : 'asc' })
    setPage(0)
  }
  const sortIndicator = (key: SortKey) => sort.key === key ? (sort.direction === 'asc' ? ' ↑' : ' ↓') : ''
  const ariaSort = (key: SortKey) => sort.key === key ? sort.direction === 'asc' ? 'ascending' as const : 'descending' as const : 'none' as const

  return <section className="changes-view changes-table-view" aria-label="TowerSignal changes">
    {payload.baseline_initialized && <div className="disclaimer"><strong>Historical baseline initialized.</strong> Existing systems are not being mislabeled as newly registered. Later source snapshots are compared with this preserved baseline.</div>}
    <div className="change-workspace-grid">
      <aside className="change-filter-rail" aria-label="Monitor filters">
        <div className="change-filter-heading"><span className="page-kicker">Filters</span><button onClick={() => { setDays('0'); setCustomStart(''); setCustomEnd(''); setBorough(''); setEventType(''); setMinimumPriority(''); setConfidence(''); setContactOnly(false); setQuickLabel('All changes'); setQuickTypes(null); setPage(0) }}>Clear all</button></div>
        <label>Event date range<select value={days} onChange={event => { setDays(event.target.value); setPage(0) }}><option value="1">Today</option><option value="7">Past 7 days</option><option value="30">Past 30 days</option><option value="custom">Custom dates</option><option value="0">All retained dates</option></select></label>
        {days === 'custom' && <><label>From<input type="date" value={customStart} onChange={event => { setCustomStart(event.target.value); setPage(0) }} /></label><label>To<input type="date" value={customEnd} onChange={event => { setCustomEnd(event.target.value); setPage(0) }} /></label></>}
        {invalidRange && <p className="monitor-date-warning" role="alert">The start date must be on or before the end date.</p>}
        <p className="monitor-filter-note">Filters use published occurrence dates. Collection timestamps and undated changes are excluded from date ranges.</p>
        <label>Borough<select value={borough} onChange={event => { setBorough(event.target.value); setPage(0) }}><option value="">All boroughs</option>{boroughs.map(value => <option key={value}>{value}</option>)}</select></label>
        <label>Change type<select value={eventType} onChange={event => { setEventType(event.target.value); setQuickLabel('All changes'); setQuickTypes(null); setPage(0) }}><option value="">All change types</option>{eventTypes.map(value => <option key={value} value={value}>{EVENT_LABELS[value] ?? value}</option>)}</select></label>
        <label>Minimum priority<input type="number" min="0" max="100" value={minimumPriority} onChange={event => { setMinimumPriority(event.target.value); setPage(0) }} placeholder="Any score" /></label>
        <label>Evidence<select value={confidence} onChange={event => { setConfidence(event.target.value); setPage(0) }}><option value="">All evidence</option><option value="CONFIRMED">Confirmed</option><option value="STRONG_SIGNAL">Strong signal</option><option value="VERIFY">Verify</option></select></label>
        <label className="change-check"><input type="checkbox" checked={contactOnly} onChange={event => { setContactOnly(event.target.checked); setPage(0) }} /><span>Contact-ready only</span></label>
      </aside>
      <div className="change-table-workspace">
        <div className="change-table-topline"><div><span className="page-kicker">Source-dated history</span><h2>Recorded events</h2><p>Violations use their published violation date or inspection date. Other source dates are labeled by type. Undated changes stay undated. Priority is the score recorded when the change was observed.</p></div><details className="monitor-history-provenance"><summary>Collection history</summary><p>History began {formatTimestamp(payload.history_started_at)}.</p><p>Latest collection {formatTimestamp(payload.observed_at)}. These are not event dates.</p></details></div>
        <div className="change-tabs" role="tablist" aria-label="Change categories">{QUICK_GROUPS.map((group, index) => <button key={group.label} role="tab" aria-selected={quickLabel === group.label} className={quickLabel === group.label ? 'active' : ''} onClick={() => chooseQuick(group.label, group.types)}>{group.label}<span>{counts[index].toLocaleString()}</span></button>)}</div>
        <div className="reference-table-card monitor-change-table-card">
          <div className="reference-table-heading"><div><strong data-testid="monitor-event-count">{sorted.length.toLocaleString()} recorded events</strong><span>{pageRows.length ? `Showing ${safePage * pageSize + 1}–${safePage * pageSize + pageRows.length}` : 'No matching events'} · sorted by {sort.key === 'event_date' ? 'source date' : sort.key.replaceAll('_', ' ')}{undatedCount > 0 ? ` · ${undatedCount.toLocaleString()} undated` : ''}</span></div></div>
          {pageRows.length === 0 ? <div className="reference-empty-state compact"><strong>No recorded events match these filters.</strong><span>Try All retained dates to include older source records and undated changes.</span></div> : <div className="reference-table-scroll monitor-event-scroll"><table className="reference-table change-reference-table"><thead><tr>
            <th scope="col" aria-sort={ariaSort('event_date')}><button onClick={() => changeSort('event_date')}>Event date{sortIndicator('event_date')}</button></th>
            <th scope="col" aria-sort={ariaSort('address')}><button onClick={() => changeSort('address')}>Account{sortIndicator('address')}</button></th>
            <th scope="col" aria-sort={ariaSort('event_type')}><button onClick={() => changeSort('event_type')}>Event & details{sortIndicator('event_type')}</button></th>
            <th scope="col" aria-sort={ariaSort('priority_score')} title="Priority recorded when the change was observed; not retroactively re-scored"><button onClick={() => changeSort('priority_score')}>Priority{sortIndicator('priority_score')}</button></th>
            <th scope="col" aria-sort={ariaSort('source')}><button onClick={() => changeSort('source')}>Source & evidence{sortIndicator('source')}</button></th>
            <th scope="col">Account link</th>
          </tr></thead><tbody>{pageRows.map((event, index) => <ChangeRow key={`${event.detected_at}-${event.system_id}-${event.event_type}-${index}`} event={event} today={today} onSelectSystem={onSelectSystem} />)}</tbody></table></div>}
          {pageCount > 1 && <div className="reference-pagination"><span>Page {safePage + 1} of {pageCount}</span><div><button disabled={safePage === 0} onClick={() => setPage(Math.max(0, safePage - 1))}>Previous</button><button disabled={safePage >= pageCount - 1} onClick={() => setPage(Math.min(pageCount - 1, safePage + 1))}>Next</button></div></div>}
        </div>
      </div>
    </div>
  </section>
}

function ChangeRow({ event, today, onSelectSystem }: { event: ChangeEvent; today: string; onSelectSystem: (systemId: string) => void }) {
  const date = eventDate(event)
  const record = recordValue(event.new_value)
  const violation = event.event_type === 'VIOLATION_ADDED'
  return <tr className="change-reference-row" onClick={() => onSelectSystem(event.system_id)}>
    <td data-label="Event date" className="monitor-source-date"><time dateTime={date.value ?? undefined}>{date.value ? formatDate(date.value) : 'Not published'}</time><small title={date.note}>{date.label}</small>{date.value && date.value > today && <small className="monitor-future-date">Future source date</small>}</td>
    <td data-label="Account"><strong>{event.address ?? event.system_id}</strong><small>{event.borough ?? 'Borough not published'}</small><small className="mono">{event.system_id}</small>{event.contact_available && <small className="monitor-contact-ready">Contact available</small>}</td>
    <td data-label="Event & details"><span className={`change-kind change-kind-${eventTone(event)}`}>{EVENT_LABELS[event.event_type] ?? event.event_type}</span>
      {violation ? <div className="monitor-event-detail"><strong>{readableValue(record.description ?? record.violation_text ?? record.citation_text ?? 'Violation description not published')}</strong><span>{[record.violation_code ? `Code ${record.violation_code}` : null, record.law_section, record.violation_type].filter(Boolean).join(' · ')}</span><span>{record.summons_number ? `Summons ${record.summons_number}` : 'No summons number published'}</span></div>
        : <div className="monitor-event-detail">{event.previous_value != null && <span className="monitor-old-value">Previously: {readableValue(event.previous_value)}</span>}<strong>{event.new_value == null ? 'Record no longer present in source snapshot' : readableValue(event.new_value)}</strong></div>}
    </td>
    <td data-label="Priority">{event.priority_score == null ? '—' : <strong className={event.priority_score >= 70 ? 'priority-text-high' : ''}>{event.priority_score}</strong>}</td>
    <td data-label="Source & evidence"><strong className="monitor-source-name" title={event.source}>{sourceLabel(event.source)}</strong>{event.evidence_confidence && <StatusBadge value={event.evidence_confidence} />}<small>{evidenceLabel(event.evidence_basis)}</small><details className="monitor-row-provenance" onClick={click => click.stopPropagation()}><summary>Provenance</summary><p>First seen by TowerSignal: {formatTimestamp(event.detected_at)}. This is a collection timestamp, not the event date.</p>{date.note && <p>{date.note}</p>}<p>{event.source}</p></details></td>
    <td data-label="Account link"><a className="monitor-open-link" href={`#/account/${event.system_id}`} onClick={click => click.stopPropagation()}>Open account <span aria-hidden="true">→</span></a></td>
  </tr>
}
