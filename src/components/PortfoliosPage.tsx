import type { SystemSummary, SystemsPayload } from '../types/data'
import type { AcrisSummaryFields } from '../types/acris'
import { ShareButton } from './ShareButton'

type PortfolioReadyRow = SystemSummary & {
  pluto_owner_name?: string | null
  pluto_building_area_sqft?: number | null
}

type OwnerGroup = {
  key: string
  name: string
  rows: PortfolioReadyRow[]
  towers: number
  highPriority: number
  contactReady: number
}

const number = new Intl.NumberFormat('en-US')

function ownerGroups(rows: SystemSummary[]): OwnerGroup[] {
  const groups = new Map<string, OwnerGroup>()
  rows.forEach(raw => {
    const row = raw as PortfolioReadyRow
    const name = row.pluto_owner_name?.trim()
    if (!name) return
    const key = name.replace(/\s+/g, ' ').toLocaleUpperCase('en-US')
    const current = groups.get(key) ?? { key, name, rows: [], towers: 0, highPriority: 0, contactReady: 0 }
    current.rows.push(row)
    current.towers += row.active_equipment
    current.highPriority += row.priority_score >= 70 ? 1 : 0
    current.contactReady += (row.hpd_contact_count ?? 0) > 0 ? 1 : 0
    groups.set(key, current)
  })
  return [...groups.values()].filter(group => group.rows.length > 1).sort((a, b) => b.rows.length - a.rows.length || b.towers - a.towers)
}

export function PortfoliosPage({ payload, watchedSystemIds, onOpenAccount }: { payload: SystemsPayload; watchedSystemIds: Set<string>; onOpenAccount: (row: SystemSummary) => void }) {
  const rows = payload.systems
  const groups = ownerGroups(rows)
  const plutoContext = rows.filter(row => row.pluto_match).length
  const contactReady = rows.filter(row => (row.hpd_contact_count ?? 0) > 0).length
  const acrisContext = rows.filter(row => ((row as SystemSummary & AcrisSummaryFields).acris_document_count ?? 0) > 0).length
  const candidates = [...rows].filter(row => row.pluto_match).sort((a, b) => b.active_equipment - a.active_equipment || b.priority_score - a.priority_score).slice(0, 12)
  const selectedGroup = groups[0]

  return <section className="product-page portfolios-page">
    <div className="product-page-heading">
      <div><span className="page-kicker">New York City · ownership context</span><h1>Portfolios</h1><p>Group related cooling-tower properties conservatively and keep every ownership relationship tied to its evidence.</p></div>
      <div className="page-actions"><ShareButton label="Share this view" /></div>
    </div>

    <div className="reference-metric-grid">
      <article><span className="reference-metric-icon success">⌂</span><div><small>PLUTO context</small><strong>{number.format(plutoContext)}</strong><span>Exact-BBL property matches</span></div></article>
      <article><span className="reference-metric-icon">◎</span><div><small>Owner groups indexed</small><strong>{number.format(groups.length)}</strong><span>{groups.length > 0 ? 'Exact normalized owner-name groups' : 'Not emitted in current summary payload'}</span></div></article>
      <article><span className="reference-metric-icon success">◉</span><div><small>Contact-ready</small><strong>{number.format(contactReady)}</strong><span>HPD contact context</span></div></article>
      <article><span className="reference-metric-icon">⌁</span><div><small>ACRIS context</small><strong>{number.format(acrisContext)}</strong><span>Exact-BBL recorded documents</span></div></article>
      <article><span className="reference-metric-icon warning">★</span><div><small>Watched accounts</small><strong>{number.format(watchedSystemIds.size)}</strong><span>Private workflow membership</span></div></article>
    </div>

    {groups.length === 0 ? <div className="portfolio-readiness-layout">
      <div className="roadmap-data-banner portfolio-index-banner"><div><span className="roadmap-status">DATA MODEL GAP</span><strong>The current account summary does not expose the PLUTO owner name needed to render ownership groups safely.</strong><p>The detailed records contain exact-BBL PLUTO owner context, but loading thousands of detail files in the browser would be an unsafe substitute for a deterministic portfolio index. This page intentionally does not fabricate owner groups.</p></div></div>
      <div className="portfolio-evidence-card"><span className="page-kicker">Portfolio evidence rule</span><h3>Grouping is context, not corporate-parent proof.</h3><p>The finished model should combine PLUTO ownership context, HPD registration/contact evidence and ACRIS party evidence, then label grouping confidence. Similar names alone are not enough.</p><div className="evidence-pill-row"><span>PLUTO · exact BBL</span><span>HPD · exact registration</span><span>ACRIS · exact document</span></div></div>
    </div> : <div className="portfolio-layout">
      <aside className="portfolio-list"><div className="portfolio-list-heading"><span className="page-kicker">Ownership groups</span><strong>{groups.length} multi-property groups</strong></div>{groups.slice(0, 20).map((group, index) => <article key={group.key} className={index === 0 ? 'active' : ''}><div><strong>{group.name}</strong><span>PLUTO owner-name context</span></div><dl><div><dt>Accounts</dt><dd>{group.rows.length}</dd></div><div><dt>Towers</dt><dd>{group.towers}</dd></div><div><dt>High priority</dt><dd>{group.highPriority}</dd></div></dl></article>)}</aside>
      {selectedGroup && <div className="portfolio-detail"><div className="portfolio-detail-heading"><div><span className="confidence-chip">CONTEXT · PLUTO OWNER NAME</span><h2>{selectedGroup.name}</h2><p>{selectedGroup.rows.length} cooling-tower accounts · {selectedGroup.towers} active equipment · {selectedGroup.contactReady} contact-ready</p></div></div><div className="reference-table-card"><div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Property</th><th>Borough</th><th>Priority</th><th>Towers</th><th>Contacts</th><th>Action</th></tr></thead><tbody>{selectedGroup.rows.slice(0, 30).map(row => <tr key={row.system_id} onClick={() => onOpenAccount(row)}><td><strong>{row.address ?? row.system_id}</strong><small>{row.system_id}</small></td><td>{row.borough ?? '—'}</td><td>{row.priority_score}</td><td>{row.active_equipment}</td><td>{row.hpd_contact_count ?? 0}</td><td><button className="table-link" onClick={event => { event.stopPropagation(); onOpenAccount(row) }}>Open →</button></td></tr>)}</tbody></table></div></div></div>}
    </div>}

    <div className="reference-table-card portfolio-candidates">
      <div className="reference-table-heading"><div><strong>Portfolio research candidates</strong><span>Large multi-equipment properties with exact PLUTO context; these are individual accounts, not inferred portfolios.</span></div></div>
      <div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Account</th><th>Borough</th><th>Towers</th><th>Priority</th><th>HPD contacts</th><th>Action</th></tr></thead><tbody>{candidates.map(row => <tr key={row.system_id}><td><strong>{row.address ?? row.system_id}</strong><small>{row.bbl ? `BBL ${row.bbl}` : row.system_id}</small></td><td>{row.borough ?? '—'}</td><td>{row.active_equipment}</td><td>{row.priority_score}</td><td>{row.hpd_contact_count ?? 0}</td><td><button className="table-link" onClick={() => onOpenAccount(row)}>Research →</button></td></tr>)}</tbody></table></div>
    </div>
  </section>
}
