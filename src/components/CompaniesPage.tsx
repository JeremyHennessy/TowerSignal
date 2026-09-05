import { useEffect, useMemo, useState } from 'react'
import { loadCompanies, loadDomesticWaterMarket, loadElapProbe, loadProviderResolution } from '../data/api'
import type { CompanyIntelligencePayload, CompanyIntelligenceRecord } from '../types/company'
import type { DomesticWaterMarketPayload, ElapProbePayload, ProviderCompanyObservation, ProviderResolutionPayload } from '../types/water'
import { formatTimestamp } from '../domain/labels'
import { ShareButton } from './ShareButton'

const number = new Intl.NumberFormat('en-US')
const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

function categoryLabel(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, match => match.toUpperCase())
}

function waterObservationType(value: ProviderCompanyObservation['type']): string {
  if (value === 'DWT_PROVIDER') return 'DWT provider'
  if (value === 'DWT_LAB') return 'DWT laboratory'
  return 'DEC 7G'
}

function marketObservationRows(payload: DomesticWaterMarketPayload | null): ProviderCompanyObservation[] {
  if (!payload) return []
  return [
    ...payload.providers.map(provider => ({
      id: provider.provider_id,
      label: provider.aliases[0]?.name ?? provider.provider_key,
      type: 'DWT_PROVIDER' as const,
      observedBuildings: provider.observed_building_count,
      observationCount: provider.inspection_count,
      confidence: 'VERIFY' as const,
      evidence: 'NYC drinking-water tank inspection provider field',
    })),
    ...payload.laboratories.map(lab => ({
      id: lab.lab_id,
      label: lab.aliases[0]?.name ?? lab.lab_key,
      type: 'DWT_LAB' as const,
      observedBuildings: lab.observed_building_count,
      observationCount: lab.inspection_count,
      confidence: 'VERIFY' as const,
      evidence: 'NYC drinking-water tank inspection laboratory field',
    })),
    ...payload.dec_7g_businesses.map((business, index) => ({
      id: business.qualification_id || `dec-7g-${index}`,
      label: business.provider_name ?? business.provider_key,
      type: 'DEC_7G' as const,
      observedBuildings: null,
      observationCount: 1,
      confidence: 'VERIFY' as const,
      evidence: [business.qualification_scope, business.registration_number].filter(Boolean).join(' · ') || 'DEC 7G qualified business registration',
    })),
  ].sort((a, b) => (b.observedBuildings ?? 0) - (a.observedBuildings ?? 0) || (b.observationCount ?? 0) - (a.observationCount ?? 0) || a.label.localeCompare(b.label))
}

export function CompaniesPage({ onOpenCompany }: { onOpenCompany: (company: CompanyIntelligenceRecord) => void }) {
  const [payload, setPayload] = useState<CompanyIntelligencePayload | null>(null)
  const [market, setMarket] = useState<DomesticWaterMarketPayload | null>(null)
  const [resolutionReview, setResolutionReview] = useState<ProviderResolutionPayload | null>(null)
  const [elapProbe, setElapProbe] = useState<ElapProbePayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [marketError, setMarketError] = useState<string | null>(null)
  const [resolutionError, setResolutionError] = useState<string | null>(null)
  const [elapError, setElapError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('ALL')
  const [resolution, setResolution] = useState('ALL')

  useEffect(() => {
    let cancelled = false
    Promise.allSettled([loadCompanies(), loadDomesticWaterMarket(), loadProviderResolution(), loadElapProbe()])
      .then(([companiesResult, marketResult, resolutionResult, elapResult]) => {
        if (cancelled) return
        if (companiesResult.status === 'fulfilled') {
          setPayload(companiesResult.value)
        } else {
          setError(companiesResult.reason instanceof Error ? companiesResult.reason.message : 'Unable to load company intelligence')
        }
        if (marketResult.status === 'fulfilled') {
          setMarket(marketResult.value)
        } else {
          setMarketError(marketResult.reason instanceof Error ? marketResult.reason.message : 'Domestic-water provider intelligence is unavailable')
        }
        if (resolutionResult.status === 'fulfilled') {
          setResolutionReview(resolutionResult.value)
        } else {
          setResolutionError(resolutionResult.reason instanceof Error ? resolutionResult.reason.message : 'Provider identity review is unavailable')
        }
        if (elapResult.status === 'fulfilled') {
          setElapProbe(elapResult.value)
        } else {
          setElapError(elapResult.reason instanceof Error ? elapResult.reason.message : 'ELAP source probe is unavailable')
        }
      })
    return () => { cancelled = true }
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
  const waterObservations = useMemo(() => marketObservationRows(market), [market])
  const visibleWaterObservations = useMemo(() => {
    const query = search.trim().toLowerCase()
    return waterObservations.filter(row => !query || `${row.label} ${row.evidence}`.toLowerCase().includes(query)).slice(0, 80)
  }, [waterObservations, search])

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
        <article><span className="reference-metric-icon">WT</span><div><small>DWT provider observations</small><strong>{market ? number.format(market.summary.observed_provider_count) : '—'}</strong><span>{market ? 'NYC tank inspection source labels' : 'Optional cache unavailable'}</span></div></article>
        <article><span className="reference-metric-icon">LAB</span><div><small>DWT labs observed</small><strong>{market ? number.format(market.summary.observed_laboratory_count) : '—'}</strong><span>{elapProbe ? `ELAP selector ${number.format(elapProbe.lab_selector.populated_option_count)}` : 'ELAP scope claims gated'}</span></div></article>
      </div>

      <div className="company-profile-grid water-company-evidence-grid">
        <section className="reference-table-card company-evidence-card">
          <div className="reference-table-heading"><div><strong>Domestic-water provider and lab observations</strong><span>{number.format(visibleWaterObservations.length)} shown · provider, lab and DEC labels are not merged into procurement companies automatically</span></div></div>
          {marketError ? <div className="reference-empty-state compact"><strong>Domestic-water market cache unavailable.</strong><span>{marketError}</span></div> : !market ? <div className="reference-empty-state compact"><strong>Domestic-water provider cache not loaded.</strong><span>The Companies table remains limited to public procurement vendors.</span></div> : <div className="reference-table-scroll"><table className="reference-table provider-observation-table"><thead><tr><th>Name</th><th>Evidence type</th><th>Buildings</th><th>Observations</th><th>Confidence</th><th>Evidence</th></tr></thead><tbody>{visibleWaterObservations.map(row => <tr key={`${row.type}-${row.id}`}>
            <td><strong>{row.label}</strong><small>{row.id}</small></td>
            <td>{waterObservationType(row.type)}</td>
            <td>{row.observedBuildings == null ? '—' : number.format(row.observedBuildings)}</td>
            <td>{row.observationCount == null ? '—' : number.format(row.observationCount)}</td>
            <td><span className="health-badge health-warning">{row.confidence}</span></td>
            <td>{row.evidence}</td>
          </tr>)}</tbody></table></div>}
        </section>
        <section className="reference-table-card company-evidence-card">
          <div className="reference-table-heading"><div><strong>Provider identity review and ELAP gate</strong><span>Review signals only; no provider or lab accreditation merge is inferred</span></div></div>
          {resolutionError && <div className="reference-empty-state compact"><strong>Provider review cache unavailable.</strong><span>{resolutionError}</span></div>}
          {resolutionReview && <dl className="detail-grid company-review-summary">
            <div><dt>Alias review candidates</dt><dd>{number.format(resolutionReview.summary.alias_review_candidate_count)}</dd></div>
            <div><dt>High-priority candidates</dt><dd>{number.format(resolutionReview.summary.high_priority_alias_candidate_count)}</dd></div>
            <div><dt>DEC name matches</dt><dd>{number.format(resolutionReview.summary.dec_name_match_count)}</dd></div>
            <div><dt>Merges applied</dt><dd>{number.format(resolutionReview.summary.merge_applied_count)}</dd></div>
          </dl>}
          {resolutionReview && resolutionReview.dec_name_matches.length > 0 && <div className="evidence-list"><strong>Top DEC name matches</strong>{resolutionReview.dec_name_matches.slice(0, 8).map(match => <div key={match.match_id}><span>{match.provider_key}</span><small>{match.dec_provider_name ?? 'DEC name unavailable'} · {match.identity_confidence} · {match.relationship_evidence}</small></div>)}</div>}
          {elapError && <div className="reference-empty-state compact"><strong>ELAP source probe unavailable.</strong><span>{elapError}</span></div>}
          {elapProbe && <div className="source-row"><strong>ELAP public search contract</strong><span>{number.format(elapProbe.lab_selector.populated_option_count)} populated lab options · {elapProbe.detail_resolution_probe.detail_resolution_status}</span><small>Scope/accreditation assertions stay disabled until a deterministic potable-water scope crawler is built.</small></div>}
        </section>
      </div>

      <div className="reference-table-card">
        <div className="reference-table-heading">
          <div><strong>Company &amp; vendor intelligence</strong><span>{number.format(companies.length)} shown · generated {formatTimestamp(payload.generated_at)}</span></div>
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
