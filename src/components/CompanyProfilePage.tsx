import { useEffect, useMemo, useState } from 'react'
import { loadCompanies, loadProcurement } from '../data/api'
import type { CompanyIntelligencePayload, CompanyIntelligenceRecord } from '../types/company'
import type { ProcurementBundle, ProcurementRecord } from '../types/procurement'
import { formatDate } from '../domain/labels'
import { ShareButton } from './ShareButton'

const number = new Intl.NumberFormat('en-US')
const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

function categoryLabel(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, match => match.toUpperCase())
}

function recordDate(row: ProcurementRecord): string | null {
  return row.due_date ?? row.award_date ?? row.start_date ?? row.notice_start_date ?? row.retrieved_at ?? null
}

function recordAmount(row: ProcurementRecord): number | null {
  return row.current_amount ?? row.amount ?? row.original_amount ?? null
}

export function CompanyProfilePage({ companyId, onBack, onOpenCompany }: { companyId: string; onBack: () => void; onOpenCompany: (company: CompanyIntelligenceRecord) => void }) {
  const [companies, setCompanies] = useState<CompanyIntelligencePayload | null>(null)
  const [procurement, setProcurement] = useState<ProcurementBundle | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([loadCompanies(), loadProcurement()])
      .then(([companyPayload, procurementPayload]) => { setCompanies(companyPayload); setProcurement(procurementPayload) })
      .catch(err => setError(err instanceof Error ? err.message : 'Unable to load company profile evidence'))
  }, [])

  const company = useMemo(() => companies?.companies.find(row => row.company_id === companyId) ?? null, [companies, companyId])
  const records = useMemo(() => {
    if (!company || !procurement) return []
    const ids = new Set(company.procurement_ids)
    return [...procurement.cityRecord.notices, ...procurement.checkbook.contracts]
      .filter(row => ids.has(row.procurement_id))
      .sort((a, b) => (recordDate(b) ?? '').localeCompare(recordDate(a) ?? ''))
  }, [company, procurement])
  const candidateCompanies = useMemo(() => company && companies ? company.candidate_related_company_ids.map(id => companies.companies.find(row => row.company_id === id)).filter((row): row is CompanyIntelligenceRecord => Boolean(row)) : [], [company, companies])

  if (error) return <section className="product-page company-profile-page"><div className="account-profile-toolbar"><button className="breadcrumb-back" onClick={onBack}>← Back to Companies</button></div><div className="reference-empty-state"><strong>Company profile evidence is unavailable.</strong><span>{error}</span></div></section>
  if (!companies || !procurement) return <section className="product-page company-profile-page"><div className="account-profile-toolbar"><button className="breadcrumb-back" onClick={onBack}>← Back to Companies</button></div><div className="reference-empty-state"><strong>Loading source-backed company profile…</strong></div></section>
  if (!company) return <section className="product-page company-profile-page"><div className="account-profile-toolbar"><button className="breadcrumb-back" onClick={onBack}>← Back to Companies</button></div><div className="reference-empty-state"><strong>Company entity not found in the current observed-vendor snapshot.</strong><span>The share link may refer to a vendor label no longer present in the current procurement window.</span></div></section>

  return <section className="product-page company-profile-page">
    <div className="account-profile-toolbar"><div><button className="breadcrumb-back" onClick={onBack}>← Back to Companies</button><span>Observed public procurement vendor profile</span></div><div className="page-actions"><ShareButton label="Copy company link" /></div></div>
    <div className="product-page-heading company-profile-heading"><div><span className="page-kicker">{company.company_type.replaceAll('_', ' ').toLowerCase()}</span><h1>{company.canonical_name}</h1><p>This entity represents an observed public procurement vendor label. It does not assert corporate parentage, sponsor ownership, company revenue or a complete customer book.</p></div><div className="company-identity-card"><span className={`health-badge health-${company.cross_source_resolution_confidence === 'VERIFY' ? 'warning' : 'healthy'}`}>{company.cross_source_resolution_confidence}</span><small>Cross-source resolution</small><strong>{company.identity_basis.replaceAll('_', ' ').toLowerCase()}</strong></div></div>

    <div className="reference-metric-grid">
      <article><span className="reference-metric-icon">▤</span><div><small>Observed contracts</small><strong>{number.format(company.metrics.observed_contract_count)}</strong><span>{number.format(company.procurement_observation_count)} total procurement observations</span></div></article>
      <article><span className="reference-metric-icon success">◎</span><div><small>Observed buyers</small><strong>{number.format(company.metrics.observed_customer_count)}</strong><span>{number.format(company.metrics.repeat_customer_count)} repeat-buyer relationships</span></div></article>
      <article><span className="reference-metric-icon">$</span><div><small>Observed contract value</small><strong>{currency.format(company.metrics.observed_contract_value)}</strong><span>Public source value · not revenue</span></div></article>
      <article><span className="reference-metric-icon warning">◷</span><div><small>Active contracts</small><strong>{number.format(company.metrics.active_contract_count)}</strong><span>{number.format(company.metrics.contracts_expiring_12m)} expiring ≤12m</span></div></article>
      <article><span className="reference-metric-icon">↻</span><div><small>Repeat-buyer proxy</small><strong>{company.metrics.observable_customer_retention == null ? '—' : `${Math.round(company.metrics.observable_customer_retention * 100)}%`}</strong><span>Repeat observed buyers / observed buyers</span></div></article>
    </div>

    <div className="company-profile-grid">
      <section className="reference-table-card company-evidence-card"><div className="reference-table-heading"><div><strong>Identity &amp; source evidence</strong><span>Observed vendor labels only</span></div></div><dl className="detail-grid"><div><dt>Canonical display label</dt><dd>{company.canonical_name}</dd></div><div><dt>Identity confidence</dt><dd>{company.identity_confidence}</dd></div><div><dt>Cross-source resolution</dt><dd>{company.cross_source_resolution_confidence} · {company.cross_source_resolution_method.replaceAll('_', ' ').toLowerCase()}</dd></div><div><dt>First observed</dt><dd>{company.first_seen ? formatDate(company.first_seen) : '—'}</dd></div><div><dt>Last observed</dt><dd>{company.last_seen ? formatDate(company.last_seen) : '—'}</dd></div><div><dt>Sources</dt><dd>{company.observed_sources.join(' · ') || '—'}</dd></div></dl><div className="evidence-list"><strong>Published aliases</strong>{company.aliases.map(alias => <div key={`${alias.source}-${alias.alias}`}><span>{alias.alias}</span><small>{alias.source} · {alias.confidence} · {alias.resolution_method.replaceAll('_', ' ').toLowerCase()}</small></div>)}</div></section>
      <section className="reference-table-card company-evidence-card"><div className="reference-table-heading"><div><strong>Observed commercial footprint</strong><span>Derived only from retained public procurement observations</span></div></div><div className="evidence-list"><strong>Service categories</strong>{company.service_categories.map(value => <div key={value}><span>{categoryLabel(value)}</span></div>)}</div><div className="evidence-list"><strong>Public buyers</strong>{company.observed_buyers.slice(0, 20).map(value => <div key={value}><span>{value}</span></div>)}</div></section>
    </div>

    {candidateCompanies.length > 0 && <div className="reference-table-card"><div className="reference-table-heading"><div><strong>Resolution candidates requiring review</strong><span>Similar normalized base name; not a confirmed corporate relationship.</span></div></div><div className="candidate-company-list">{candidateCompanies.map(candidate => <button key={candidate.company_id} onClick={() => onOpenCompany(candidate)}><strong>{candidate.canonical_name}</strong><span>{candidate.cross_source_resolution_confidence} · separate observed vendor entity</span></button>)}</div></div>}

    <div className="reference-table-card"><div className="reference-table-heading"><div><strong>Public procurement observations</strong><span>{number.format(records.length)} source-backed records linked by this exact observed vendor entity</span></div></div><div className="reference-table-scroll"><table className="reference-table company-procurement-table"><thead><tr><th>Record</th><th>Source</th><th>Buyer</th><th>Service</th><th>Observed value</th><th>Date</th><th>Source evidence</th></tr></thead><tbody>{records.map(row => <tr key={row.procurement_id}><td><strong>{row.title ?? row.description ?? row.source_record_id}</strong><small>{row.source_contract_id ?? row.notice_id ?? row.source_record_id}</small></td><td>{row.source}<small>{row.vendor_role ?? row.scope ?? 'source observation'}</small></td><td>{row.buyer_name ?? row.agency ?? '—'}</td><td>{categoryLabel(row.service_category)}<small>{row.service_confidence}</small></td><td>{recordAmount(row) == null ? '—' : currency.format(recordAmount(row) ?? 0)}<small>{row.observed_value_evidence ?? row.amount_evidence ?? 'No amount published'}</small></td><td>{recordDate(row) ? formatDate(recordDate(row) ?? '') : '—'}</td><td>{row.source_url ? <a className="table-link" href={row.source_url} target="_blank" rel="noreferrer">Open source ↗</a> : '—'}</td></tr>)}</tbody></table></div></div>

    <div className="source-health-footnote">{company.value_semantics} No parent, sponsor, acquisition or private-company financial claims are created from procurement names alone.</div>
  </section>
}
