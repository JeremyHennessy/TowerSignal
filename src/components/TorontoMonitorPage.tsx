import { useEffect, useMemo, useState } from 'react'
import type { TorontoHistoryEvent, TorontoHistoryPayload } from '../types/torontoHistory'

const base = import.meta.env.BASE_URL

function humanize(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, character => character.toUpperCase())
}

function sourceLabel(value: string): string {
  const labels: Record<string, string> = {
    toronto_address_points: 'Toronto Address Points',
    toronto_building_permits_active_targeted: 'Active building permits',
    toronto_building_permits_cleared_targeted_since_2017: 'Cleared building permits',
    tdsb_facility_condition_renewal: 'TDSB facility-condition renewals',
    toronto_aic_applications: 'Toronto AIC applications',
    chemtrac_history: 'ChemTRAC history',
    chemtrac_2024: 'ChemTRAC 2024',
    tobids_awarded_contracts: 'TOBids awards',
    tobids_awarded_contracts_exact_document_address_prior_poc: 'TOBids exact-address awards',
  }
  return labels[value] ?? humanize(value)
}

function eventSummary(event: TorontoHistoryEvent): string {
  if (event.record_title) return event.record_title
  if (event.event_type === 'TOWER_EVIDENCE_CHANGED') return `${String(event.previous_value ?? 'None')} → ${String(event.new_value ?? 'None')}`
  if (event.event_type === 'RELATIONSHIP_ADDED' || event.event_type === 'RELATIONSHIP_REMOVED') {
    const value = (event.new_value ?? event.previous_value) as { organization?: string; relationship?: string } | null
    return value?.organization ? `${value.organization} · ${humanize(value.relationship ?? '')}` : humanize(event.event_type)
  }
  if (event.event_type === 'PROPERTY_FIRST_SEEN') return 'Canonical property first present in this verified release'
  if (event.event_type === 'PROPERTY_NO_LONGER_PRESENT') return 'Canonical property no longer present in this verified release'
  return humanize(event.event_type)
}

function eventDate(event: TorontoHistoryEvent): string {
  return event.source_observation_date || event.detected_at
}

function openProperty(event: TorontoHistoryEvent): void {
  window.location.hash = `#/toronto/${encodeURIComponent(event.property_id)}`
}

export function TorontoMonitorPage() {
  const [payload, setPayload] = useState<TorontoHistoryPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [type, setType] = useState('')
  const [source, setSource] = useState('')

  useEffect(() => {
    fetch(`${base}data/toronto-changes.json`, { cache: 'no-store' })
      .then(async response => {
        if (!response.ok) throw new Error(`Toronto Monitor request failed: HTTP ${response.status}`)
        const data = await response.json() as TorontoHistoryPayload
        if (data.schema_version !== 'toronto-history-1.0' || !Array.isArray(data.events)) throw new Error('Toronto Monitor dataset is malformed')
        setPayload(data)
      })
      .catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load Toronto Monitor'))
  }, [])

  const types = useMemo(() => payload ? Object.keys(payload.event_type_counts).sort() : [], [payload])
  const sources = useMemo(() => payload ? Object.keys(payload.source_counts).sort() : [], [payload])
  const filtered = useMemo(() => {
    if (!payload) return []
    const term = search.trim().toLowerCase()
    return payload.events.filter(event => {
      if (type && event.event_type !== type) return false
      if (source && event.source_key !== source) return false
      if (!term) return true
      return [
        event.address,
        event.property_id,
        event.event_type,
        event.source_key,
        event.source_record_id,
        event.record_title,
        event.record_status,
        eventSummary(event),
      ].filter(Boolean).join(' ').toLowerCase().includes(term)
    })
  }, [payload, search, type, source])

  if (error) return <section className="product-page toronto-page toronto-parity-page"><div className="reference-empty-state"><strong>Toronto Monitor is unavailable.</strong><span>{error}</span></div></section>
  if (!payload) return <section className="product-page toronto-page toronto-parity-page"><div className="portal-loading">Loading verified Toronto release changes…</div></section>

  const permitEvents = payload.events.filter(event => event.event_type.startsWith('PERMIT_') || event.event_type.startsWith('TDSB_')).length
  const relationshipEvents = payload.events.filter(event => event.event_type.startsWith('RELATIONSHIP_')).length
  const evidenceEvents = payload.events.filter(event => event.event_type === 'TOWER_EVIDENCE_CHANGED').length

  return <section className="product-page toronto-page toronto-parity-page toronto-monitor-page">
    <div className="product-page-heading"><div><span className="page-kicker">Toronto · verified release changes</span><h1>Monitor</h1><p>Release-to-release changes from exact Toronto property identity, stable source-record identity and source-preserved organization roles. These events report observed dataset changes; they are not NYC compliance events.</p></div></div>
    <div className="reference-metric-grid toronto-parity-metrics">
      <article><span className="reference-metric-icon urgent">◷</span><div><small>Observed changes</small><strong>{payload.event_count.toLocaleString()}</strong><span>Across two verified releases</span></div></article>
      <article><span className="reference-metric-icon">⌂</span><div><small>Properties changed</small><strong>{payload.properties_with_changes.toLocaleString()}</strong><span>Exact canonical property ID</span></div></article>
      <article><span className="reference-metric-icon warning">⌁</span><div><small>Permit / renewal events</small><strong>{permitEvents.toLocaleString()}</strong><span>Source record added or removed</span></div></article>
      <article><span className="reference-metric-icon">↔</span><div><small>Relationship changes</small><strong>{relationshipEvents.toLocaleString()}</strong><span>Source role preserved</span></div></article>
      <article><span className="reference-metric-icon success">◎</span><div><small>Tower-evidence changes</small><strong>{evidenceEvents.toLocaleString()}</strong><span>TowerSignal evidence contract only</span></div></article>
    </div>
    <div className="toronto-limit-banner"><strong>Change semantics are bounded.</strong><span>{payload.contract.semantics}</span></div>
    <div className="toronto-parity-toolbar toronto-monitor-toolbar">
      <input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search address, source record or organization" />
      <select value={type} onChange={event => setType(event.target.value)}><option value="">All event types</option>{types.map(value => <option key={value} value={value}>{humanize(value)}</option>)}</select>
      <select value={source} onChange={event => setSource(event.target.value)}><option value="">All sources</option>{sources.map(value => <option key={value} value={value}>{sourceLabel(value)}</option>)}</select>
      <strong>{filtered.length.toLocaleString()} events</strong>
    </div>
    <div className="toronto-monitor-list">
      {filtered.slice(0, 600).map(event => <article key={event.event_id} className="toronto-monitor-event">
        <div className="toronto-monitor-event-main"><div><span className="toronto-attention-badge tier-context">{humanize(event.event_type)}</span><button className="toronto-address-button" onClick={() => openProperty(event)}>{event.address || event.property_id}</button><small>{eventDate(event)}{event.source_key ? ` · ${sourceLabel(event.source_key)}` : ''}</small></div><p>{eventSummary(event)}</p></div>
        <div className="toronto-monitor-event-meta">{event.record_status && <span>{event.record_status}</span>}<small>{event.evidence_basis.replaceAll('_', ' ').toLowerCase()}</small><button onClick={() => openProperty(event)}>Open evidence</button></div>
      </article>)}
    </div>
    {filtered.length > 600 && <p className="toronto-table-limit">Showing the first 600 matching change events. Refine the filters to narrow the timeline.</p>}
    <details className="toronto-limitations"><summary>Monitor lineage</summary><ul><li>Baseline source: {payload.previous_release_sha}</li><li>Current source: {payload.current_release_sha}</li><li>History started: {payload.history_started_at}</li><li>{payload.contract.identity}</li><li>{payload.contract.baseline}</li></ul></details>
  </section>
}
