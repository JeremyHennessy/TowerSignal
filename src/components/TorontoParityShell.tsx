import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { loadTorontoMarket } from '../data/api'
import type { TorontoMarketPayload, TorontoProperty, TorontoSourceLink } from '../types/toronto'
import { TorontoBenchmarkingPage } from './TorontoBenchmarkingPage'

type TorontoWorkspace = 'market' | 'benchmarking' | 'prospects' | 'opportunities' | 'companies' | 'portfolios' | 'watchlist' | 'sources'

type ProspectRow = {
  property: TorontoProperty
  attention: number
  tier: 'HIGH' | 'MEDIUM' | 'CONTEXT'
  factors: string[]
  opportunities: string[]
}

type CompanyRow = {
  key: string
  name: string
  propertyIds: Set<string>
  confirmedPropertyIds: Set<string>
  roles: Set<string>
  sources: Set<string>
  highAttentionPropertyIds: Set<string>
}

const WATCHLIST_KEY = 'towersignal-toronto-watchlist-v1'
const permitSources = new Set(['toronto_building_permits_active_targeted', 'toronto_building_permits_cleared_targeted_since_2017'])
const planningSources = new Set(['toronto_aic_applications', 'development_pipeline', 'affordable_housing_pipeline'])
const environmentSources = new Set(['chemtrac_history', 'chemtrac_2024', 'ontario_environmental_compliance_reports', 'toronto_highrise_residential_health_hazards'])
const portfolioRoles = new Set(['OWNER_OF', 'PROPERTY_MANAGER_OF', 'LICENCE_HOLDER_AT_PROPERTY', 'CHEMTRAC_REPORTING_FACILITY_AT', 'SUCCESSFUL_BIDDER_AT_PROPERTY'])

const sourceLabels: Record<string, string> = {
  chemtrac_history: 'ChemTRAC history',
  chemtrac_2024: 'ChemTRAC 2024',
  toronto_aic_applications: 'Toronto AIC applications',
  toronto_highrise_residential_health_hazards: 'Highrise residential health hazards',
  toronto_building_permits_active_targeted: 'Active building permits',
  toronto_building_permits_cleared_targeted_since_2017: 'Cleared building permits since 2017',
  ontario_environmental_compliance_reports: 'Ontario environmental compliance',
  ontario_bps_energy_2024: 'Ontario BPS energy',
  tobids_awarded_contracts: 'TOBids awarded contracts',
  rentsafe_registration: 'RentSafe registration',
  apartment_building_evaluation: 'Apartment building evaluations',
  development_pipeline: 'Development pipeline',
  affordable_housing_pipeline: 'Affordable housing pipeline',
  renewable_energy_installations: 'Renewable energy installations',
  business_licence_matches_prior_poc: 'Business licences',
  tobids_awarded_contracts_exact_document_address_prior_poc: 'TOBids exact-address awards',
  toronto_public_notices_exact_prior_poc: 'Toronto public notices',
  '311_matches_prior_poc': '311 records',
}

function humanize(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, character => character.toUpperCase())
}

function sourceLabel(value: string): string {
  return sourceLabels[value] ?? humanize(value)
}

function detailValue(link: TorontoSourceLink, label: string): string {
  return link.record_details.find(item => item.label === label)?.value ?? ''
}

function hasMechanicalPermit(property: TorontoProperty): boolean {
  return property.source_links.some(link => permitSources.has(link.source_key) && detailValue(link, 'Mechanical signals').trim().length > 0)
}

function hasActivePermit(property: TorontoProperty): boolean {
  return property.source_links.some(link => link.source_key === 'toronto_building_permits_active_targeted')
}

function hasRecentPlanning(property: TorontoProperty): boolean {
  return property.source_links.some(link => planningSources.has(link.source_key))
}

function hasEnvironmentalContext(property: TorontoProperty): boolean {
  return property.source_keys.some(key => environmentSources.has(key))
}

function hasRole(property: TorontoProperty, role: string): boolean {
  return property.relationships.some(item => item.relationship === role)
}

function buildProspect(property: TorontoProperty): ProspectRow {
  let attention = 0
  const factors: string[] = []
  const opportunities: string[] = []

  if (property.tower_evidence_status === 'CONFIRMED_DOCUMENTARY_TOWER') {
    attention += 45
    factors.push('Documentary-confirmed tower')
  } else if (property.tower_evidence_status === 'STRONG_DOCUMENTARY_CANDIDATE') {
    attention += 28
    factors.push('Strong documentary candidate')
  } else if (property.tower_evidence_status === 'AIC_DOCUMENT_CANDIDATE') {
    attention += 18
    factors.push('AIC document candidate')
  }

  const mechanicalPermit = hasMechanicalPermit(property)
  const activePermit = hasActivePermit(property)
  if (mechanicalPermit) {
    attention += 22
    factors.push('Mechanical permit signal')
    opportunities.push('Mechanical / cooling-system permit activity')
  } else if (activePermit) {
    attention += 12
    factors.push('Active building permit')
    opportunities.push('Active project timing')
  }

  if (hasRecentPlanning(property)) {
    attention += 8
    factors.push('Planning / development record')
    opportunities.push('Planning or development activity')
  }
  if (property.source_keys.includes('chemtrac_2024') || property.source_keys.includes('chemtrac_history')) {
    attention += 7
    factors.push('ChemTRAC operating context')
  }
  if (hasEnvironmentalContext(property)) {
    attention += 5
    opportunities.push('Environmental / health context')
  }

  const manager = hasRole(property, 'PROPERTY_MANAGER_OF')
  const owner = hasRole(property, 'OWNER_OF')
  if (manager || owner) {
    attention += 8
    factors.push(manager ? 'Property manager identified' : 'Owner identified')
  } else if (property.tower_evidence_status === 'CONFIRMED_DOCUMENTARY_TOWER') {
    opportunities.push('Relationship research gap')
  }

  attention += Math.min(6, property.source_keys.length)
  attention += Math.min(4, property.relationships.length)
  attention = Math.min(100, attention)

  if (property.tower_evidence_status === 'CONFIRMED_DOCUMENTARY_TOWER' && mechanicalPermit) opportunities.unshift('Confirmed tower + mechanical project timing')
  if (property.source_keys.length >= 4) opportunities.push('Multi-source account context')

  return {
    property,
    attention,
    tier: attention >= 65 ? 'HIGH' : attention >= 35 ? 'MEDIUM' : 'CONTEXT',
    factors: [...new Set(factors)],
    opportunities: [...new Set(opportunities)],
  }
}

function normalizeOrganization(value: string): string {
  return value.trim().replace(/\s+/g, ' ').toUpperCase()
}

function buildCompanies(properties: TorontoProperty[], prospects: Map<string, ProspectRow>): CompanyRow[] {
  const companies = new Map<string, CompanyRow>()
  for (const property of properties) {
    for (const relationship of property.relationships) {
      const key = normalizeOrganization(relationship.organization)
      if (!key) continue
      const current = companies.get(key) ?? {
        key,
        name: relationship.organization.trim(),
        propertyIds: new Set<string>(),
        confirmedPropertyIds: new Set<string>(),
        roles: new Set<string>(),
        sources: new Set<string>(),
        highAttentionPropertyIds: new Set<string>(),
      }
      current.propertyIds.add(property.property_id)
      current.roles.add(relationship.relationship)
      current.sources.add(relationship.source_key)
      if (property.tower_evidence_status === 'CONFIRMED_DOCUMENTARY_TOWER') current.confirmedPropertyIds.add(property.property_id)
      if ((prospects.get(property.property_id)?.attention ?? 0) >= 65) current.highAttentionPropertyIds.add(property.property_id)
      companies.set(key, current)
    }
  }
  return [...companies.values()].sort((left, right) => right.propertyIds.size - left.propertyIds.size || right.confirmedPropertyIds.size - left.confirmedPropertyIds.size || left.name.localeCompare(right.name))
}

function matchesSearch(row: ProspectRow, term: string): boolean {
  if (!term) return true
  const property = row.property
  return [property.display_address, property.property_id, property.address_point_id, ...property.source_keys, ...property.relationships.flatMap(item => [item.organization, item.relationship]), ...row.factors, ...row.opportunities].join(' ').toLowerCase().includes(term)
}

function openInMarket(property: TorontoProperty, setView: (view: TorontoWorkspace) => void) {
  window.location.hash = `#/toronto/${encodeURIComponent(property.property_id)}`
  setView('market')
}

function TorontoWorkspaceTabs({ view, onChange, watchCount }: { view: TorontoWorkspace; onChange: (view: TorontoWorkspace) => void; watchCount: number }) {
  const items: { value: TorontoWorkspace; label: string }[] = [
    { value: 'market', label: 'Market' },
    { value: 'benchmarking', label: 'Benchmarking' },
    { value: 'prospects', label: 'Prospects' },
    { value: 'opportunities', label: 'Opportunities' },
    { value: 'companies', label: 'Companies' },
    { value: 'portfolios', label: 'Portfolios' },
    { value: 'watchlist', label: `Watchlist${watchCount ? ` ${watchCount}` : ''}` },
    { value: 'sources', label: 'Sources' },
  ]
  return <nav className="toronto-parity-tabs" aria-label="Toronto workspaces">{items.map(item => <button key={item.value} className={view === item.value ? 'active-control' : ''} onClick={() => onChange(item.value)}>{item.label}</button>)}</nav>
}

function PropertyAction({ watched, onToggleWatch, onOpen }: { watched: boolean; onToggleWatch: () => void; onOpen: () => void }) {
  return <div className="toronto-parity-actions"><button className="primary" onClick={onOpen}>Open evidence</button><button className={watched ? 'active-control' : ''} onClick={onToggleWatch}>{watched ? 'Watching' : 'Watch'}</button></div>
}

function ProspectTable({ rows, watchedIds, onToggleWatch, onOpen }: { rows: ProspectRow[]; watchedIds: Set<string>; onToggleWatch: (id: string) => void; onOpen: (property: TorontoProperty) => void }) {
  return <div className="toronto-table-wrap"><table className="toronto-table toronto-parity-table"><thead><tr><th>Property</th><th>Attention</th><th>Why now</th><th>Organizations</th><th>Actions</th></tr></thead><tbody>{rows.slice(0, 500).map(row => <tr key={row.property.property_id}><td><button className="toronto-address-button" onClick={() => onOpen(row.property)}>{row.property.display_address}</button><small>{row.property.address_point_id}</small></td><td><span className={`toronto-attention-badge tier-${row.tier.toLowerCase()}`}>{row.attention} · {humanize(row.tier)}</span><small>Commercial ranking only</small></td><td><div className="toronto-chip-list">{row.factors.slice(0, 4).map(value => <span key={value}>{value}</span>)}</div></td><td><strong>{row.property.relationships.length}</strong><small>{[...new Set(row.property.relationships.map(item => item.organization))].slice(0, 2).join(' · ') || 'No organization linked'}</small></td><td><PropertyAction watched={watchedIds.has(row.property.property_id)} onToggleWatch={() => onToggleWatch(row.property.property_id)} onOpen={() => onOpen(row.property)} /></td></tr>)}</tbody></table>{rows.length > 500 && <p className="toronto-table-limit">Showing the first 500 ranked properties.</p>}</div>
}

function CompanyTable({ rows, propertiesById, onOpen, portfolioOnly }: { rows: CompanyRow[]; propertiesById: Map<string, TorontoProperty>; onOpen: (property: TorontoProperty) => void; portfolioOnly?: boolean }) {
  return <div className="toronto-table-wrap"><table className="toronto-table toronto-parity-table"><thead><tr><th>Organization</th><th>Properties</th><th>Confirmed towers</th><th>High attention</th><th>Roles</th><th>Example property</th></tr></thead><tbody>{rows.slice(0, 500).map(company => {
    const property = propertiesById.get([...company.propertyIds][0])
    return <tr key={company.key}><td><strong>{company.name}</strong><small>{[...company.sources].map(sourceLabel).slice(0, 2).join(' · ')}</small></td><td>{company.propertyIds.size}</td><td>{company.confirmedPropertyIds.size}</td><td>{company.highAttentionPropertyIds.size}</td><td><div className="toronto-chip-list">{[...company.roles].slice(0, 4).map(role => <span key={role}>{humanize(role)}</span>)}</div></td><td>{property ? <button className="toronto-address-button" onClick={() => onOpen(property)}>{property.display_address}</button> : '—'}</td></tr>
  })}</tbody></table>{rows.length > 500 && <p className="toronto-table-limit">Showing the first 500 organizations{portfolioOnly ? ' with portfolio-capable relationships' : ''}.</p>}</div>
}

export function TorontoParityShell({ explorer }: { explorer: ReactNode }) {
  const [view, setView] = useState<TorontoWorkspace>('market')
  const [payload, setPayload] = useState<TorontoMarketPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [opportunityFilter, setOpportunityFilter] = useState('all')
  const [companyRole, setCompanyRole] = useState('')
  const [watchedIds, setWatchedIds] = useState<Set<string>>(() => {
    try {
      const parsed = JSON.parse(localStorage.getItem(WATCHLIST_KEY) ?? '[]')
      return new Set(Array.isArray(parsed) ? parsed.filter(value => typeof value === 'string') : [])
    } catch {
      return new Set<string>()
    }
  })

  useEffect(() => {
    if (view === 'market' || view === 'benchmarking' || payload || error) return
    loadTorontoMarket().then(setPayload).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load Toronto market data'))
  }, [view, payload, error])

  const toggleWatch = (propertyId: string) => setWatchedIds(current => {
    const next = new Set(current)
    if (next.has(propertyId)) next.delete(propertyId)
    else next.add(propertyId)
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify([...next]))
    return next
  })

  const prospects = useMemo(() => payload ? payload.properties.map(buildProspect).sort((left, right) => right.attention - left.attention || right.property.source_keys.length - left.property.source_keys.length || left.property.display_address.localeCompare(right.property.display_address)) : [], [payload])
  const prospectById = useMemo(() => new Map(prospects.map(row => [row.property.property_id, row])), [prospects])
  const propertiesById = useMemo(() => new Map((payload?.properties ?? []).map(property => [property.property_id, property])), [payload])
  const companies = useMemo(() => payload ? buildCompanies(payload.properties, prospectById) : [], [payload, prospectById])
  const roles = useMemo(() => [...new Set(companies.flatMap(company => [...company.roles]))].sort(), [companies])
  const term = search.trim().toLowerCase()
  const filteredProspects = useMemo(() => prospects.filter(row => matchesSearch(row, term)), [prospects, term])
  const highProspects = useMemo(() => filteredProspects.filter(row => row.attention >= 65), [filteredProspects])
  const opportunityRows = useMemo(() => filteredProspects.filter(row => {
    if (row.opportunities.length === 0) return false
    if (opportunityFilter === 'all') return true
    if (opportunityFilter === 'confirmed-permit') return row.opportunities.includes('Confirmed tower + mechanical project timing')
    if (opportunityFilter === 'mechanical') return row.opportunities.includes('Mechanical / cooling-system permit activity')
    if (opportunityFilter === 'planning') return row.opportunities.includes('Planning or development activity')
    if (opportunityFilter === 'relationship-gap') return row.opportunities.includes('Relationship research gap')
    if (opportunityFilter === 'multi-source') return row.opportunities.includes('Multi-source account context')
    if (opportunityFilter === 'environment') return row.opportunities.includes('Environmental / health context')
    return true
  }), [filteredProspects, opportunityFilter])
  const filteredCompanies = useMemo(() => companies.filter(company => {
    if (companyRole && !company.roles.has(companyRole)) return false
    if (!term) return true
    return [company.name, ...company.roles, ...company.sources].join(' ').toLowerCase().includes(term)
  }), [companies, companyRole, term])
  const portfolioCompanies = useMemo(() => filteredCompanies.filter(company => [...company.roles].some(role => portfolioRoles.has(role)) && company.propertyIds.size >= 2), [filteredCompanies])
  const watchRows = useMemo(() => prospects.filter(row => watchedIds.has(row.property.property_id)), [prospects, watchedIds])

  const changeView = (next: TorontoWorkspace) => {
    setView(next)
    if (next !== 'market') window.location.hash = '#/toronto'
  }
  const openProperty = (property: TorontoProperty) => openInMarket(property, setView)

  return <div className="toronto-parity-shell">
    <TorontoWorkspaceTabs view={view} onChange={changeView} watchCount={watchedIds.size} />
    {view === 'market' ? explorer : <>
      {view === 'benchmarking' && <TorontoBenchmarkingPage />}
      {error && view !== 'benchmarking' && <section className="product-page toronto-page"><div className="reference-empty-state"><strong>Toronto commercial workspace unavailable.</strong><span>{error}</span></div></section>}
      {view !== 'benchmarking' && !error && !payload && <section className="product-page toronto-page"><div className="portal-loading">Loading Toronto commercial intelligence…</div></section>}
      {payload && view === 'prospects' && <section className="product-page toronto-page toronto-parity-page">
        <div className="product-page-heading"><div><span className="page-kicker">Toronto · commercial intelligence</span><h1>Prospect workspace</h1><p>Rank source-backed Toronto properties for commercial attention using documentary tower evidence, project timing, joined source depth and identified organizations. This attention index is not a regulatory or compliance score.</p></div></div>
        <div className="reference-metric-grid toronto-parity-metrics"><article><span className="reference-metric-icon urgent">↗</span><div><small>High attention</small><strong>{prospects.filter(row => row.attention >= 65).length.toLocaleString()}</strong><span>Commercial rank 65+</span></div></article><article><span className="reference-metric-icon success">◎</span><div><small>Confirmed towers</small><strong>{payload.counts.documentary_confirmed_properties.toLocaleString()}</strong><span>Documentary evidence only</span></div></article><article><span className="reference-metric-icon warning">⌁</span><div><small>Mechanical permit signals</small><strong>{prospects.filter(row => hasMechanicalPermit(row.property)).length.toLocaleString()}</strong><span>Permit text signal</span></div></article><article><span className="reference-metric-icon">↔</span><div><small>Relationship-ready</small><strong>{prospects.filter(row => row.property.relationships.length > 0).length.toLocaleString()}</strong><span>At least one source-backed role</span></div></article><article><span className="reference-metric-icon">⌂</span><div><small>Canonical universe</small><strong>{payload.counts.canonical_properties.toLocaleString()}</strong><span>Deterministic address-point spine</span></div></article></div>
        <div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search address, company, source or signal" /><strong>{highProspects.length.toLocaleString()} high-attention matches</strong></div>
        <ProspectTable rows={filteredProspects} watchedIds={watchedIds} onToggleWatch={toggleWatch} onOpen={openProperty} />
      </section>}
      {payload && view === 'opportunities' && <section className="product-page toronto-page toronto-parity-page">
        <div className="product-page-heading"><div><span className="page-kicker">Toronto · why now</span><h1>Opportunity queues</h1><p>Surface defensible timing and research queues from Toronto-specific public evidence. Signals organize work; they do not assert equipment condition, compliance, ownership or procurement intent beyond the cited records.</p></div></div>
        <div className="toronto-opportunity-cards"><button onClick={() => setOpportunityFilter('confirmed-permit')}><small>Confirmed + mechanical permit</small><strong>{prospects.filter(row => row.opportunities.includes('Confirmed tower + mechanical project timing')).length.toLocaleString()}</strong></button><button onClick={() => setOpportunityFilter('mechanical')}><small>Mechanical permit activity</small><strong>{prospects.filter(row => row.opportunities.includes('Mechanical / cooling-system permit activity')).length.toLocaleString()}</strong></button><button onClick={() => setOpportunityFilter('relationship-gap')}><small>Confirmed relationship gaps</small><strong>{prospects.filter(row => row.opportunities.includes('Relationship research gap')).length.toLocaleString()}</strong></button><button onClick={() => setOpportunityFilter('multi-source')}><small>Multi-source context</small><strong>{prospects.filter(row => row.opportunities.includes('Multi-source account context')).length.toLocaleString()}</strong></button><button onClick={() => setOpportunityFilter('planning')}><small>Planning / development</small><strong>{prospects.filter(row => row.opportunities.includes('Planning or development activity')).length.toLocaleString()}</strong></button></div>
        <div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search opportunity accounts" /><select value={opportunityFilter} onChange={event => setOpportunityFilter(event.target.value)}><option value="all">All opportunity signals</option><option value="confirmed-permit">Confirmed tower + mechanical permit</option><option value="mechanical">Mechanical / cooling-system permit</option><option value="planning">Planning / development</option><option value="relationship-gap">Relationship research gap</option><option value="multi-source">Multi-source context</option><option value="environment">Environmental / health context</option></select><strong>{opportunityRows.length.toLocaleString()} matches</strong></div>
        <div className="toronto-opportunity-list">{opportunityRows.slice(0, 300).map(row => <article key={row.property.property_id}><div><span className={`toronto-attention-badge tier-${row.tier.toLowerCase()}`}>{row.attention}</span><button className="toronto-address-button" onClick={() => openProperty(row.property)}>{row.property.display_address}</button><small>{row.property.source_keys.length} source families · {row.property.relationships.length} relationships</small></div><div className="toronto-chip-list">{row.opportunities.map(value => <span key={value}>{value}</span>)}</div><PropertyAction watched={watchedIds.has(row.property.property_id)} onToggleWatch={() => toggleWatch(row.property.property_id)} onOpen={() => openProperty(row.property)} /></article>)}</div>
      </section>}
      {payload && view === 'companies' && <section className="product-page toronto-page toronto-parity-page">
        <div className="product-page-heading"><div><span className="page-kicker">Toronto · relationship graph</span><h1>Companies</h1><p>Aggregate source-backed organizations across property manager, owner, licence holder, reporting facility and procurement relationships. Role provenance remains attached to every underlying property.</p></div></div>
        <div className="reference-metric-grid toronto-parity-metrics"><article><span className="reference-metric-icon">↔</span><div><small>Organizations</small><strong>{companies.length.toLocaleString()}</strong><span>Normalized display-name aggregation</span></div></article><article><span className="reference-metric-icon success">⌂</span><div><small>Multi-property</small><strong>{companies.filter(company => company.propertyIds.size >= 2).length.toLocaleString()}</strong><span>2+ linked properties</span></div></article><article><span className="reference-metric-icon urgent">◎</span><div><small>Linked confirmed towers</small><strong>{companies.filter(company => company.confirmedPropertyIds.size > 0).length.toLocaleString()}</strong><span>Organizations touching confirmed properties</span></div></article></div>
        <div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search organization or role" /><select value={companyRole} onChange={event => setCompanyRole(event.target.value)}><option value="">All relationship roles</option>{roles.map(role => <option key={role} value={role}>{humanize(role)}</option>)}</select><strong>{filteredCompanies.length.toLocaleString()} organizations</strong></div>
        <CompanyTable rows={filteredCompanies} propertiesById={propertiesById} onOpen={openProperty} />
      </section>}
      {payload && view === 'portfolios' && <section className="product-page toronto-page toronto-parity-page">
        <div className="product-page-heading"><div><span className="page-kicker">Toronto · account groups</span><h1>Portfolios</h1><p>Group multi-property organizations from defensible relationship edges so sales and research teams can work accounts at the portfolio level rather than one address at a time.</p></div></div>
        <div className="reference-metric-grid toronto-parity-metrics"><article><span className="reference-metric-icon success">⌂</span><div><small>Multi-property portfolios</small><strong>{portfolioCompanies.length.toLocaleString()}</strong><span>2+ properties, portfolio-capable role</span></div></article><article><span className="reference-metric-icon urgent">◎</span><div><small>Portfolios with confirmed towers</small><strong>{portfolioCompanies.filter(company => company.confirmedPropertyIds.size > 0).length.toLocaleString()}</strong><span>Documentary-confirmed property link</span></div></article><article><span className="reference-metric-icon">↗</span><div><small>High-attention portfolios</small><strong>{portfolioCompanies.filter(company => company.highAttentionPropertyIds.size > 0).length.toLocaleString()}</strong><span>At least one 65+ account</span></div></article></div>
        <div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search portfolio organization" /><select value={companyRole} onChange={event => setCompanyRole(event.target.value)}><option value="">All portfolio roles</option>{roles.filter(role => portfolioRoles.has(role)).map(role => <option key={role} value={role}>{humanize(role)}</option>)}</select><strong>{portfolioCompanies.length.toLocaleString()} portfolios</strong></div>
        <CompanyTable rows={portfolioCompanies} propertiesById={propertiesById} onOpen={openProperty} portfolioOnly />
      </section>}
      {payload && view === 'watchlist' && <section className="product-page toronto-page toronto-parity-page">
        <div className="product-page-heading"><div><span className="page-kicker">Toronto · browser-local workflow</span><h1>Watchlist</h1><p>Save Toronto properties for repeat review without enabling the shared NY workflow backend. This beta watchlist stays in this browser and does not imply monitoring of source changes.</p></div></div>
        {watchRows.length ? <ProspectTable rows={watchRows} watchedIds={watchedIds} onToggleWatch={toggleWatch} onOpen={openProperty} /> : <div className="reference-empty-state"><strong>No Toronto properties are watched yet.</strong><span>Add properties from Prospects or Opportunities.</span></div>}
      </section>}
      {payload && view === 'sources' && <section className="product-page toronto-page toronto-parity-page">
        <div className="product-page-heading"><div><span className="page-kicker">Toronto · evidence operations</span><h1>Source health & coverage</h1><p>Inspect source-level record counts, deterministic match results and known identity limitations before relying on a prospect or portfolio conclusion.</p></div></div>
        <div className="reference-metric-grid toronto-parity-metrics"><article><span className="reference-metric-icon success">✓</span><div><small>Official source families</small><strong>{payload.counts.official_source_families.toLocaleString()}</strong><span>Published in current app payload</span></div></article><article><span className="reference-metric-icon">↔</span><div><small>Source links</small><strong>{payload.counts.source_links.toLocaleString()}</strong><span>Property-to-source links</span></div></article><article><span className="reference-metric-icon">⌁</span><div><small>Record-level links</small><strong>{payload.counts.record_level_source_links.toLocaleString()}</strong><span>Durable row-level where available</span></div></article></div>
        <div className="toronto-table-wrap"><table className="toronto-table toronto-source-health-table"><thead><tr><th>Source</th><th>Status</th><th>Records</th><th>Matched</th><th>Properties</th><th>Match rate</th><th>Limitation</th><th>Official</th></tr></thead><tbody>{Object.entries(payload.source_coverage).filter(([, summary]) => summary.source_records != null || summary.matched_records != null).sort(([, left], [, right]) => (right.matched_canonical_properties ?? 0) - (left.matched_canonical_properties ?? 0)).map(([key, summary]) => {
          const rate = summary.source_records && summary.matched_records != null ? `${Math.round(summary.matched_records / summary.source_records * 100)}%` : '—'
          return <tr key={key}><td><strong>{sourceLabel(key)}</strong></td><td>{summary.status ? humanize(summary.status) : '—'}</td><td>{summary.source_records?.toLocaleString() ?? '—'}</td><td>{summary.matched_records?.toLocaleString() ?? '—'}</td><td>{summary.matched_canonical_properties?.toLocaleString() ?? '—'}</td><td>{rate}</td><td><small>{summary.identity_limitation || summary.scope_limitation || 'Deterministic join contract'}</small></td><td>{payload.source_catalog[key]?.dataset_url ? <a href={payload.source_catalog[key].dataset_url} target="_blank" rel="noreferrer">Open ↗</a> : '—'}</td></tr>
        })}</tbody></table></div>
        <section className="toronto-parity-limitations"><h2>Known limitations</h2><ul>{payload.limitations.map(item => <li key={item}>{item}</li>)}</ul></section>
      </section>}
    </>}
  </div>
}
