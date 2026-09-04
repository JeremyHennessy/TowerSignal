import { useCallback, useEffect, useMemo, useState } from 'react'
import { loadTorontoMarket } from '../data/api'
import type { TorontoMarketPayload, TorontoProperty, TorontoSourceCatalogItem, TorontoSourceLink, TorontoTowerEvidenceStatus } from '../types/toronto'
import { TorontoMarketMap } from './TorontoMarketMap'
import { TorontoParityShell } from './TorontoParityShell'

const evidenceLabels: Record<TorontoTowerEvidenceStatus, string> = {
  CONFIRMED_DOCUMENTARY_TOWER: 'Confirmed documentary tower',
  STRONG_DOCUMENTARY_CANDIDATE: 'Strong documentary candidate',
  AIC_DOCUMENT_CANDIDATE: 'AIC document candidate',
  AERIAL_REVIEW_CANDIDATE: 'Aerial review candidate',
  NO_TOWER_ASSERTION: 'No tower assertion',
}

const sourceLabels: Record<string, string> = {
  chemtrac_history: 'ChemTRAC history',
  chemtrac_2024: 'ChemTRAC 2024',
  toronto_aic_applications: 'Toronto AIC applications',
  toronto_highrise_residential_health_hazards: 'Highrise residential health hazards',
  toronto_building_permits_active_targeted: 'Toronto active building permits',
  toronto_building_permits_cleared_targeted_since_2017: 'Toronto cleared building permits',
  ontario_environmental_compliance_reports: 'Ontario environmental compliance',
  ontario_bps_energy_2024: 'Ontario BPS energy 2024',
  tobids_awarded_contracts: 'TOBids awarded contracts',
  rentsafe_registration: 'RentSafe registration',
  apartment_building_evaluation: 'Apartment building evaluations',
  development_pipeline: 'Development pipeline',
  affordable_housing_pipeline: 'Affordable housing pipeline',
  renewable_energy_installations: 'Renewable energy installations',
  business_licence_matches_prior_poc: 'Business licences — prior POC',
  tobids_awarded_contracts_exact_document_address_prior_poc: 'TOBids awards — exact prior POC address',
  toronto_public_notices_exact_prior_poc: 'Toronto public notices — exact address/application link',
  '311_matches_prior_poc': '311 records — prior POC',
}

function humanize(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, character => character.toUpperCase())
}

function sourceLabel(value: string): string {
  return sourceLabels[value] ?? humanize(value)
}

export function buildTorontoPropertySearchText(property: TorontoProperty): string {
  return [
    property.display_address,
    property.property_id,
    property.address_point_id,
    ...property.source_links.flatMap(link => [
      link.source_record_id,
      link.source_address,
      link.record_title,
      link.record_date,
      link.record_status,
      ...link.record_details.flatMap(detail => [detail.label, detail.value]),
    ]),
    ...property.relationships.flatMap(item => [item.organization, item.relationship, item.source_key, ...(item.evidence ?? []).flatMap(detail => [detail.label, detail.value])]),
  ].filter(Boolean).join(' ').toLowerCase()
}

export function groupTorontoSourceLinks(links: TorontoSourceLink[]): { sourceKey: string; links: TorontoSourceLink[]; yearSummary: string }[] {
  const grouped = new Map<string, TorontoSourceLink[]>()
  for (const link of links) grouped.set(link.source_key, [...(grouped.get(link.source_key) ?? []), link])
  return [...grouped.entries()].sort(([left], [right]) => left.localeCompare(right)).map(([sourceKey, sourceLinks]) => {
    const years = [...new Set(sourceLinks.map(link => link.record_date?.match(/^\d{4}/)?.[0]).filter((year): year is string => Boolean(year)))].sort()
    const yearSummary = years.length === 0 ? 'No published record year' : years.length === 1 ? years[0] : `${years[0]}–${years.at(-1)} · ${years.length} reporting years`
    return { sourceKey, links: sourceLinks, yearSummary }
  })
}

export interface TorontoSourceFilters {
  chemical: string
  reportingYear: string
  aicApplication: string
  aicStatus: string
  healthStatus: string
  environmentalRecord: string
  company: string
  permitSignal: string
  permitStatus: string
  permitLifecycle: string
  permitInterpretation: string
}

function sourceDetailValue(link: TorontoSourceLink, label: string): string {
  return link.record_details.find(detail => detail.label === label)?.value ?? ''
}

const permitSourceKeys = new Set(['toronto_building_permits_active_targeted', 'toronto_building_permits_cleared_targeted_since_2017'])

function permitSignalValues(link: TorontoSourceLink): string[] {
  return sourceDetailValue(link, 'Mechanical signals').split(',').map(value => value.trim()).filter(Boolean)
}

export function propertyMatchesTorontoSourceFilters(property: TorontoProperty, filters: TorontoSourceFilters): boolean {
  const chemtrac = property.source_links.filter(link => link.source_key === 'chemtrac_history' || link.source_key === 'chemtrac_2024')
  const aic = property.source_links.filter(link => link.source_key === 'toronto_aic_applications')
  const health = property.source_links.filter(link => link.source_key === 'toronto_highrise_residential_health_hazards')
  const environmental = property.source_links.filter(link => link.source_key === 'ontario_environmental_compliance_reports')
  const permits = property.source_links.filter(link => permitSourceKeys.has(link.source_key))
  if (filters.chemical && !chemtrac.some(link => sourceDetailValue(link, 'Chemical') === filters.chemical)) return false
  if (filters.reportingYear && !chemtrac.some(link => link.record_date?.startsWith(filters.reportingYear))) return false
  if (filters.aicApplication && !aic.some(link => `${link.record_title ?? ''} ${link.source_record_id}`.toLowerCase().includes(filters.aicApplication.toLowerCase()))) return false
  if (filters.aicStatus && !aic.some(link => link.record_status === filters.aicStatus)) return false
  if (filters.healthStatus && !health.some(link => link.record_status === filters.healthStatus)) return false
  if (filters.environmentalRecord && !environmental.some(link => [link.source_record_id, link.record_title, ...link.record_details.map(detail => detail.value)].join(' ').toLowerCase().includes(filters.environmentalRecord.toLowerCase()))) return false
  if (filters.permitSignal && !permits.some(link => permitSignalValues(link).includes(filters.permitSignal))) return false
  if (filters.permitStatus && !permits.some(link => link.record_status === filters.permitStatus)) return false
  if (filters.permitLifecycle && !permits.some(link => sourceDetailValue(link, 'Cooling tower lifecycle') === filters.permitLifecycle)) return false
  if (filters.permitInterpretation && !permits.some(link => sourceDetailValue(link, 'Cooling tower current interpretation') === filters.permitInterpretation)) return false
  if (filters.company) {
    const term = filters.company.toLowerCase()
    const relationshipMatch = property.relationships.some(item => item.organization.toLowerCase().includes(term))
    const sourceMatch = property.source_links.some(link => [link.record_title, ...link.record_details.filter(detail => ['Facility owner', 'Client', 'Successful supplier'].includes(detail.label)).map(detail => detail.value)].filter(Boolean).join(' ').toLowerCase().includes(term))
    if (!relationshipMatch && !sourceMatch) return false
  }
  return true
}

function currentPropertyId(): string | null {
  const parts = window.location.hash.replace(/^#\/?/, '').split('?')[0].split('/').filter(Boolean)
  return parts[0] === 'toronto' && parts[1] ? decodeURIComponent(parts[1]) : null
}

export function buildTorontoCsv(rows: TorontoProperty[]): string {
  const columns = ['property_id', 'address_point_id', 'display_address', 'municipality', 'poc_scope', 'tower_evidence_status', 'source_keys', 'relationship_roles', 'relationship_count', 'latitude', 'longitude']
  const escape = (value: unknown) => `"${String(value ?? '').replaceAll('"', '""')}"`
  const body = rows.map(row => [row.property_id, row.address_point_id, row.display_address, row.municipality, row.is_original_poc_property ? 'ORIGINAL_POC' : 'EXPANDED_UNIVERSE', row.tower_evidence_status, row.source_keys.join('|'), [...new Set(row.relationships.map(item => item.relationship))].join('|'), row.relationships.length, row.latitude, row.longitude].map(escape).join(','))
  return [columns.join(','), ...body].join('\n')
}

function exportTorontoCsv(rows: TorontoProperty[]) {
  const blob = new Blob([`\uFEFF${buildTorontoCsv(rows)}`], { type: 'text/csv;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = 'towersignal-toronto-properties.csv'
  document.body.append(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(link.href), 0)
}

function PropertyDetail({ property, sourceCatalog, onClose }: { property: TorontoProperty; sourceCatalog: Record<string, TorontoSourceCatalogItem>; onClose: () => void }) {
  const [visibleBySource, setVisibleBySource] = useState<Record<string, number>>({})
  const sourceGroups = useMemo(() => groupTorontoSourceLinks(property.source_links), [property.source_links])
  useEffect(() => setVisibleBySource({}), [property.property_id])
  return <aside className="toronto-detail" aria-label="Toronto property detail">
    <div className="toronto-detail-heading"><div><span className="eyebrow">Toronto property intelligence</span><h2>{property.display_address}</h2><p>{property.property_id}</p></div><button onClick={onClose} aria-label="Close Toronto property detail">×</button></div>
    <div className={`toronto-evidence-badge status-${property.tower_evidence_status.toLowerCase()}`}>{evidenceLabels[property.tower_evidence_status]}</div>
    <dl className="toronto-identity-grid">
      <div><dt>Address Point ID</dt><dd>{property.address_point_id}</dd></div>
      <div><dt>Identity basis</dt><dd>{property.identity_basis || 'Current municipal address point'}</dd></div>
      <div><dt>Identity confidence</dt><dd>{property.identity_confidence || 'Deterministic'}</dd></div>
      <div><dt>Original POC</dt><dd>{property.is_original_poc_property ? 'Yes' : 'No — expanded universe'}</dd></div>
    </dl>
    {property.aerial_review_rank && <section className="toronto-detail-section"><h3>Aerial review signal</h3><p>Review rank {property.aerial_review_rank}; weak-label similarity score {property.aerial_visual_similarity_score?.toFixed(3)}. This is not cooling-tower evidence.</p></section>}
    <section className="toronto-detail-section"><h3>Source-backed property links <span>{property.source_links.length}</span></h3>{property.source_links.length ? <div className="toronto-source-groups">{sourceGroups.map(group => {
      const visibleCount = visibleBySource[group.sourceKey] ?? 10
      const catalog = sourceCatalog[group.sourceKey]
      return <details key={group.sourceKey} className="toronto-source-group" open>
        <summary><strong>{sourceLabel(group.sourceKey)}</strong><span>{group.links.length} {group.links.length === 1 ? 'record' : 'records'} · {group.yearSummary}</span></summary>
        <div className="toronto-source-list">{group.links.slice(0, visibleCount).map((link, index) => <article key={`${link.source_key}:${link.source_record_id}`}>
        <strong>{sourceLabel(link.source_key)}</strong>
        <span>{link.record_title || link.source_record_id}</span>
        {(link.record_date || link.record_status) && <span>{[link.record_date, link.record_status].filter(Boolean).join(' · ')}</span>}
        {link.source_address && <span>Source address: {link.source_address}</span>}
        {link.record_details.length > 0 && <dl className="toronto-source-details">{link.record_details.map(item => <div key={`${item.label}:${item.value}`}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl>}
        <small>{humanize(link.match_basis)}</small>
        <div className="toronto-source-actions">
          {link.record_url && link.record_link_label && <a href={link.record_url} target="_blank" rel="noreferrer">{link.record_link_label} ↗</a>}
          {index === 0 && catalog?.dataset_url && <a href={catalog.dataset_url} target="_blank" rel="noreferrer">{catalog.dataset_link_label} ↗</a>}
        </div>
        {index === 0 && !link.record_url && catalog?.dataset_url && <small>No durable row-level URL is published; the official source page is provided instead.</small>}
      </article>)}</div>
        {group.links.length > 10 && <button className="toronto-history-more" onClick={() => setVisibleBySource(current => ({ ...current, [group.sourceKey]: visibleCount >= group.links.length ? 10 : Math.min(visibleCount + 10, group.links.length) }))}>{visibleCount >= group.links.length ? 'Show first 10' : `Show ${Math.min(10, group.links.length - visibleCount)} more`}</button>}
      </details>
    })}</div> : <p>No joined enrichment record beyond the municipal property spine.</p>}</section>
    <section className="toronto-detail-section"><h3>Organizations and roles <span>{property.relationships.length}</span></h3>{property.relationships.length ? <div className="toronto-source-list">{property.relationships.map((relationship, index) => <article key={`${relationship.relationship}:${relationship.organization}:${index}`}><strong>{relationship.organization}</strong><span>{humanize(relationship.relationship)}</span>{(relationship.evidence ?? []).length > 0 && <dl className="toronto-source-details">{(relationship.evidence ?? []).map(item => <div key={`${item.label}:${item.value}`}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}</dl>}<small>{sourceLabel(relationship.source_key)} · {humanize(relationship.confidence)} · {humanize(relationship.basis)}</small></article>)}</div> : <p>No defensible organization relationship is currently attached.</p>}</section>
  </aside>
}

function TorontoMarketExplorer() {
  const [payload, setPayload] = useState<TorontoMarketPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [evidence, setEvidence] = useState<TorontoTowerEvidenceStatus | ''>('')
  const [source, setSource] = useState('')
  const [relationship, setRelationship] = useState('')
  const [scope, setScope] = useState<'all' | 'poc' | 'expanded'>('all')
  const [sourceFilters, setSourceFilters] = useState<TorontoSourceFilters>({ chemical: '', reportingYear: '', aicApplication: '', aicStatus: '', healthStatus: '', environmentalRecord: '', company: '', permitSignal: '', permitStatus: '', permitLifecycle: '', permitInterpretation: '' })
  const [view, setView] = useState<'table' | 'map'>('table')
  const [selected, setSelected] = useState<TorontoProperty | null>(null)

  useEffect(() => {
    loadTorontoMarket().then(data => {
      setPayload(data)
      const propertyId = currentPropertyId()
      if (propertyId) setSelected(data.properties.find(property => property.property_id === propertyId) ?? null)
    }).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load Toronto market data'))
  }, [])

  const openProperty = useCallback((property: TorontoProperty) => {
    setSelected(property)
    window.location.hash = `#/toronto/${encodeURIComponent(property.property_id)}`
  }, [])
  const closeProperty = useCallback(() => {
    setSelected(null)
    window.location.hash = '#/toronto'
  }, [])

  const sources = useMemo(() => payload ? [...new Set(payload.properties.flatMap(property => property.source_keys))].sort() : [], [payload])
  const relationships = useMemo(() => payload ? [...new Set(payload.properties.flatMap(property => property.relationships.map(item => item.relationship)))].sort() : [], [payload])
  const sourceFilterOptions = useMemo(() => {
    if (!payload) return { chemicals: [], reportingYears: [], aicStatuses: [], healthStatuses: [], permitSignals: [], permitStatuses: [], permitLifecycles: [], permitInterpretations: [] }
    const links = payload.properties.flatMap(property => property.source_links)
    const chemtrac = links.filter(link => link.source_key === 'chemtrac_history' || link.source_key === 'chemtrac_2024')
    const permits = links.filter(link => permitSourceKeys.has(link.source_key))
    return {
      chemicals: [...new Set(chemtrac.map(link => sourceDetailValue(link, 'Chemical')).filter(Boolean))].sort(),
      reportingYears: [...new Set(chemtrac.map(link => link.record_date?.match(/^\d{4}/)?.[0]).filter((year): year is string => Boolean(year)))].sort().reverse(),
      aicStatuses: [...new Set(links.filter(link => link.source_key === 'toronto_aic_applications').map(link => link.record_status).filter((status): status is string => Boolean(status)))].sort(),
      healthStatuses: [...new Set(links.filter(link => link.source_key === 'toronto_highrise_residential_health_hazards').map(link => link.record_status).filter((status): status is string => Boolean(status)))].sort(),
      permitSignals: [...new Set(permits.flatMap(permitSignalValues))].sort(),
      permitStatuses: [...new Set(permits.map(link => link.record_status).filter((status): status is string => Boolean(status)))].sort(),
      permitLifecycles: [...new Set(permits.map(link => sourceDetailValue(link, 'Cooling tower lifecycle')).filter(Boolean))].sort(),
      permitInterpretations: [...new Set(permits.map(link => sourceDetailValue(link, 'Cooling tower current interpretation')).filter(Boolean))].sort(),
    }
  }, [payload])
  const searchIndex = useMemo(() => payload ? new Map(payload.properties.map(property => [property.property_id, buildTorontoPropertySearchText(property)])) : new Map<string, string>(), [payload])
  const filtered = useMemo(() => {
    if (!payload) return []
    const term = search.trim().toLowerCase()
    return payload.properties.filter(property => {
      if (term && !searchIndex.get(property.property_id)?.includes(term)) return false
      if (evidence && property.tower_evidence_status !== evidence) return false
      if (source && !property.source_keys.includes(source)) return false
      if (relationship && !property.relationships.some(item => item.relationship === relationship)) return false
      if (scope === 'poc' && !property.is_original_poc_property) return false
      if (scope === 'expanded' && property.is_original_poc_property) return false
      if (!propertyMatchesTorontoSourceFilters(property, sourceFilters)) return false
      return true
    })
  }, [payload, search, evidence, source, relationship, scope, sourceFilters, searchIndex])

  if (error) return <section className="product-page toronto-page"><div className="reference-empty-state"><strong>Toronto market data is unavailable.</strong><span>{error}</span></div></section>
  if (!payload) return <section className="product-page toronto-page"><div className="portal-loading">Loading the isolated Toronto market snapshot…</div></section>

  const sourceCoverage = Object.entries(payload.source_coverage).filter(([, summary]) => typeof summary.source_records === 'number' || typeof summary.matched_records === 'number')

  return <section className="product-page toronto-page">
    <div className="product-page-heading"><div><span className="page-kicker">Toronto · isolated beta</span><h1>Toronto Market</h1><p>Canonical municipal properties with source-backed environmental, health, planning and organization context. Toronto does not inherit NYC scoring or regulatory assertions.</p></div><div className="page-actions"><button onClick={() => exportTorontoCsv(filtered)}>Export {filtered.length.toLocaleString()} properties</button></div></div>
    <div className="toronto-limit-banner"><strong>Market denominator unknown.</strong><span>{payload.counts.documentary_confirmed_properties.toLocaleString()} documentary-confirmed properties are known, but TowerSignal does not claim a Toronto market-coverage percentage.</span></div>
    <div className="reference-metric-grid toronto-metrics" aria-label="Toronto market summary">
      <article><span className="reference-metric-icon">⌂</span><div><small>Canonical properties</small><strong>{payload.counts.canonical_properties.toLocaleString()}</strong><span>Municipal Address Point spine</span></div></article>
      <article><span className="reference-metric-icon success">✓</span><div><small>POC reconciled</small><strong>{payload.counts.original_poc_resolved}/{payload.counts.original_poc_properties}</strong><span>{payload.counts.original_poc_unresolved} retained unresolved</span></div></article>
      <article><span className="reference-metric-icon urgent">◎</span><div><small>Confirmed towers</small><strong>{payload.counts.documentary_confirmed_properties.toLocaleString()}</strong><span>Documentary evidence only</span></div></article>
      <article><span className="reference-metric-icon warning">⌁</span><div><small>Aerial review queue</small><strong>{payload.counts.aerial_review_candidates.toLocaleString()}</strong><span>Weak signal, not confirmation</span></div></article>
      <article><span className="reference-metric-icon">↔</span><div><small>Entity relationships</small><strong>{payload.counts.relationship_edges.toLocaleString()}</strong><span>Source role preserved</span></div></article>
    </div>
    <div className="toronto-filters">
      <label><span>Search</span><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Address, company, application or source record" /></label>
      <label><span>Tower evidence</span><select value={evidence} onChange={event => setEvidence(event.target.value as TorontoTowerEvidenceStatus | '')}><option value="">All evidence states</option>{Object.entries(evidenceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label><span>Source family</span><select value={source} onChange={event => setSource(event.target.value)}><option value="">All source families</option>{sources.map(value => <option key={value} value={value}>{sourceLabel(value)}</option>)}</select></label>
      <label><span>Organization role</span><select value={relationship} onChange={event => setRelationship(event.target.value)}><option value="">All organization roles</option>{relationships.map(value => <option key={value} value={value}>{humanize(value)}</option>)}</select></label>
      <label><span>Property scope</span><select value={scope} onChange={event => setScope(event.target.value as 'all' | 'poc' | 'expanded')}><option value="all">All canonical properties</option><option value="poc">Original POC only</option><option value="expanded">Expanded universe only</option></select></label>
      <div className="toronto-view-toggle"><button className={view === 'table' ? 'active-control' : ''} onClick={() => setView('table')}>Table</button><button className={view === 'map' ? 'active-control' : ''} onClick={() => setView('map')}>Map</button></div>
    </div>
    <details className="toronto-source-filter-panel"><summary>Source-specific filters</summary><div>
      <label><span>ChemTRAC chemical</span><select value={sourceFilters.chemical} onChange={event => setSourceFilters(current => ({ ...current, chemical: event.target.value }))}><option value="">All chemicals</option>{sourceFilterOptions.chemicals.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <label><span>ChemTRAC year</span><select value={sourceFilters.reportingYear} onChange={event => setSourceFilters(current => ({ ...current, reportingYear: event.target.value }))}><option value="">All reporting years</option>{sourceFilterOptions.reportingYears.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <label><span>AIC application</span><input value={sourceFilters.aicApplication} onChange={event => setSourceFilters(current => ({ ...current, aicApplication: event.target.value }))} placeholder="Application number" /></label>
      <label><span>AIC status</span><select value={sourceFilters.aicStatus} onChange={event => setSourceFilters(current => ({ ...current, aicStatus: event.target.value }))}><option value="">All AIC statuses</option>{sourceFilterOptions.aicStatuses.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <label><span>Health status</span><select value={sourceFilters.healthStatus} onChange={event => setSourceFilters(current => ({ ...current, healthStatus: event.target.value }))}><option value="">All health statuses</option>{sourceFilterOptions.healthStatuses.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <label><span>Environmental record</span><input value={sourceFilters.environmentalRecord} onChange={event => setSourceFilters(current => ({ ...current, environmentalRecord: event.target.value }))} placeholder="Facility, contaminant or record ID" /></label>
      <label><span>Company</span><input value={sourceFilters.company} onChange={event => setSourceFilters(current => ({ ...current, company: event.target.value }))} placeholder="Company or organization" /></label>
      <label><span>Permit signal</span><select value={sourceFilters.permitSignal} onChange={event => setSourceFilters(current => ({ ...current, permitSignal: event.target.value }))}><option value="">All permit signals</option>{sourceFilterOptions.permitSignals.map(value => <option key={value} value={value}>{humanize(value)}</option>)}</select></label>
      <label><span>Permit status</span><select value={sourceFilters.permitStatus} onChange={event => setSourceFilters(current => ({ ...current, permitStatus: event.target.value }))}><option value="">All permit statuses</option>{sourceFilterOptions.permitStatuses.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
      <label><span>Cooling tower lifecycle</span><select value={sourceFilters.permitLifecycle} onChange={event => setSourceFilters(current => ({ ...current, permitLifecycle: event.target.value }))}><option value="">All cooling tower lifecycle states</option>{sourceFilterOptions.permitLifecycles.map(value => <option key={value} value={value}>{humanize(value)}</option>)}</select></label>
      <label><span>Cooling tower interpretation</span><select value={sourceFilters.permitInterpretation} onChange={event => setSourceFilters(current => ({ ...current, permitInterpretation: event.target.value }))}><option value="">All current interpretations</option>{sourceFilterOptions.permitInterpretations.map(value => <option key={value} value={value}>{humanize(value)}</option>)}</select></label>
      <button onClick={() => setSourceFilters({ chemical: '', reportingYear: '', aicApplication: '', aicStatus: '', healthStatus: '', environmentalRecord: '', company: '', permitSignal: '', permitStatus: '', permitLifecycle: '', permitInterpretation: '' })}>Clear source filters</button>
    </div></details>
    <div className="toronto-result-heading"><strong>{filtered.length.toLocaleString()} matching properties</strong><span>All links use deterministic municipal identity.</span></div>
    {view === 'map' ? <TorontoMarketMap properties={filtered} selectedId={selected?.property_id ?? null} onSelect={openProperty} /> : <div className="toronto-table-wrap"><table className="toronto-table"><thead><tr><th>Property</th><th>Tower evidence</th><th>Sources</th><th>Relationships</th><th>Identity</th></tr></thead><tbody>{filtered.slice(0, 500).map(property => <tr key={property.property_id} onClick={() => openProperty(property)}><td><button>{property.display_address}</button><small>{property.address_point_id}</small></td><td><span className={`toronto-evidence-badge status-${property.tower_evidence_status.toLowerCase()}`}>{evidenceLabels[property.tower_evidence_status]}</span></td><td>{property.source_keys.length}</td><td>{property.relationships.length}</td><td>{property.identity_confidence || 'Deterministic'}</td></tr>)}</tbody></table>{filtered.length > 500 && <p className="toronto-table-limit">Showing the first 500 matching properties. Refine the filters or export the full result set.</p>}</div>}
    <details className="toronto-coverage"><summary>Source coverage and deterministic join results</summary><div className="toronto-coverage-wrap"><table><thead><tr><th>Source</th><th>Records</th><th>Addressable</th><th>Matched records</th><th>Properties</th><th>Unmatched</th><th>Official source</th></tr></thead><tbody>{sourceCoverage.map(([key, summary]) => <tr key={key}><td><strong>{sourceLabel(key)}</strong>{(summary.identity_limitation || summary.scope_limitation) && <small>{summary.identity_limitation || summary.scope_limitation}</small>}</td><td>{summary.source_records?.toLocaleString() ?? '—'}</td><td>{summary.records_with_property_address?.toLocaleString() ?? '—'}</td><td>{summary.matched_records?.toLocaleString() ?? '—'}</td><td>{summary.matched_canonical_properties?.toLocaleString() ?? '—'}</td><td>{summary.unmatched_source_records?.toLocaleString() ?? '—'}</td><td>{payload.source_catalog[key]?.dataset_url ? <a href={payload.source_catalog[key].dataset_url} target="_blank" rel="noreferrer">Open ↗</a> : '—'}</td></tr>)}</tbody></table></div></details>
    <details className="toronto-limitations"><summary>Known data limitations</summary><ul>{payload.limitations.map(item => <li key={item}>{item}</li>)}</ul>{payload.unresolved_poc.length > 0 && <div><strong>Unresolved original POC addresses</strong><ul>{payload.unresolved_poc.map(item => <li key={item.property_key}>{item.input_address || item.property_key} — {item.resolution_status.replaceAll('_', ' ').toLowerCase()}</li>)}</ul></div>}</details>
    {selected && <PropertyDetail property={selected} sourceCatalog={payload.source_catalog} onClose={closeProperty} />}
  </section>
}

export function TorontoMarketPage() {
  return <TorontoParityShell explorer={<TorontoMarketExplorer />} />
}
