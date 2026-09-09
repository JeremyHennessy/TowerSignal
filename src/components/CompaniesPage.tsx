import { useEffect, useMemo, useState } from 'react'
import { loadKnownFirms } from '../data/api'
import type { CompanyIntelligenceRecord } from '../types/company'
import type { KnownFirmPayload, KnownFirmRole, KnownFirmSummaryRecord } from '../types/firm'
import { formatDate, formatTimestamp } from '../domain/labels'
import { ShareButton } from './ShareButton'

const number = new Intl.NumberFormat('en-US')
const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const PAGE_SIZE = 100

type SortKey = 'canonical_name' | 'serviced_site_count' | 'observed_site_count' | 'tower_account_count' | 'latest_observed_date' | 'observed_contract_count' | 'observed_customer_count' | 'observed_contract_value' | 'identity_confidence'
type SortDirection = 'asc' | 'desc'

function label(value: string): string {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, match => match.toUpperCase())
}

function roleLabel(value: KnownFirmRole): string {
  const overrides: Record<string, string> = {
    DWT_INSPECTION_PROVIDER: 'DWT service provider',
    DWT_LABORATORY: 'DWT laboratory',
    PROCUREMENT_VENDOR: 'Procurement vendor',
    DEC_7G_REGISTERED_BUSINESS: 'DEC 7G business',
    DOB_NOW_APPLICANT_BUSINESS: 'DOB applicant business',
    DOB_NOW_OWNER_BUSINESS: 'DOB owner business',
    LEGACY_DOB_OWNER_BUSINESS: 'Legacy DOB owner business',
  }
  return overrides[value] ?? label(value)
}

function csvCell(value: unknown): string {
  const text = String(value ?? '')
  return `"${text.replaceAll('"', '""')}"`
}

function exportKnownFirms(rows: KnownFirmSummaryRecord[]) {
  const header = [
    'firm_id', 'canonical_name', 'roles', 'serviced_site_count', 'contracted_site_count', 'observed_site_count',
    'tower_account_count', 'observation_count', 'latest_observed_date', 'active_last_12m', 'observed_contract_count',
    'observed_customer_count', 'observed_contract_value', 'identity_confidence', 'resolution_method', 'source_classes',
  ]
  const lines = [
    header.map(csvCell).join(','),
    ...rows.map(row => [
      row.firm_id, row.canonical_name, row.roles.join('|'), row.serviced_site_count, row.contracted_site_count,
      row.observed_site_count, row.tower_account_count, row.observation_count, row.latest_observed_date ?? '',
      row.active_last_12m, row.observed_contract_count, row.observed_customer_count, row.observed_contract_value,
      row.identity_confidence, row.resolution_method, row.source_classes.join('|'),
    ].map(csvCell).join(',')),
  ]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = 'towersignal-known-firms.csv'
  anchor.click()
  URL.revokeObjectURL(url)
}

function compareValues(left: unknown, right: unknown): number {
  if (typeof left === 'number' && typeof right === 'number') return left - right
  if (typeof left === 'boolean' && typeof right === 'boolean') return Number(left) - Number(right)
  return String(left ?? '').localeCompare(String(right ?? ''), undefined, { numeric: true, sensitivity: 'base' })
}

export function CompaniesPage({ onOpenCompany }: { onOpenCompany: (company: CompanyIntelligenceRecord) => void }) {
  void onOpenCompany
  const [payload, setPayload] = useState<KnownFirmPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [role, setRole] = useState('ALL')
  const [relationship, setRelationship] = useState('ALL')
  const [confidence, setConfidence] = useState('ALL')
  const [activity, setActivity] = useState('ALL')
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({ key: 'serviced_site_count', direction: 'desc' })
  const [page, setPage] = useState(1)

  useEffect(() => {
    let cancelled = false
    loadKnownFirms()
      .then(value => { if (!cancelled) setPayload(value) })
      .catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : 'Unable to load known-firm intelligence') })
    return () => { cancelled = true }
  }, [])

  const roles = useMemo(() => payload ? [...new Set(payload.firms.flatMap(firm => firm.roles))].sort() : [], [payload])
  const filtered = useMemo(() => payload ? payload.firms.filter(firm => {
    const query = search.trim().toLowerCase()
    const haystack = [firm.canonical_name, firm.normalized_name, ...firm.roles, ...firm.source_classes, ...firm.service_categories].join(' ').toLowerCase()
    if (query && !haystack.includes(query)) return false
    if (role !== 'ALL' && !firm.roles.includes(role)) return false
    if (relationship === 'SERVICED' && firm.serviced_site_count === 0) return false
    if (relationship === 'CONTRACTED' && firm.contracted_site_count === 0) return false
    if (relationship === 'RELATED' && firm.observed_site_count === 0) return false
    if (confidence !== 'ALL' && firm.identity_confidence !== confidence) return false
    if (activity === 'RECENT' && !firm.active_last_12m) return false
    return true
  }) : [], [payload, search, role, relationship, confidence, activity])

  const sorted = useMemo(() => [...filtered].sort((a, b) => {
    const result = compareValues(a[sort.key], b[sort.key]) || a.canonical_name.localeCompare(b.canonical_name)
    return sort.direction === 'asc' ? result : -result
  }), [filtered, sort])

  useEffect(() => { setPage(1) }, [search, role, relationship, confidence, activity, sort])
  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE))
  useEffect(() => { if (page > pageCount) setPage(pageCount) }, [page, pageCount])
  const visible = useMemo(() => sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE), [sorted, page])
  const jsonUrl = `${import.meta.env.BASE_URL}data/known-firms.json`
  const openFirm = (firm: KnownFirmSummaryRecord) => { window.location.hash = `#/company/${encodeURIComponent(firm.firm_id)}` }
  const changeSort = (key: SortKey) => setSort(current => current.key === key
    ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
    : { key, direction: key === 'canonical_name' ? 'asc' : 'desc' })
  const sortIndicator = (key: SortKey) => sort.key === key ? (sort.direction === 'asc' ? ' ↑' : ' ↓') : ''

  return <section className="product-page companies-page known-firms-page">
    <div className="product-page-heading">
      <div>
        <span className="page-kicker">New York · normalized firm intelligence</span>
        <h1>Known firms</h1>
        <p>One normalized workspace for source-observed service providers, laboratories, procurement vendors, qualified 7G businesses and DOB project-role firms. Serviced-site counts require explicit provider or laboratory evidence at the building; procurement and project relationships remain separate.</p>
      </div>
      <div className="page-actions">
        <a className="secondary-link-button" href={jsonUrl} target="_blank" rel="noreferrer">Open JSON dataset ↗</a>
        <button onClick={() => exportKnownFirms(sorted)} disabled={sorted.length === 0}>Export {number.format(sorted.length)} firms</button>
        <ShareButton label="Share this view" />
      </div>
    </div>

    {error && <div className="reference-empty-state"><strong>Known-firm intelligence is unavailable.</strong><span>{error}</span><span>TowerSignal will not fall back to disconnected provider/company lists when the normalized dataset is missing.</span></div>}
    {!payload && !error && <div className="reference-empty-state"><strong>Loading normalized firm intelligence…</strong></div>}

    {payload && <>
      <div className="reference-metric-grid known-firm-metrics">
        <article><span className="reference-metric-icon success">◎</span><div><small>Known firms</small><strong>{number.format(payload.summary.known_firm_count)}</strong><span>Normalized source-observed entities</span></div></article>
        <article><span className="reference-metric-icon urgent">⌂</span><div><small>Firms with serviced sites</small><strong>{number.format(payload.summary.firms_with_serviced_sites)}</strong><span>Explicit DWT provider/lab evidence</span></div></article>
        <article><span className="reference-metric-icon">●</span><div><small>Unique serviced sites</small><strong>{number.format(payload.summary.unique_serviced_site_count)}</strong><span>Building-level, not tower-count inflated</span></div></article>
        <article><span className="reference-metric-icon warning">▤</span><div><small>Procurement firms</small><strong>{number.format(payload.summary.firms_with_procurement_evidence)}</strong><span>Observed public vendor entities</span></div></article>
        <article><span className="reference-metric-icon">⌁</span><div><small>Related sites</small><strong>{number.format(payload.summary.unique_related_site_count)}</strong><span>Service, contract or project-role evidence</span></div></article>
        <article><span className="reference-metric-icon">◉</span><div><small>Mapped relationships</small><strong>{number.format(payload.summary.mapped_firm_site_relationship_count)}</strong><span>Firm-site rows with usable coordinates</span></div></article>
      </div>

      <div className="reference-table-card known-firm-boundary-card">
        <div className="known-firm-boundary-grid">
          <div><strong>Serviced site</strong><span>Source explicitly names the firm or laboratory on a DWT inspection at that building.</span></div>
          <div><strong>Contracted site</strong><span>Public procurement has a confirmed TowerSignal account link. It does not prove work was completed.</span></div>
          <div><strong>Related site</strong><span>Includes service, procurement and exact-property DOB business roles. Related does not mean incumbent provider.</span></div>
          <div><strong>Identity</strong><span>Legal suffixes are preserved; ambiguous cross-source names remain separate review candidates.</span></div>
        </div>
      </div>

      <div className="reference-table-card">
        <div className="reference-table-heading known-firm-table-heading">
          <div><strong>Normalized firm summary</strong><span>{number.format(sorted.length)} matching of {number.format(payload.summary.known_firm_count)} · generated {formatTimestamp(payload.generated_at)}</span></div>
          <div className="page-actions company-filter-actions known-firm-filters">
            <input aria-label="Known firm search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Firm, role, service or source…" />
            <select aria-label="Known firm role" value={role} onChange={event => setRole(event.target.value)}><option value="ALL">All roles</option>{roles.map(value => <option key={value} value={value}>{roleLabel(value)}</option>)}</select>
            <select aria-label="Known firm relationship" value={relationship} onChange={event => setRelationship(event.target.value)}><option value="ALL">All relationships</option><option value="SERVICED">Has serviced sites</option><option value="CONTRACTED">Has confirmed contract sites</option><option value="RELATED">Has any related sites</option></select>
            <select aria-label="Known firm activity" value={activity} onChange={event => setActivity(event.target.value)}><option value="ALL">Any activity date</option><option value="RECENT">Observed in last 12 months</option></select>
            <select aria-label="Known firm identity confidence" value={confidence} onChange={event => setConfidence(event.target.value)}><option value="ALL">All identity states</option><option value="CONFIRMED">Confirmed</option><option value="STRONG">Strong</option><option value="VERIFY">Verify</option></select>
          </div>
        </div>
        <div className="reference-table-scroll"><table className="reference-table companies-table known-firms-table"><thead><tr>
          <th><button onClick={() => changeSort('canonical_name')}>Firm{sortIndicator('canonical_name')}</button></th>
          <th>Roles</th>
          <th><button onClick={() => changeSort('serviced_site_count')}>Serviced sites{sortIndicator('serviced_site_count')}</button></th>
          <th><button onClick={() => changeSort('observed_site_count')}>Related sites{sortIndicator('observed_site_count')}</button></th>
          <th><button onClick={() => changeSort('tower_account_count')}>Tower accounts{sortIndicator('tower_account_count')}</button></th>
          <th><button onClick={() => changeSort('latest_observed_date')}>Last active{sortIndicator('latest_observed_date')}</button></th>
          <th><button onClick={() => changeSort('observed_contract_count')}>Contracts{sortIndicator('observed_contract_count')}</button></th>
          <th><button onClick={() => changeSort('observed_customer_count')}>Public buyers{sortIndicator('observed_customer_count')}</button></th>
          <th><button onClick={() => changeSort('observed_contract_value')}>Observed value{sortIndicator('observed_contract_value')}</button></th>
          <th><button onClick={() => changeSort('identity_confidence')}>Identity{sortIndicator('identity_confidence')}</button></th><th>Action</th>
        </tr></thead><tbody>{visible.map(firm => <tr key={firm.firm_id} onClick={() => openFirm(firm)}>
          <td><strong>{firm.canonical_name}</strong><small>{number.format(firm.observation_count)} observations · {firm.source_classes.slice(0, 2).map(label).join(' · ') || 'Source observed'}</small></td>
          <td><strong>{firm.roles.slice(0, 2).map(roleLabel).join(' · ')}</strong><small>{firm.roles.length > 2 ? `+${firm.roles.length - 2} more roles` : firm.primary_role !== firm.roles[0] ? roleLabel(firm.primary_role) : ''}</small></td>
          <td><strong>{number.format(firm.serviced_site_count)}</strong><small>explicit DWT service</small></td>
          <td><strong>{number.format(firm.observed_site_count)}</strong><small>{number.format(firm.contracted_site_count)} confirmed contract · {number.format(firm.project_site_count)} project-role</small></td>
          <td><strong>{number.format(firm.tower_account_count)}</strong><small>{number.format(firm.mapped_site_count)} mapped sites</small></td>
          <td><strong>{firm.latest_observed_date ? formatDate(firm.latest_observed_date) : '—'}</strong><small>{firm.active_last_12m ? 'Observed ≤12 months' : firm.first_observed_date ? `First ${formatDate(firm.first_observed_date)}` : 'No dated observation'}</small></td>
          <td><strong>{number.format(firm.observed_contract_count)}</strong><small>{number.format(firm.active_contract_count)} active</small></td>
          <td><strong>{number.format(firm.observed_customer_count)}</strong><small>{number.format(firm.repeat_buyer_count)} repeat buyers</small></td>
          <td><strong>{firm.observed_contract_value ? currency.format(firm.observed_contract_value) : '—'}</strong><small>public values · not revenue</small></td>
          <td><span className={`health-badge health-${firm.identity_confidence === 'VERIFY' || firm.identity_confidence === 'UNRESOLVED' ? 'warning' : 'healthy'}`}>{firm.identity_confidence}</span><small>{label(firm.resolution_method)}</small></td>
          <td><button className="table-link" onClick={event => { event.stopPropagation(); openFirm(firm) }}>Open firm →</button></td>
        </tr>)}</tbody></table></div>
        {sorted.length > PAGE_SIZE && <div className="known-firm-pagination"><button onClick={() => setPage(value => Math.max(1, value - 1))} disabled={page === 1}>← Previous</button><span>Page {number.format(page)} of {number.format(pageCount)} · rows {number.format((page - 1) * PAGE_SIZE + 1)}–{number.format(Math.min(page * PAGE_SIZE, sorted.length))}</span><button onClick={() => setPage(value => Math.min(pageCount, value + 1))} disabled={page === pageCount}>Next →</button></div>}
      </div>
      <div className="source-health-footnote">{payload.evidence_semantics.normalization} {payload.evidence_semantics.serviced_sites}</div>
    </>}
  </section>
}
