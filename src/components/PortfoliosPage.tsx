import { useState } from 'react'
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

const number = new Intl.NumberFormat('en-US')
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

export function PortfoliosPage({ payload, watchedSystemIds, onOpenAccount }: { payload: SystemsPayload; watchedSystemIds: Set<string>; onOpenAccount: (row: SystemSummary) => void }) {
  const rows = payload.systems
  const groups = ownerGroups(rows)
  const [selectedKey, setSelectedKey] = useState<string | null>(ownerKeyFromHash)
  const plutoContext = rows.filter(row => row.pluto_match).length
  const contactReady = rows.filter(row => (row.hpd_contact_count ?? 0) > 0).length
  const acrisContext = rows.filter(row => ((row as SystemSummary & AcrisSummaryFields).acris_recent_document_count ?? 0) > 0).length
  const candidates = [...rows].filter(row => row.pluto_match && normalizedOwnerName(row.pluto_owner_name)).sort((a, b) => b.active_equipment - a.active_equipment || b.priority_score - a.priority_score).slice(0, 12)
  const selectedGroup = groups.find(group => group.key === selectedKey) ?? groups[0]

  const selectGroup = (group: OwnerGroup) => {
    setSelectedKey(group.key)
    window.location.hash = `#/portfolios?owner=${encodeURIComponent(group.key)}`
  }

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
      {selectedGroup && <div className="portfolio-detail"><div className="portfolio-detail-heading"><div><span className="confidence-chip">CONTEXT · PLUTO OWNER NAME</span><h2>{selectedGroup.name}</h2><p>{selectedGroup.rows.length} cooling-tower accounts · {selectedGroup.towers} active equipment · {selectedGroup.contactReady} contact-ready{selectedGroup.buildingAreaSqft > 0 ? ` · ${number.format(Math.round(selectedGroup.buildingAreaSqft))} sq ft PLUTO building area` : ''}</p></div></div><div className="reference-table-card"><div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Property</th><th>Borough</th><th>Priority</th><th>Towers</th><th>Building area</th><th>Contacts</th><th>Action</th></tr></thead><tbody>{selectedGroup.rows.slice(0, 30).map(row => <tr key={row.system_id} onClick={() => onOpenAccount(row)}><td><strong>{row.address ?? row.system_id}</strong><small>{row.bbl ? `BBL ${row.bbl}` : row.system_id}</small></td><td>{row.borough ?? '—'}</td><td>{row.priority_score}</td><td>{row.active_equipment}</td><td>{row.pluto_building_area_sqft ? `${number.format(Math.round(row.pluto_building_area_sqft))} sq ft` : '—'}</td><td>{row.hpd_contact_count ?? 0}</td><td><button className="table-link" onClick={event => { event.stopPropagation(); onOpenAccount(row) }}>Open →</button></td></tr>)}</tbody></table></div></div></div>}
    </div>}

    <div className="reference-table-card portfolio-candidates">
      <div className="reference-table-heading"><div><strong>Portfolio research candidates</strong><span>Large multi-equipment properties with meaningful exact PLUTO owner context; these are individual accounts, not inferred portfolios.</span></div></div>
      <div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Account</th><th>Owner context</th><th>Borough</th><th>Towers</th><th>Priority</th><th>HPD contacts</th><th>Action</th></tr></thead><tbody>{candidates.map(row => <tr key={row.system_id}><td><strong>{row.address ?? row.system_id}</strong><small>{row.bbl ? `BBL ${row.bbl}` : row.system_id}</small></td><td>{row.pluto_owner_name ?? '—'}</td><td>{row.borough ?? '—'}</td><td>{row.active_equipment}</td><td>{row.priority_score}</td><td>{row.hpd_contact_count ?? 0}</td><td><button className="table-link" onClick={() => onOpenAccount(row)}>Research →</button></td></tr>)}</tbody></table></div>
    </div>
  </section>
}