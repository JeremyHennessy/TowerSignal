import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { loadTorontoMarket } from '../data/api'
import type { TorontoMarketPayload, TorontoProperty, TorontoSourceLink } from '../types/toronto'
import { buildTorontoCompanyCsv, buildTorontoLeadSummary, buildTorontoProspectCsv, copyText, downloadCsv } from '../utils/torontoCommercialExport'
import { TorontoBenchmarkingPage } from './TorontoBenchmarkingPage'

type TorontoView = 'home' | 'prospect' | 'monitor' | 'map' | 'market' | 'changes' | 'opportunities' | 'companies' | 'portfolios' | 'workflow' | 'source-health' | 'benchmarking' | 'property' | 'company' | 'portfolio'

type TorontoRoute = {
  view: TorontoView
  id: string | null
  from: TorontoView | null
  fromId: string | null
  search: string
}

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
const routeViews = new Set<TorontoView>(['home', 'prospect', 'monitor', 'map', 'market', 'changes', 'opportunities', 'companies', 'portfolios', 'workflow', 'source-health', 'benchmarking', 'property', 'company', 'portfolio'])
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

function normalizeOrganization(value: string): string {
  return value.trim().replace(/\s+/g, ' ').toUpperCase()
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
  if (hasMechanicalPermit(property)) {
    attention += 22
    factors.push('Mechanical permit signal')
    opportunities.push('Mechanical / cooling-system permit activity')
  } else if (hasActivePermit(property)) {
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
  if (property.tower_evidence_status === 'CONFIRMED_DOCUMENTARY_TOWER' && hasMechanicalPermit(property)) opportunities.unshift('Confirmed tower + mechanical project timing')
  if (property.source_keys.length >= 4) opportunities.push('Multi-source account context')
  return { property, attention, tier: attention >= 65 ? 'HIGH' : attention >= 35 ? 'MEDIUM' : 'CONTEXT', factors: [...new Set(factors)], opportunities: [...new Set(opportunities)] }
}

function buildCompanies(properties: TorontoProperty[], prospects: Map<string, ProspectRow>): CompanyRow[] {
  const companies = new Map<string, CompanyRow>()
  for (const property of properties) {
    for (const relationship of property.relationships) {
      const key = normalizeOrganization(relationship.organization)
      if (!key) continue
      const current = companies.get(key) ?? { key, name: relationship.organization.trim(), propertyIds: new Set<string>(), confirmedPropertyIds: new Set<string>(), roles: new Set<string>(), sources: new Set<string>(), highAttentionPropertyIds: new Set<string>() }
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

function parseTorontoRoute(): TorontoRoute {
  const raw = window.location.hash.replace(/^#\/?/, '')
  const [path, query = ''] = raw.split('?')
  const parts = path.split('/').filter(Boolean)
  const params = new URLSearchParams(query)
  const candidate = parts[0] === 'toronto' ? parts[1] : null
  if (!candidate) return { view: 'home', id: null, from: null, fromId: null, search: params.get('search') ?? '' }
  if (!routeViews.has(candidate as TorontoView)) {
    return { view: 'market', id: decodeURIComponent(candidate), from: null, fromId: null, search: params.get('search') ?? '' }
  }
  const fromValue = params.get('from')
  return {
    view: candidate as TorontoView,
    id: parts[2] ? decodeURIComponent(parts[2]) : null,
    from: fromValue && routeViews.has(fromValue as TorontoView) ? fromValue as TorontoView : null,
    fromId: params.get('fromId'),
    search: params.get('search') ?? '',
  }
}

function routeHash(view: TorontoView, id?: string | null, from?: TorontoView | null, fromId?: string | null, search?: string): string {
  const path = id ? `#/toronto/${view}/${encodeURIComponent(id)}` : `#/toronto/${view}`
  const params = new URLSearchParams()
  if (from) params.set('from', from)
  if (fromId) params.set('fromId', fromId)
  if (search) params.set('search', search)
  const query = params.toString()
  return query ? `${path}?${query}` : path
}

function viewLabel(view: TorontoView): string {
  const labels: Partial<Record<TorontoView, string>> = {
    home: 'Home', prospect: 'Prospect', monitor: 'Monitor', map: 'Map', market: 'Toronto Market', changes: 'Toronto Changes', opportunities: 'Opportunities', companies: 'Companies', portfolios: 'Portfolios', workflow: 'Workflow', 'source-health': 'Source Health', benchmarking: 'Benchmarking', company: 'Company', portfolio: 'Portfolio', property: 'Property',
  }
  return labels[view] ?? humanize(view)
}

function matchesSearch(row: ProspectRow, term: string): boolean {
  if (!term) return true
  const property = row.property
  return [property.display_address, property.property_id, property.address_point_id, ...property.source_keys, ...property.relationships.flatMap(item => [item.organization, item.relationship]), ...row.factors, ...row.opportunities].join(' ').toLowerCase().includes(term)
}

function PropertyActions({ row, watched, onOpen, onCopyLead, onToggleWatch }: { row: ProspectRow; watched: boolean; onOpen: () => void; onCopyLead: () => void; onToggleWatch: () => void }) {
  return <div className="toronto-parity-actions"><button className="primary" onClick={onOpen}>Open profile →</button><button onClick={onCopyLead}>Copy lead</button><button className={watched ? 'active-control' : ''} onClick={onToggleWatch}>{watched ? 'Watching' : 'Watch'}</button></div>
}

function ProspectTable({ rows, watchedIds, onOpen, onCopyLead, onToggleWatch }: { rows: ProspectRow[]; watchedIds: Set<string>; onOpen: (row: ProspectRow) => void; onCopyLead: (row: ProspectRow) => void; onToggleWatch: (id: string) => void }) {
  return <div className="toronto-table-wrap"><table className="toronto-table toronto-parity-table"><thead><tr><th>Property</th><th>Attention</th><th>Why now</th><th>Organizations</th><th>Action</th></tr></thead><tbody>{rows.slice(0, 500).map(row => <tr key={row.property.property_id}><td><button className="toronto-address-button" onClick={() => onOpen(row)}>{row.property.display_address}</button><small>{row.property.address_point_id}</small></td><td><span className={`toronto-attention-badge tier-${row.tier.toLowerCase()}`}>{row.attention} · {humanize(row.tier)}</span><small>Commercial ranking only</small></td><td><div className="toronto-chip-list">{row.factors.slice(0, 4).map(value => <span key={value}>{value}</span>)}</div></td><td><strong>{row.property.relationships.length}</strong><small>{[...new Set(row.property.relationships.map(item => item.organization))].slice(0, 2).join(' · ') || 'No organization linked'}</small></td><td><PropertyActions row={row} watched={watchedIds.has(row.property.property_id)} onOpen={() => onOpen(row)} onCopyLead={() => onCopyLead(row)} onToggleWatch={() => onToggleWatch(row.property.property_id)} /></td></tr>)}</tbody></table>{rows.length > 500 && <p className="toronto-table-limit">Showing the first 500 ranked properties.</p>}</div>
}

function CompanyTable({ rows, propertiesById, onOpenCompany, onOpenProperty, portfolio }: { rows: CompanyRow[]; propertiesById: Map<string, TorontoProperty>; onOpenCompany: (company: CompanyRow) => void; onOpenProperty: (property: TorontoProperty) => void; portfolio?: boolean }) {
  return <div className="toronto-table-wrap"><table className="toronto-table toronto-parity-table"><thead><tr><th>Organization</th><th>Properties</th><th>Confirmed towers</th><th>High attention</th><th>Roles</th><th>Example property</th><th>Action</th></tr></thead><tbody>{rows.slice(0, 500).map(company => {
    const property = propertiesById.get([...company.propertyIds][0])
    return <tr key={company.key} onClick={() => onOpenCompany(company)}><td><strong>{company.name}</strong><small>{[...company.sources].map(sourceLabel).slice(0, 2).join(' · ')}</small></td><td>{company.propertyIds.size}</td><td>{company.confirmedPropertyIds.size}</td><td>{company.highAttentionPropertyIds.size}</td><td><div className="toronto-chip-list">{[...company.roles].slice(0, 4).map(role => <span key={role}>{humanize(role)}</span>)}</div></td><td>{property ? <button className="toronto-address-button" onClick={event => { event.stopPropagation(); onOpenProperty(property) }}>{property.display_address}</button> : '—'}</td><td><button className="table-link" onClick={event => { event.stopPropagation(); onOpenCompany(company) }}>Open {portfolio ? 'portfolio' : 'company'} →</button></td></tr>
  })}</tbody></table>{rows.length > 500 && <p className="toronto-table-limit">Showing the first 500 organizations.</p>}</div>
}

function PropertyProfile({ row, payload, companies, watched, onBack, onOpenMarket, onOpenCompany, onToggleWatch, onCopyLead }: { row: ProspectRow; payload: TorontoMarketPayload; companies: Map<string, CompanyRow>; watched: boolean; onBack: () => void; onOpenMarket: () => void; onOpenCompany: (company: CompanyRow) => void; onToggleWatch: () => void; onCopyLead: () => void }) {
  return <section className="product-page toronto-page toronto-parity-page toronto-drillthrough-page">
    <div className="account-profile-toolbar"><div><button className="breadcrumb-back" onClick={onBack}>← Back</button><span>Toronto property profile</span></div><div className="page-actions"><button onClick={onCopyLead}>Copy lead</button><button onClick={onOpenMarket}>Open market evidence</button><button onClick={onToggleWatch}>{watched ? 'Watching' : 'Watch'}</button></div></div>
    <div className="product-page-heading"><div><span className="page-kicker">Toronto · source-backed account</span><h1>{row.property.display_address}</h1><p>{row.property.property_id} · Address Point {row.property.address_point_id}. Commercial attention is a workflow ranking only; verify current equipment, relationship and operating status before outreach.</p></div><div className="company-identity-card"><span className={`toronto-attention-badge tier-${row.tier.toLowerCase()}`}>{row.attention} · {row.tier}</span><small>Commercial attention</small><strong>{humanize(row.property.tower_evidence_status)}</strong></div></div>
    <div className="reference-metric-grid"><article><span className="reference-metric-icon">▤</span><div><small>Source records</small><strong>{row.property.source_links.length}</strong><span>{row.property.source_keys.length} source families</span></div></article><article><span className="reference-metric-icon success">↔</span><div><small>Relationships</small><strong>{row.property.relationships.length}</strong><span>Explicit source roles only</span></div></article><article><span className="reference-metric-icon urgent">↗</span><div><small>Opportunity signals</small><strong>{row.opportunities.length}</strong><span>{row.factors.length} ranking factors</span></div></article></div>
    <div className="company-profile-grid">
      <section className="reference-table-card company-evidence-card"><div className="reference-table-heading"><div><strong>Why now</strong><span>Commercial workflow context</span></div></div><div className="toronto-chip-list">{row.factors.map(value => <span key={value}>{value}</span>)}</div><div className="evidence-list"><strong>Opportunity queues</strong>{row.opportunities.map(value => <div key={value}><span>{value}</span></div>)}</div></section>
      <section className="reference-table-card company-evidence-card"><div className="reference-table-heading"><div><strong>Organizations &amp; roles</strong><span>Cross-link to company profiles</span></div></div><div className="evidence-list">{row.property.relationships.length ? row.property.relationships.map((relationship, index) => {
        const company = companies.get(normalizeOrganization(relationship.organization))
        return <button className="toronto-drill-link" key={`${relationship.organization}:${relationship.relationship}:${index}`} onClick={() => company && onOpenCompany(company)} disabled={!company}><strong>{relationship.organization}</strong><span>{humanize(relationship.relationship)} · {sourceLabel(relationship.source_key)}</span></button>
      }) : <div><span>No defensible organization relationship is currently attached.</span></div>}</div></section>
    </div>
    <div className="reference-table-card"><div className="reference-table-heading"><div><strong>Source evidence</strong><span>{row.property.source_links.length} property-linked records</span></div></div><div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Source</th><th>Record</th><th>Status / date</th><th>Identity</th><th>Evidence</th></tr></thead><tbody>{row.property.source_links.map(link => {
      const catalog = payload.source_catalog[link.source_key]
      const href = link.record_url || catalog?.dataset_url
      return <tr key={`${link.source_key}:${link.source_record_id}`}><td><strong>{sourceLabel(link.source_key)}</strong></td><td><strong>{link.record_title || link.source_record_id}</strong><small>{link.source_record_id}</small></td><td>{[link.record_status, link.record_date].filter(Boolean).join(' · ') || '—'}</td><td>{humanize(link.match_basis)}<small>{link.source_address || 'canonical property spine'}</small></td><td>{href ? <a className="table-link" href={href} target="_blank" rel="noreferrer">Open source ↗</a> : '—'}<small>{link.record_url ? 'record-level link' : catalog?.dataset_url ? 'dataset fallback' : 'no durable source action'}</small></td></tr>
    })}</tbody></table></div></div>
  </section>
}

function OrganizationProfile({ company, propertiesById, prospects, portfolio, onBack, onOpenProperty, onOpenOtherProfile }: { company: CompanyRow; propertiesById: Map<string, TorontoProperty>; prospects: Map<string, ProspectRow>; portfolio: boolean; onBack: () => void; onOpenProperty: (property: TorontoProperty) => void; onOpenOtherProfile: () => void }) {
  const linked = [...company.propertyIds].map(id => propertiesById.get(id)).filter((property): property is TorontoProperty => Boolean(property)).sort((left, right) => (prospects.get(right.property_id)?.attention ?? 0) - (prospects.get(left.property_id)?.attention ?? 0))
  return <section className="product-page toronto-page toronto-parity-page toronto-drillthrough-page">
    <div className="account-profile-toolbar"><div><button className="breadcrumb-back" onClick={onBack}>← Back to {portfolio ? 'Portfolios' : 'Companies'}</button><span>Toronto {portfolio ? 'portfolio' : 'company'} profile</span></div><div className="page-actions">{company.propertyIds.size >= 2 && <button onClick={onOpenOtherProfile}>Open {portfolio ? 'company' : 'portfolio'} view</button>}</div></div>
    <div className="product-page-heading"><div><span className="page-kicker">Toronto · source-backed organization</span><h1>{company.name}</h1><p>Organization grouping is based on observed public-record labels and explicit relationship roles. TowerSignal does not infer corporate parentage or ownership beyond cited source evidence.</p></div></div>
    <div className="reference-metric-grid"><article><span className="reference-metric-icon">⌂</span><div><small>Linked properties</small><strong>{company.propertyIds.size}</strong><span>{company.confirmedPropertyIds.size} documentary-confirmed towers</span></div></article><article><span className="reference-metric-icon urgent">↗</span><div><small>High-attention properties</small><strong>{company.highAttentionPropertyIds.size}</strong><span>Commercial rank 65+</span></div></article><article><span className="reference-metric-icon">↔</span><div><small>Observed roles</small><strong>{company.roles.size}</strong><span>{company.sources.size} source families</span></div></article></div>
    <div className="company-profile-grid"><section className="reference-table-card company-evidence-card"><div className="reference-table-heading"><div><strong>Observed roles</strong><span>Explicit source roles only</span></div></div><div className="toronto-chip-list">{[...company.roles].map(role => <span key={role}>{humanize(role)}</span>)}</div></section><section className="reference-table-card company-evidence-card"><div className="reference-table-heading"><div><strong>Source provenance</strong><span>Organization relationship sources</span></div></div><div className="evidence-list">{[...company.sources].map(source => <div key={source}><span>{sourceLabel(source)}</span></div>)}</div></section></div>
    <div className="reference-table-card"><div className="reference-table-heading"><div><strong>Linked Toronto properties</strong><span>Drill through to property profiles</span></div></div><div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Property</th><th>Attention</th><th>Tower evidence</th><th>Sources</th><th>Action</th></tr></thead><tbody>{linked.map(property => {
      const prospect = prospects.get(property.property_id)
      return <tr key={property.property_id} onClick={() => onOpenProperty(property)}><td><strong>{property.display_address}</strong><small>{property.property_id}</small></td><td>{prospect?.attention ?? 0}<small>commercial rank</small></td><td>{humanize(property.tower_evidence_status)}</td><td>{property.source_keys.length}</td><td><button className="table-link" onClick={event => { event.stopPropagation(); onOpenProperty(property) }}>Open profile →</button></td></tr>
    })}</tbody></table></div></div>
  </section>
}

export function TorontoUnifiedWorkspace({ explorer, mapExplorer }: { explorer: ReactNode; mapExplorer: ReactNode }) {
  const initialRoute = parseTorontoRoute()
  const [route, setRoute] = useState<TorontoRoute>(initialRoute)
  const [payload, setPayload] = useState<TorontoMarketPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState(initialRoute.search)
  const [opportunityFilter, setOpportunityFilter] = useState('all')
  const [companyRole, setCompanyRole] = useState('')
  const [copyFeedback, setCopyFeedback] = useState('')
  const [watchedIds, setWatchedIds] = useState<Set<string>>(() => {
    try {
      const parsed = JSON.parse(localStorage.getItem(WATCHLIST_KEY) ?? '[]')
      return new Set(Array.isArray(parsed) ? parsed.filter(value => typeof value === 'string') : [])
    } catch {
      return new Set<string>()
    }
  })

  useEffect(() => {
    const sync = () => {
      const next = parseTorontoRoute()
      setRoute(next)
      if (next.search) setSearch(next.search)
    }
    sync()
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])

  useEffect(() => {
    if (route.view === 'market' || route.view === 'map' || route.view === 'benchmarking' || payload || error) return
    loadTorontoMarket().then(setPayload).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load Toronto market data'))
  }, [route.view, payload, error])

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
  const companiesByKey = useMemo(() => new Map(companies.map(company => [company.key, company])), [companies])
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

  const navigate = (view: TorontoView, id?: string | null) => { window.location.hash = routeHash(view, id) }
  const openProperty = (property: TorontoProperty, from: TorontoView = route.view, fromId: string | null = route.id) => { window.location.hash = routeHash('property', property.property_id, from, fromId) }
  const openCompany = (company: CompanyRow, from: TorontoView = route.view, fromId: string | null = route.id) => { window.location.hash = routeHash('company', company.key, from, fromId) }
  const openPortfolio = (company: CompanyRow, from: TorontoView = route.view, fromId: string | null = route.id) => { window.location.hash = routeHash('portfolio', company.key, from, fromId) }
  const goBack = () => {
    if (route.from === 'company' && route.fromId) window.location.hash = routeHash('company', route.fromId)
    else if (route.from === 'portfolio' && route.fromId) window.location.hash = routeHash('portfolio', route.fromId)
    else if (route.from === 'property' && route.fromId) window.location.hash = routeHash('property', route.fromId)
    else window.location.hash = routeHash(route.from ?? (route.view === 'company' ? 'companies' : route.view === 'portfolio' ? 'portfolios' : 'prospect'))
  }
  const copyLead = async (row: ProspectRow) => {
    try { await copyText(buildTorontoLeadSummary(row)); setCopyFeedback(`Copied ${row.property.display_address}`) }
    catch { setCopyFeedback('Clipboard unavailable') }
    window.setTimeout(() => setCopyFeedback(''), 2200)
  }
  const exportProspects = (rows: ProspectRow[], filename: string) => downloadCsv(filename, buildTorontoProspectCsv(rows))
  const exportCompanies = (rows: CompanyRow[], filename: string) => downloadCsv(filename, buildTorontoCompanyCsv(rows))

  if (route.view === 'market') return <>{explorer}</>
  if (route.view === 'map') return <>{mapExplorer}</>
  if (route.view === 'benchmarking') return <TorontoBenchmarkingPage />
  if (error) return <section className="product-page toronto-page"><div className="reference-empty-state"><strong>Toronto workspace unavailable.</strong><span>{error}</span></div></section>
  if (!payload) return <section className="product-page toronto-page"><div className="portal-loading">Loading Toronto commercial intelligence…</div></section>

  const selectedProperty = route.id ? prospectById.get(route.id) ?? null : null
  const selectedCompany = route.id ? companiesByKey.get(normalizeOrganization(route.id)) ?? companiesByKey.get(route.id) ?? null : null

  if (route.view === 'property') return selectedProperty ? <PropertyProfile row={selectedProperty} payload={payload} companies={companiesByKey} watched={watchedIds.has(selectedProperty.property.property_id)} onBack={goBack} onOpenMarket={() => { window.location.hash = `#/toronto/market/${encodeURIComponent(selectedProperty.property.property_id)}` }} onOpenCompany={company => openCompany(company, 'property', selectedProperty.property.property_id)} onToggleWatch={() => toggleWatch(selectedProperty.property.property_id)} onCopyLead={() => copyLead(selectedProperty)} /> : <section className="product-page toronto-page"><div className="account-profile-toolbar"><button className="breadcrumb-back" onClick={goBack}>← Back</button></div><div className="reference-empty-state"><strong>Toronto property profile not found.</strong><span>The property may no longer be present in the current canonical snapshot.</span></div></section>
  if (route.view === 'company') return selectedCompany ? <OrganizationProfile company={selectedCompany} propertiesById={propertiesById} prospects={prospectById} portfolio={false} onBack={goBack} onOpenProperty={property => openProperty(property, 'company', selectedCompany.key)} onOpenOtherProfile={() => openPortfolio(selectedCompany, route.from ?? 'companies', route.fromId)} /> : <section className="product-page toronto-page"><div className="account-profile-toolbar"><button className="breadcrumb-back" onClick={goBack}>← Back to Companies</button></div><div className="reference-empty-state"><strong>Toronto company profile not found.</strong></div></section>
  if (route.view === 'portfolio') return selectedCompany ? <OrganizationProfile company={selectedCompany} propertiesById={propertiesById} prospects={prospectById} portfolio onBack={goBack} onOpenProperty={property => openProperty(property, 'portfolio', selectedCompany.key)} onOpenOtherProfile={() => openCompany(selectedCompany, route.from ?? 'portfolios', route.fromId)} /> : <section className="product-page toronto-page"><div className="account-profile-toolbar"><button className="breadcrumb-back" onClick={goBack}>← Back to Portfolios</button></div><div className="reference-empty-state"><strong>Toronto portfolio profile not found.</strong></div></section>

  if (route.view === 'home') return <section className="product-page toronto-page toronto-parity-page toronto-home-page"><div className="product-page-heading"><div><span className="page-kicker">Toronto · commercial intelligence</span><h1>TowerSignal Toronto</h1><p>Use the same workspace flow as New York with Toronto-native source contracts: find prospects, review timing, drill into accounts and companies, work portfolios, and verify evidence before outreach.</p></div></div><div className="reference-metric-grid toronto-parity-metrics"><article><span className="reference-metric-icon">⌂</span><div><small>Canonical properties</small><strong>{payload.counts.canonical_properties.toLocaleString()}</strong><span>Municipal Address Point spine</span></div></article><article><span className="reference-metric-icon success">◎</span><div><small>Confirmed towers</small><strong>{payload.counts.documentary_confirmed_properties.toLocaleString()}</strong><span>Documentary evidence only</span></div></article><article><span className="reference-metric-icon urgent">↗</span><div><small>High attention</small><strong>{prospects.filter(row => row.attention >= 65).length.toLocaleString()}</strong><span>Commercial rank 65+</span></div></article><article><span className="reference-metric-icon">↔</span><div><small>Organizations</small><strong>{companies.length.toLocaleString()}</strong><span>Source-backed relationship graph</span></div></article></div><div className="toronto-home-actions"><button onClick={() => navigate('prospect')}><strong>Prospect</strong><span>Rank and filter Toronto accounts →</span></button><button onClick={() => navigate('opportunities')}><strong>Opportunities</strong><span>Review project and mechanical timing →</span></button><button onClick={() => navigate('companies')}><strong>Companies</strong><span>Drill through organization relationships →</span></button><button onClick={() => navigate('portfolios')}><strong>Portfolios</strong><span>Work multi-property organizations →</span></button><button onClick={() => navigate('market')}><strong>Toronto Market</strong><span>Full evidence table and map →</span></button><button onClick={() => navigate('benchmarking')}><strong>Benchmarking</strong><span>Ontario EWRB aggregate market context →</span></button><button onClick={() => navigate('source-health')}><strong>Source Health</strong><span>Inspect deterministic coverage and limitations →</span></button><button onClick={() => navigate('workflow')}><strong>Workflow</strong><span>Review browser-local watched accounts →</span></button></div></section>

  if (route.view === 'prospect') return <section className="product-page toronto-page toronto-parity-page"><div className="product-page-heading"><div><span className="page-kicker">Toronto · commercial intelligence</span><h1>Prospect workspace</h1><p>Rank source-backed Toronto properties for commercial attention using documentary tower evidence, project timing, joined source depth and identified organizations. This attention index is not a regulatory or compliance score.</p></div></div><div className="reference-metric-grid toronto-parity-metrics"><article><span className="reference-metric-icon urgent">↗</span><div><small>High attention</small><strong>{prospects.filter(row => row.attention >= 65).length.toLocaleString()}</strong><span>Commercial rank 65+</span></div></article><article><span className="reference-metric-icon success">◎</span><div><small>Confirmed towers</small><strong>{payload.counts.documentary_confirmed_properties.toLocaleString()}</strong><span>Documentary evidence only</span></div></article><article><span className="reference-metric-icon warning">⌁</span><div><small>Mechanical permit signals</small><strong>{prospects.filter(row => hasMechanicalPermit(row.property)).length.toLocaleString()}</strong><span>Permit text signal</span></div></article><article><span className="reference-metric-icon">↔</span><div><small>Relationship-ready</small><strong>{prospects.filter(row => row.property.relationships.length > 0).length.toLocaleString()}</strong><span>At least one source-backed role</span></div></article></div><div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search address, company, source or signal" /><div className="toronto-parity-toolbar-actions"><button onClick={() => exportProspects(filteredProspects, 'towersignal-toronto-prospects.csv')}>Export CSV</button>{copyFeedback && <small role="status">{copyFeedback}</small>}</div><strong>{highProspects.length.toLocaleString()} high-attention matches</strong></div><ProspectTable rows={filteredProspects} watchedIds={watchedIds} onOpen={row => openProperty(row.property, 'prospect')} onCopyLead={copyLead} onToggleWatch={toggleWatch} /></section>

  if (route.view === 'monitor') return <section className="product-page toronto-page toronto-parity-page"><div className="product-page-heading"><div><span className="page-kicker">Toronto · monitored accounts</span><h1>Monitor workspace</h1><p>Review watched Toronto accounts in the same workflow position as New York Monitor. Toronto does not yet publish a validated snapshot-to-snapshot event stream, so this page does not fabricate change events.</p></div></div><div className="toronto-limit-banner"><strong>Historical change feed not yet available.</strong><span>Watched accounts remain useful for repeat review; changes will only appear here after a Toronto event stream passes the evidence contract.</span></div>{watchRows.length ? <ProspectTable rows={watchRows} watchedIds={watchedIds} onOpen={row => openProperty(row.property, 'monitor')} onCopyLead={copyLead} onToggleWatch={toggleWatch} /> : <div className="reference-empty-state"><strong>No Toronto accounts are monitored yet.</strong><span>Add accounts from Prospect or Opportunities.</span><button onClick={() => navigate('prospect')}>Open Prospect workspace</button></div>}</section>

  if (route.view === 'changes') return <section className="product-page toronto-page toronto-parity-page"><div className="product-page-heading"><div><span className="page-kicker">Toronto · historical intelligence</span><h1>Toronto Changes</h1><p>This page occupies the same navigation position as NYS Changes, but it remains evidence-limited until Toronto snapshots are persisted and compared under a validated event contract.</p></div></div><div className="reference-empty-state"><strong>No fabricated Toronto change events.</strong><span>Current-source observations, permits, relationships and documentary evidence remain available in Toronto Market and Source Health. A record being present today is not itself a change event.</span><div className="page-actions"><button onClick={() => navigate('market')}>Open Toronto Market</button><button onClick={() => navigate('source-health')}>Open Source Health</button></div></div></section>

  if (route.view === 'opportunities') return <section className="product-page toronto-page toronto-parity-page"><div className="product-page-heading"><div><span className="page-kicker">Toronto · why now</span><h1>Opportunities workspace</h1><p>Surface defensible timing and research queues from Toronto-specific public evidence. Drill through any property to its source-backed profile.</p></div></div><div className="toronto-opportunity-cards"><button onClick={() => setOpportunityFilter('confirmed-permit')}><small>Confirmed + mechanical permit</small><strong>{prospects.filter(row => row.opportunities.includes('Confirmed tower + mechanical project timing')).length.toLocaleString()}</strong></button><button onClick={() => setOpportunityFilter('mechanical')}><small>Mechanical permit activity</small><strong>{prospects.filter(row => row.opportunities.includes('Mechanical / cooling-system permit activity')).length.toLocaleString()}</strong></button><button onClick={() => setOpportunityFilter('relationship-gap')}><small>Confirmed relationship gaps</small><strong>{prospects.filter(row => row.opportunities.includes('Relationship research gap')).length.toLocaleString()}</strong></button><button onClick={() => setOpportunityFilter('multi-source')}><small>Multi-source context</small><strong>{prospects.filter(row => row.opportunities.includes('Multi-source account context')).length.toLocaleString()}</strong></button><button onClick={() => setOpportunityFilter('planning')}><small>Planning / development</small><strong>{prospects.filter(row => row.opportunities.includes('Planning or development activity')).length.toLocaleString()}</strong></button></div><div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search opportunity accounts" /><select value={opportunityFilter} onChange={event => setOpportunityFilter(event.target.value)}><option value="all">All opportunity signals</option><option value="confirmed-permit">Confirmed tower + mechanical permit</option><option value="mechanical">Mechanical / cooling-system permit</option><option value="planning">Planning / development</option><option value="relationship-gap">Relationship research gap</option><option value="multi-source">Multi-source context</option><option value="environment">Environmental / health context</option></select><div className="toronto-parity-toolbar-actions"><button onClick={() => exportProspects(opportunityRows, 'towersignal-toronto-opportunities.csv')}>Export CSV</button>{copyFeedback && <small role="status">{copyFeedback}</small>}</div><strong>{opportunityRows.length.toLocaleString()} matches</strong></div><div className="toronto-opportunity-list">{opportunityRows.slice(0, 300).map(row => <article key={row.property.property_id}><div><span className={`toronto-attention-badge tier-${row.tier.toLowerCase()}`}>{row.attention}</span><button className="toronto-address-button" onClick={() => openProperty(row.property, 'opportunities')}>{row.property.display_address}</button><small>{row.property.source_keys.length} source families · {row.property.relationships.length} relationships</small></div><div className="toronto-chip-list">{row.opportunities.map(value => <span key={value}>{value}</span>)}</div><PropertyActions row={row} watched={watchedIds.has(row.property.property_id)} onOpen={() => openProperty(row.property, 'opportunities')} onCopyLead={() => copyLead(row)} onToggleWatch={() => toggleWatch(row.property.property_id)} /></article>)}</div></section>

  if (route.view === 'companies') return <section className="product-page toronto-page toronto-parity-page"><div className="product-page-heading"><div><span className="page-kicker">Toronto · relationship graph</span><h1>Companies</h1><p>Explore source-backed organizations and drill through to organization profiles, linked properties and underlying source evidence.</p></div></div><div className="reference-metric-grid toronto-parity-metrics"><article><span className="reference-metric-icon">↔</span><div><small>Organizations</small><strong>{companies.length.toLocaleString()}</strong><span>Normalized observed labels</span></div></article><article><span className="reference-metric-icon success">⌂</span><div><small>Multi-property</small><strong>{companies.filter(company => company.propertyIds.size >= 2).length.toLocaleString()}</strong><span>2+ linked properties</span></div></article><article><span className="reference-metric-icon urgent">◎</span><div><small>Linked confirmed towers</small><strong>{companies.filter(company => company.confirmedPropertyIds.size > 0).length.toLocaleString()}</strong><span>Organizations touching confirmed properties</span></div></article></div><div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search organization or role" /><select value={companyRole} onChange={event => setCompanyRole(event.target.value)}><option value="">All relationship roles</option>{roles.map(role => <option key={role} value={role}>{humanize(role)}</option>)}</select><div className="toronto-parity-toolbar-actions"><button onClick={() => exportCompanies(filteredCompanies, 'towersignal-toronto-companies.csv')}>Export CSV</button></div><strong>{filteredCompanies.length.toLocaleString()} organizations</strong></div><CompanyTable rows={filteredCompanies} propertiesById={propertiesById} onOpenCompany={company => openCompany(company, 'companies')} onOpenProperty={property => openProperty(property, 'companies')} /></section>

  if (route.view === 'portfolios') return <section className="product-page toronto-page toronto-parity-page"><div className="product-page-heading"><div><span className="page-kicker">Toronto · account groups</span><h1>Portfolios</h1><p>Group multi-property organizations from defensible relationship edges and drill through to their linked Toronto properties.</p></div></div><div className="reference-metric-grid toronto-parity-metrics"><article><span className="reference-metric-icon success">⌂</span><div><small>Multi-property portfolios</small><strong>{portfolioCompanies.length.toLocaleString()}</strong><span>2+ properties, portfolio-capable role</span></div></article><article><span className="reference-metric-icon urgent">◎</span><div><small>Portfolios with confirmed towers</small><strong>{portfolioCompanies.filter(company => company.confirmedPropertyIds.size > 0).length.toLocaleString()}</strong><span>Documentary-confirmed property link</span></div></article><article><span className="reference-metric-icon">↗</span><div><small>High-attention portfolios</small><strong>{portfolioCompanies.filter(company => company.highAttentionPropertyIds.size > 0).length.toLocaleString()}</strong><span>At least one 65+ account</span></div></article></div><div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search portfolio organization" /><select value={companyRole} onChange={event => setCompanyRole(event.target.value)}><option value="">All portfolio roles</option>{roles.filter(role => portfolioRoles.has(role)).map(role => <option key={role} value={role}>{humanize(role)}</option>)}</select><div className="toronto-parity-toolbar-actions"><button onClick={() => exportCompanies(portfolioCompanies, 'towersignal-toronto-portfolios.csv')}>Export CSV</button></div><strong>{portfolioCompanies.length.toLocaleString()} portfolios</strong></div><CompanyTable rows={portfolioCompanies} propertiesById={propertiesById} onOpenCompany={company => openPortfolio(company, 'portfolios')} onOpenProperty={property => openProperty(property, 'portfolios')} portfolio /></section>

  if (route.view === 'workflow') return <section className="product-page toronto-page toronto-parity-page"><div className="product-page-heading"><div><span className="page-kicker">Toronto · workflow</span><h1>Workflow workspace</h1><p>Work watched Toronto accounts in the same navigation position as New York Workflow. This preview stores watch state in this browser and does not activate the shared NY workflow backend.</p></div></div>{watchRows.length ? <><div className="toronto-parity-toolbar toronto-watchlist-toolbar"><div className="toronto-parity-toolbar-actions"><button onClick={() => exportProspects(watchRows, 'towersignal-toronto-workflow.csv')}>Export workflow CSV</button>{copyFeedback && <small role="status">{copyFeedback}</small>}</div><strong>{watchRows.length.toLocaleString()} watched properties</strong></div><ProspectTable rows={watchRows} watchedIds={watchedIds} onOpen={row => openProperty(row.property, 'workflow')} onCopyLead={copyLead} onToggleWatch={toggleWatch} /></> : <div className="reference-empty-state"><strong>No Toronto properties are in workflow yet.</strong><span>Add properties from Prospect or Opportunities.</span><button onClick={() => navigate('prospect')}>Open Prospect workspace</button></div>}</section>

  if (route.view === 'source-health') return <section className="product-page toronto-page toronto-parity-page"><div className="product-page-heading"><div><span className="page-kicker">Toronto · evidence operations</span><h1>Source health & coverage</h1><p>Inspect source-level record counts, deterministic match results and known identity limitations before relying on a prospect or portfolio conclusion.</p></div></div><div className="reference-metric-grid toronto-parity-metrics"><article><span className="reference-metric-icon success">✓</span><div><small>Official source families</small><strong>{payload.counts.official_source_families.toLocaleString()}</strong><span>Published in current app payload</span></div></article><article><span className="reference-metric-icon">↔</span><div><small>Source links</small><strong>{payload.counts.source_links.toLocaleString()}</strong><span>Property-to-source links</span></div></article><article><span className="reference-metric-icon">⌁</span><div><small>Record-level links</small><strong>{payload.counts.record_level_source_links.toLocaleString()}</strong><span>Durable row-level where available</span></div></article></div><div className="toronto-table-wrap"><table className="toronto-table toronto-source-health-table"><thead><tr><th>Source</th><th>Status</th><th>Records</th><th>Matched</th><th>Properties</th><th>Match rate</th><th>Limitation</th><th>Official</th></tr></thead><tbody>{Object.entries(payload.source_coverage).filter(([, summary]) => summary.source_records != null || summary.matched_records != null).sort(([, left], [, right]) => (right.matched_canonical_properties ?? 0) - (left.matched_canonical_properties ?? 0)).map(([key, summary]) => {
    const rate = summary.source_records && summary.matched_records != null ? `${Math.round(summary.matched_records / summary.source_records * 100)}%` : '—'
    return <tr key={key}><td><strong>{sourceLabel(key)}</strong></td><td>{summary.status ? humanize(summary.status) : '—'}</td><td>{summary.source_records?.toLocaleString() ?? '—'}</td><td>{summary.matched_records?.toLocaleString() ?? '—'}</td><td>{summary.matched_canonical_properties?.toLocaleString() ?? '—'}</td><td>{rate}</td><td><small>{summary.identity_limitation || summary.scope_limitation || 'Deterministic join contract'}</small></td><td>{payload.source_catalog[key]?.dataset_url ? <a href={payload.source_catalog[key].dataset_url} target="_blank" rel="noreferrer">Open ↗</a> : '—'}</td></tr>
  })}</tbody></table></div><section className="toronto-parity-limitations"><h2>Known limitations</h2><ul>{payload.limitations.map(item => <li key={item}>{item}</li>)}</ul></section></section>

  return <section className="product-page toronto-page"><div className="reference-empty-state"><strong>{viewLabel(route.view)} is unavailable.</strong><span>The route is recognized but no Toronto surface is currently rendered.</span></div></section>
}
