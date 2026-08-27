import { useEffect, useMemo, useState } from 'react'
import { loadCompanies } from '../data/api'
import type { CompanyIntelligencePayload, CompanyIntelligenceRecord } from '../types/company'
import { formatDate } from '../domain/labels'
import { ShareButton } from './ShareButton'

const number = new Intl.NumberFormat('en-US')
const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

function categoryLabel(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, match => match.toUpperCase())
}

export function CompaniesPage({ onOpenCompany }: { onOpenCompany: (company: CompanyIntelligenceRecord) => void }) {
  const [payload, setPayload] = useState<CompanyIntelligencePayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('ALL')
  const [resolution, setResolution] = useState('ALL')

  useEffect(() => {
    loadCompanies().then(setPayload).catch(err => setError(err instanceof Error ? err.message : 'Unable to load company intelligence'))
  }, [])

  const categories = useMemo(() => payload ? [...new Set(payload.companies.flatMap(company => company.service_categories))].sort() : [], [payload])
  const companies = useMemo(() => payload ? payload.companies.filter(company => {
    const query = search.trim().toLowerCase()
    if (query && ![company.canonical_name, ...company.aliases.map(alias => alias.alias), ...company.observed_buyers].join(' ').toLowerCase().includes(query)) return false
    if (category !== 'ALL' && !company.service_categories.includes(category)) return false
    if (resolution !== 'ALL' && company.cross_source_resolution_confidence !== resolution) return false
    return true
  }).slice(0, 200) : [], [payload, search, category, resolution])

  const totalObservedValue = payload?.companies.reduce((sum, company) => sum + company.metrics.observed_contract_value, 0) ?? 0
  const repeatRelationshipCompanies = payload?.companies.filter(company => company.metrics.repeat_customer_count > 0).length ?? 0

  return <section className="product-page companies-page">
    <div className="product-page-heading">
      <div><span className="page-kicker">New York City · observed vendor intelligence</span><h1>Companies</h1><p>Explore source-observed procurement vendors and their public customer/contract footprint. Company identities are conservative observed vendor labels; legal parentage, sponsor ownership and complete customer books are not inferred.</p></div>
      <div className="page-actions"><ShareButton label="Share this view" /></div>
    </div>

    {error && <div className="reference-empty-state"><strong>Company intelligence is unavailable.</strong><span>{error}</span><span>TowerSignal will not fabricate company relationships when the generated company payload is unavailable.</span></div>}
    {!payload && !error && <div className="reference-empty-state"><strong>Loading observed-vendor company intelligence…</strong></div>}

    {payload && <>
      <div className="reference-metric-grid">
        <article><span className="reference-metric-icon success">◎</span><div><small>Observed vendors</small><strong>{number.format(payload.summary.observed_vendor_company_count)}</strong><span>Exact source-label entities</span></div></article>
        <article><span className="reference-metric-icon">▤</span><div><small>Procurement observations</small><strong>{number.format(payload.summary.procurement_observation_count)}</strong><span>Relevant City Record + Checkbook records</span></div></article>
        <article><span className="reference-metric-icon warning">?</span><div><small>Resolution review</small><strong>{number.format(payload.summary.companies_requiring_resolution_review)}</strong><span>Potential legal-suffix/source variants</span></div></article>
        <article><span className="reference-metric-icon">↻</span><div><small>Repeat-customer evidence</small><strong>{number.format(repeatRelationshipCompanies)}</strong><span>Companies with 2+ observations for a buyer</span></div></article>
        <article><span className="reference-metric-icon">$</span><div><small>Observed contract value</small><strong>{currency.format(totalObservedValue)}</strong><span>Public Checkbook values · not revenue</span></div></article>
      </div>

      <div className="reference-table-card">
        <div className="reference-table-heading">
          <div><strong>Company &amp; vendor intelligence</strong><span>{number.format(companies.length)} shown · generated {formatDate(payload.generated_at)}</span></div>
          <div className="page-actions company-filter-actions">
            <input aria-label="Company search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Company, alias or public buyer…" />
            <select aria-label="Company service category" value={category} onChange={event => setCategory(event.target.value)}><option value="ALL">All services</option>{categories.map(value => <option key={value} value={value}>{categoryLabel(value)}</option>)}</select>
            <select aria-label="Company resolution confidence" value={resolution} onChange={event => setResolution(event.target.value)}><option value="ALL">All resolution states</option><option value="STRONG">Strong</option><option value="VERIFY">Verify</option></select>
          </div>
        </div>
        <div className="reference-table-scroll"><table className="reference-table companies-table"><thead><tr><th>Company / vendor</th><th>Identity</th><th>Services</th><th>Contracts</th><th>Public buyers</th><th>Repeat buyers</th><th>Observed value</th><th>Active</th><th>Action</th></tr></thead><tbody>{companies.map(company => <tr key={company.company_id} onClick={() => onOpenCompany(company)}>
          <td><strong>{company.canonical_name}</strong><small>{company.observed_sources.join(' · ')}</small></td>
          <td><span className={`health-badge health-${company.cross_source_resolution_confidence === 'VERIFY' ? 'warning' : 'healthy'}`}>{company.cross_source_resolution_confidence}</span><small>{company.identity_scope.replaceAll('_', ' ').toLowerCase()}</small></td>
          <td><strong>{company.service_categories.slice(0, 2).map(categoryLabel).join(' · ') || '—'}</strong><small>{company.service_categories.length > 2 ? `+${company.service_categories.length - 2} more` : ''}</small></td>
          <td>{number.format(company.metrics.observed_contract_count)}<small>{number.format(company.procurement_observation_count)} total observations</small></td>
          <td>{number.format(company.metrics.observed_customer_count)}<small>{company.observed_buyers.slice(0, 2).join(' · ') || 'No buyer published'}</small></td>
          <td>{number.format(company.metrics.repeat_customer_count)}<small>{company.metrics.observable_customer_retention == null ? 'retention proxy unavailable' : `${Math.round(company.metrics.observable_customer_retention * 100)}% repeat-buyer proxy`}</small></td>
          <td>{currency.format(company.metrics.observed_contract_value)}<small>not company revenue</small></td>
          <td>{number.format(company.metrics.active_contract_count)}<small>{number.format(company.metrics.contracts_expiring_12m)} expiring ≤12m</small></td>
          <td><button className="table-link" onClick={event => { event.stopPropagation(); onOpenCompany(company) }}>Open company →</button></td>
        </tr>)}</tbody></table></div>
      </div>
      <div className="source-health-footnote">Observed vendor entities are built from exact public procurement labels with legal suffixes preserved. Similar base names are surfaced as VERIFY candidates rather than silently merged.</div>
    </>}
  </section>
}
