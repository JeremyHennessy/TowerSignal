import { useMemo, useState } from 'react'
import type { SystemSummary, SystemsPayload } from '../types/data'
import type { AcrisSummaryFields } from '../types/acris'
import { ShareButton } from './ShareButton'

type OwnerGroup = {
  key: string
  name: string
  rows: SystemSummary[]
  towers: number
  buildingAreaSqft: number
  highPriority: number
  contactReady: number
}

type SortDirection = 'asc' | 'desc'
type PropertySortKey = 'address' | 'borough' | 'priority' | 'towers' | 'area' | 'contacts'
type CandidateSortKey = 'address' | 'owner' | 'borough' | 'towers' | 'priority' | 'contacts'

const number = new Intl.NumberFormat('en-US')
const PAGE_SIZE = 30
const PLACEHOLDER_OWNER_NAMES = new Set([
  'UNAVAILABLE OWNER',
  'OWNER UNAVAILABLE',
  'NAME NOT ON FILE',
  'NOT AVAILABLE',
  'UNKNOWN',
  'N/A',
  'NA',
  'NONE',
])

function normalizedOwnerName(value: string | null | undefined): { key: string; name: string } | null {
  const name = value?.trim().replace(/\s+/g, ' ')
  if (!name) return null
  const key = name.toLocaleUpperCase('en-US')
  if (PLACEHOLDER_OWNER_NAMES.has(key)) return null
  return { key, name }
}

function ownerGroups(rows: SystemSummary[]): OwnerGroup[] {
  const groups = new Map<string, OwnerGroup>()
  rows.forEach(row => {
    const owner = normalizedOwnerName(row.pluto_owner_name)
    if (!owner) return
    const current = groups.get(owner.key) ?? { key: owner.key, name: owner.name, rows: [], towers: 0, buildingAreaSqft: 0, highPriority: 0, contactReady: 0 }
    current.rows.push(row)
    current.towers += row.active_equipment
    current.buildingAreaSqft += row.pluto_building_area_sqft ?? 0
    current.highPriority += row.priority_score >= 70 ? 1 : 0
    current.contactReady += (row.hpd_contact_count ?? 0) > 0 ? 1 : 0
    groups.set(owner.key, current)
  })
  return [...groups.values()].filter(group => group.rows.length > 1).sort((a, b) => b.rows.length - a.rows.length || b.towers - a.towers)
}

function ownerKeyFromHash(): string | null {
  const query = window.location.hash.split('?')[1]
  if (!query) return null
  return new URLSearchParams(query).get('owner')
}

function compareValues(left: unknown, right: unknown): number {
  if (typeof left === 'number' && typeof right === 'number') return left - right
  return String(left ?? '').localeCompare(String(right ?? ''), undefined, { numeric: true, sensitivity: 'base' })
}

function PageControls({ page, total, onPage }: { page: number; total: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  if (pages <= 1) return null
  const safe = Math.min(page, pages)
  return <div className="reference-pagination"><span>Page {safe} of {pages}</span><div><button disabled={safe <= 1} onClick={() => onPage(safe - 1)}>Previous</button><button disabled={safe >= pages} onClick={() => onPage(safe + 1)}>Next</button></div></div>
}

export function PortfoliosPage({ payload, watchedSystemIds, onOpenAccount }: { payload: SystemsPayload; watchedSystemIds: Set<string>; onOpenAccount: (row: SystemSummary) => void }) {
  const rows = payload.systems
  const groups = ownerGroups(rows)
  const [selectedKey, setSelectedKey] = useState<string | null>(ownerKeyFromHash)
  const [propertySearch, setPropertySearch] = useState('')
  const [propertySort, setPropertySort] = useState<{ key: PropertySortKey; direction: SortDirection }>({ key: 'priority', direction: 'desc' })
  const [propertyPage, setPropertyPage] = useState(1)
  const [candidateSearch, setCandidateSearch] = useState('')
  const [candidateMinTowers, setCandidateMinTowers] = useState('1')
  const [candidateSort, setCandidateSort] = useState<{ key: CandidateSortKey; direction: SortDirection }>({ key: 'towers', direction: 'desc' })
  const [candidatePage, setCandidatePage] = useState(1)

  const plutoContext = rows.filter(row => row.pluto_match).length
  const contactReady = rows.filter(row => (row.hpd_contact_count ?? 0) > 0).length
  const acrisContext = rows.filter(row => ((row as SystemSummary & AcrisSummaryFields).acris_recent_document_count ?? 0) > 0).length
  const selectedGroup = groups.find(group => group.key === selectedKey) ?? groups[0]

  const selectedRows = useMemo(() => {
    const query = propertySearch.trim().toLowerCase()
    const source = selectedGroup?.rows ?? []
    return source.filter(row => !query || [row.address, row.borough, row.zip, row.system_id, row.bbl].filter(Boolean).join(' ').toLowerCase().includes(query))
  }, [selectedGroup, propertySearch])
  const sortedSelectedRows = useMemo(() => [...selectedRows].sort((a, b) => {
    const value = (row: SystemSummary): unknown => {
      if (propertySort.key === 'address') return row.address ?? row.system_id
      if (propertySort.key === 'borough') return row.borough
      if (propertySort.key === 'priority') return row.priority_score
      if (propertySort.key === 'towers') return row.active_equipment
      if (propertySort.key === 'area') return row.pluto_building_area_sqft ?? 0
      return row.hpd_contact_count ?? 0
    }
    const result = compareValues(value(a), value(b)) || compareValues(a.address, b.address)
    return propertySort.direction === 'asc' ? result : -result
  }), [selectedRows, propertySort])
  const propertyPageCount = Math.max(1, Math.ceil(sortedSelectedRows.length / PAGE_SIZE))
  const safePropertyPage = Math.min(propertyPage, propertyPageCount)
  const visibleSelectedRows = sortedSelectedRows.slice((safePropertyPage - 1) * PAGE_SIZE, safePropertyPage * PAGE_SIZE)

  const candidateRows = useMemo(() => {
    const query = candidateSearch.trim().toLowerCase()
    const minTowers = Number(candidateMinTowers)
    return rows.filter(row => {
      const owner = normalizedOwnerName(row.pluto_owner_name)
      if (!row.pluto_match || !owner) return false
      if (row.active_equipment < minTowers) return false
      if (query && ![row.address, row.pluto_owner_name, row.borough, row.zip, row.system_id, row.bbl].filter(Boolean).join(' ').toLowerCase().includes(query)) return false
      return true
    })
  }, [rows, candidateSearch, candidateMinTowers])
  const sortedCandidates = useMemo(() => [...candidateRows].sort((a, b) => {
    const value = (row: SystemSummary): unknown => {
      if (candidateSort.key === 'address') return row.address ?? row.system_id
      if (candidateSort.key === 'owner') return row.pluto_owner_name
      if (candidateSort.key === 'borough') return row.borough
      if (candidateSort.key === 'towers') return row.active_equipment
      if (candidateSort.key === 'priority') return row.priority_score
      return row.hpd_contact_count ?? 0
    }
    const result = compareValues(value(a), value(b)) || compareValues(a.address, b.address)
    return candidateSort.direction === 'asc' ? result : -result
  }), [candidateRows, candidateSort])
  const candidatePageCount = Math.max(1, Math.ceil(sortedCandidates.length / PAGE_SIZE))
  const safeCandidatePage = Math.min(candidatePage, candidatePageCount)
  const visibleCandidates = sortedCandidates.slice((safeCandidatePage - 1) * PAGE_SIZE, safeCandidatePage * PAGE_SIZE)

  const selectGroup = (group: OwnerGroup) => {
    setSelectedKey(group.key)
    setPropertyPage(1)
    setPropertySearch('')
    window.location.hash = `#/portfolios?owner=${encodeURIComponent(group.key)}`
  }
  const changePropertySort = (key: PropertySortKey) => {
    setPropertySort(current => current.key === key ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' } : { key, direction: key === 'address' || key === 'borough' ? 'asc' : 'desc' })
    setPropertyPage(1)
  }
  const changeCandidateSort = (key: CandidateSortKey) => {
    setCandidateSort(current => current.key === key ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' } : { key, direction: key === 'address' || key === 'owner' || key === 'borough' ? 'asc' : 'desc' })
    setCandidatePage(1)
  }
  const propertyIndicator = (key: PropertySortKey) => propertySort.key === key ? (propertySort.direction === 'asc' ? ' ↑' : ' ↓') : ''
  const candidateIndicator = (key: CandidateSortKey) => candidateSort.key === key ? (candidateSort.direction === 'asc' ? ' ↑' : ' ↓') : ''

  return <section className="product-page portfolios-page">
    <div className="product-page-heading">
      <div><span className="page-kicker">New York City · ownership context</span><h1>Portfolios</h1><p>Group properties by exact PLUTO owner-name context, then evaluate timing, contact readiness and account scale without implying a corporate parent relationship.</p></div>
      <div className="page-actions"><ShareButton label="Share this portfolio view" /></div>
    </div>

    <div className="reference-metric-grid">
      <article><span className="reference-metric-icon success">⌂</span><div><small>PLUTO context</small><strong>{number.format(plutoContext)}</strong><span>Exact-BBL property matches</span></div></article>
      <article><span className="reference-metric-icon">◎</span><div><small>Owner groups indexed</small><strong>{number.format(groups.length)}</strong><span>{groups.length > 0 ? 'Repeated exact normalized owner names' : 'No repeated exact owner names in this snapshot'}</span></div></article>
      <article><span className="reference-metric-icon success">◉</span><div><small>Contact-ready</small><strong>{number.format(contactReady)}</strong><span>HPD contact context</span></div></article>
      <article><span className="reference-metric-icon">⌁</span><div><small>ACRIS context</small><strong>{number.format(acrisContext)}</strong><span>Exact-BBL recent recorded activity</span></div></article>
      <article><span className="reference-metric-icon warning">★</span><div><small>Watched accounts</small><strong>{number.format(watchedSystemIds.size)}</strong><span>Private workflow membership</span></div></article>
    </div>

    {groups.length === 0 ? <div className="portfolio-readiness-layout">
      <div className="roadmap-data-banner portfolio-index-banner"><div><span className="roadmap-status">SOURCE-BACKED RESULT</span><strong>No repeated exact PLUTO owner names are present in the current normalized account snapshot.</strong><p>TowerSignal does not broaden or fuzzy-match owner names to manufacture portfolios. Individual exact-BBL PLUTO accounts remain available below for portfolio research.</p></div></div>
      <div className="portfolio-evidence-card"><span className="page-kicker">Portfolio evidence rule</span><h3>Grouping is context, not corporate-parent proof.</h3><p>Build 015 groups only identical PLUTO owner names after whitespace/case normalization. Placeholder owner values are excluded. HPD registration/contact and ACRIS party evidence should strengthen future confidence; similar names alone are not enough.</p><div className="evidence-pill-row"><span>PLUTO · exact BBL</span><span>HPD · exact registration</span><span>ACRIS · exact document</span></div></div>
    </div> : <div className="portfolio-layout">
      <aside className="portfolio-list"><div className="portfolio-list-heading"><span className="page-kicker">Ownership groups</span><strong>{groups.length} multi-property {groups.length === 1 ? 'group' : 'groups'}</strong></div>{groups.slice(0, 20).map(group => <article key={group.key} className={selectedGroup?.key === group.key ? 'active' : ''}><button className="portfolio-group-button" onClick={() => selectGroup(group)}><div><strong>{group.name}</strong><span>PLUTO owner-name context</span></div><dl><div><dt>Accounts</dt><dd>{group.rows.length}</dd></div><div><dt>Towers</dt><dd>{group.towers}</dd></div><div><dt>High priority</dt><dd>{group.highPriority}</dd></div></dl></button></article>)}</aside>
      {selectedGroup && <div className="portfolio-detail"><div className="portfolio-detail-heading"><div><span className="confidence-chip">CONTEXT · PLUTO OWNER NAME</span><h2>{selectedGroup.name}</h2><p>{selectedGroup.rows.length} cooling-tower accounts · {selectedGroup.towers} active equipment · {selectedGroup.contactReady} contact-ready{selectedGroup.buildingAreaSqft > 0 ? ` · ${number.format(Math.round(selectedGroup.buildingAreaSqft))} sq ft PLUTO building area` : ''}</p></div></div><div className="reference-table-card"><div className="reference-table-heading"><div><strong>Portfolio properties</strong><span>{number.format(sortedSelectedRows.length)} matching · {number.format(visibleSelectedRows.length)} shown</span></div><div className="page-actions"><input aria-label="Search portfolio properties" value={propertySearch} onChange={event => { setPropertySearch(event.target.value); setPropertyPage(1) }} placeholder="Address, borough, BBL…" /></div></div><div className="reference-table-scroll"><table className="reference-table"><thead><tr><th><button onClick={() => changePropertySort('address')}>Property{propertyIndicator('address')}</button></th><th><button onClick={() => changePropertySort('borough')}>Borough{propertyIndicator('borough')}</button></th><th><button onClick={() => changePropertySort('priority')}>Priority{propertyIndicator('priority')}</button></th><th><button onClick={() => changePropertySort('towers')}>Towers{propertyIndicator('towers')}</button></th><th><button onClick={() => changePropertySort('area')}>Building area{propertyIndicator('area')}</button></th><th><button onClick={() => changePropertySort('contacts')}>Contacts{propertyIndicator('contacts')}</button></th><th>Action</th></tr></thead><tbody>{visibleSelectedRows.map(row => <tr key={row.system_id} onClick={() => onOpenAccount(row)}><td><strong>{row.address ?? row.system_id}</strong><small>{row.bbl ? `BBL ${row.bbl}` : row.system_id}</small></td><td>{row.borough ?? '—'}</td><td>{row.priority_score}</td><td>{row.active_equipment}</td><td>{row.pluto_building_area_sqft ? `${number.format(Math.round(row.pluto_building_area_sqft))} sq ft` : '—'}</td><td>{row.hpd_contact_count ?? 0}</td><td><button className="table-link" onClick={event => { event.stopPropagation(); onOpenAccount(row) }}>Open →</button></td></tr>)}</tbody></table></div><PageControls page={safePropertyPage} total={sortedSelectedRows.length} onPage={setPropertyPage} /></div></div>}
    </div>}

    <div className="reference-table-card portfolio-candidates">
      <div className="reference-table-heading"><div><strong>Portfolio research candidates</strong><span>{number.format(sortedCandidates.length)} matching exact-PLUTO owner-context accounts · {number.format(visibleCandidates.length)} shown</span></div><div className="page-actions"><input aria-label="Search portfolio candidates" value={candidateSearch} onChange={event => { setCandidateSearch(event.target.value); setCandidatePage(1) }} placeholder="Account, owner, borough…" /><select aria-label="Minimum portfolio candidate towers" value={candidateMinTowers} onChange={event => { setCandidateMinTowers(event.target.value); setCandidatePage(1) }}><option value="1">1+ active units</option><option value="2">2+ active units</option><option value="3">3+ active units</option></select></div></div>
      <div className="reference-table-scroll"><table className="reference-table"><thead><tr><th><button onClick={() => changeCandidateSort('address')}>Account{candidateIndicator('address')}</button></th><th><button onClick={() => changeCandidateSort('owner')}>Owner context{candidateIndicator('owner')}</button></th><th><button onClick={() => changeCandidateSort('borough')}>Borough{candidateIndicator('borough')}</button></th><th><button onClick={() => changeCandidateSort('towers')}>Towers{candidateIndicator('towers')}</button></th><th><button onClick={() => changeCandidateSort('priority')}>Priority{candidateIndicator('priority')}</button></th><th><button onClick={() => changeCandidateSort('contacts')}>HPD contacts{candidateIndicator('contacts')}</button></th><th>Action</th></tr></thead><tbody>{visibleCandidates.map(row => <tr key={row.system_id}><td><strong>{row.address ?? row.system_id}</strong><small>{row.bbl ? `BBL ${row.bbl}` : row.system_id}</small></td><td>{row.pluto_owner_name ?? '—'}</td><td>{row.borough ?? '—'}</td><td>{row.active_equipment}</td><td>{row.priority_score}</td><td>{row.hpd_contact_count ?? 0}</td><td><button className="table-link" onClick={() => onOpenAccount(row)}>Research →</button></td></tr>)}</tbody></table></div>
      <PageControls page={safeCandidatePage} total={sortedCandidates.length} onPage={setCandidatePage} />
    </div>
  </section>
}
