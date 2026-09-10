import { useEffect, useMemo, useState } from 'react'
import { loadKnownFirms } from '../data/api'
import type { CompanyIntelligenceRecord } from '../types/company'
import type { KnownFirmPayload, KnownFirmRole, KnownFirmSummaryRecord } from '../types/firm'
import { formatDate, formatTimestamp } from '../domain/labels'
import { ShareButton } from './ShareButton'

const number = new Intl.NumberFormat('en-US')
const currency = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
const PAGE_SIZE = 50

type SortKey =
  | 'canonical_name'
  | 'serviced_site_count'
  | 'tower_account_count'
  | 'latest_observed_date'
  | 'observed_contract_count'
  | 'observed_customer_count'
  | 'active_qualification_count'
  | 'identity_confidence'
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
    'observed_customer_count', 'observed_contract_value', 'active_qualification_count', 'identity_confidence',
    'resolution_method', 'source_classes',
  ]
  const lines = [
    header.map(csvCell).join(','),
    ...rows.map(row => [
      row.firm_id, row.canonical_name, row.roles.join('|'), row.serviced_site_count, row.contracted_site_count,
      row.observed_site_count, row.tower_account_count, row.observation_count, row.latest_observed_date ?? '',
      row.active_last_12m, row.observed_contract_count, row.observed_customer_count, row.observed_contract_value,
      row.active_qualification_count, row.identity_confidence, row.resolution_method, row.source_classes.join('|'),
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
  const [page, setPage] = useState(0)

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
    const haystack = [
      firm.canonical_name,
      firm.normalized_name,
      ...firm.roles,
      ...firm.source_classes,
      ...firm.service_categories,
    ].join(' ').toLowerCase()
    if (query && !haystack.includes(query)) return false
    if (role !== 'ALL' && !firm.roles.includes(role)) return false
    if (relationship === 'SERVICED' && firm.serviced_site_count === 0) return false
    if (relationship === 'CONTRACTED' && firm.contracted_site_count === 0) return false
    if (relationship === 'TOWER' && firm.tower_account_count === 0) return false
    if (relationship === 'RELATED' && firm.observed_site_count === 0) return false
    if (confidence !== 'ALL' && firm.identity_confidence !== confidence) return false
    if (activity === 'RECENT' && !firm.active_last_12m) return false
    return true
  }) : [], [payload, search, role, relationship, confidence, activity])

  const sorted = useMemo(() => [...filtered].sort((a, b) => {
    const result = compareValues(a[sort.key], b[sort.key]) || a.canonical_name.localeCompare(b.canonical_name)
    return sort.direction === 'asc' ? result : -result
  }), [filtered, sort])

  useEffect(() => { setPage(0) }, [search, role, relationship, confidence, activity, sort])
  const maxPage = Math.max(0, Math.ceil(sorted.length / PAGE_SIZE) - 1)
  const activePage = Math.min(page, maxPage)
  const visible = useMemo(
    () => sorted.slice(activePage * PAGE_SIZE, activePage * PAGE_SIZE + PAGE_SIZE),
    [sorted, activePage],
  )
  const jsonUrl = `${import.meta.env.BASE_URL}data/known-firms.json`
  const openFirm = (firm: KnownFirmSummaryRecord) => { window.location.hash = `#/company/${encodeURIComponent(firm.firm_id)}` }
  const changeSort = (key: SortKey) => setSort(current => current.key === key
    ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
    : { key, direction: key === 'canonical_name' ? 'asc' : 'desc' })
  const sortIndicator = (key: SortKey) => sort.key === key ? (sort.direction === 'asc' ? ' ↑' : ' ↓') : ''

  return <section className="product-page companies-page known-firms-page">
    <div className="product-page-heading compact-heading">
      <div>
        <span className="page-kicker">New York · company and service-market intelligence</span>
        <h1>Known companies &amp; firms</h1>
        <p>One normalized list of every company or firm TowerSignal can support from public evidence: service providers, laboratories, procurement vendors, DEC 7G businesses and DOB project-role firms.</p>
      </div>
    </div>

    {error && <div className="reference-empty-state"><strong>Known-company intelligence is unavailable.</strong><span>{error}</span><span>TowerSignal will not substitute disconnected provider or vendor lists when the normalized dataset is missing.</span></div>}
    {!payload && !error && <div className="reference-empty-state"><strong>Loading normalized company intelligence…</strong></div>}

    {payload && <div className="table-card account-table-card known-firms-master-card">
      <div className="firm-master-toolbar">
        <div className="firm-master-summary">
          <strong>{number.format(sorted.length)} of {number.format(payload.summary.known_firm_count)} known firms</strong>
          <span>Generated {formatTimestamp(payload.generated_at)} · click any row for the complete firm profile and site map</span>
        </div>
        <div className="page-actions firm-master-actions">
          <a className="secondary-link-button" href={jsonUrl} target="_blank" rel="noreferrer">Dataset ↗</a>
          <button onClick={() => exportKnownFirms(sorted)} disabled={sorted.length === 0}>Export {number.format(sorted.length)}</button>
          <ShareButton label="Share view" />
        </div>
      </div>

      <div className="firm-master-filters" aria-label="Known company filters">
        <input aria-label="Known firm search" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search company, role, service or source…" />
        <select aria-label="Known firm role" value={role} onChange={event => setRole(event.target.value)}>
          <option value="ALL">All roles</option>
          {roles.map(value => <option key={value} value={value}>{roleLabel(value)}</option>)}
        </select>
        <select aria-label="Known firm relationship" value={relationship} onChange={event => setRelationship(event.target.value)}>
          <option value="ALL">All site relationships</option>
          <option value="SERVICED">Observed service sites</option>
          <option value="TOWER">Linked tower accounts</option>
          <option value="CONTRACTED">Confirmed contract sites</option>
          <option value="RELATED">Any related site</option>
        </select>
        <select aria-label="Known firm activity" value={activity} onChange={event => setActivity(event.target.value)}>
          <option value="ALL">Any activity date</option>
          <option value="RECENT">Observed in last 12 months</option>
        </select>
        <select aria-label="Known firm identity confidence" value={confidence} onChange={event => setConfidence(event.target.value)}>
          <option value="ALL">All identity states</option>
          <option value="CONFIRMED">Confirmed</option>
          <option value="STRONG">Strong</option>
          <option value="VERIFY">Verify</option>
          <option value="UNRESOLVED">Unresolved</option>
        </select>
      </div>

      {sorted.length === 0 ? <div className="empty-state"><strong>No companies match these filters.</strong><span>Widen the role, relationship, activity or identity criteria.</span></div> : <div className="table-scroll"><table className="account-table known-firms-master-table"><thead><tr>
        <th><button onClick={() => changeSort('canonical_name')}>Company / firm{sortIndicator('canonical_name')}</button></th>
        <th>Role</th>
        <th><button onClick={() => changeSort('serviced_site_count')}>Service footprint{sortIndicator('serviced_site_count')}</button></th>
        <th><button onClick={() => changeSort('tower_account_count')}>Tower accounts{sortIndicator('tower_account_count')}</button></th>
        <th><button onClick={() => changeSort('latest_observed_date')}>Last active{sortIndicator('latest_observed_date')}</button></th>
        <th><button onClick={() => changeSort('observed_contract_count')}>Public contracts{sortIndicator('observed_contract_count')}</button></th>
        <th><button onClick={() => changeSort('observed_customer_count')}>Buyers{sortIndicator('observed_customer_count')}</button></th>
        <th><button onClick={() => changeSort('active_qualification_count')}>7G{sortIndicator('active_qualification_count')}</button></th>
        <th><button onClick={() => changeSort('identity_confidence')}>Identity{sortIndicator('identity_confidence')}</button></th>
        <th aria-label="Open firm" />
      </tr></thead><tbody>{visible.map(firm => <tr key={firm.firm_id} onClick={() => openFirm(firm)} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') openFirm(firm) }}>
        <td className="account-cell firm-name-cell">
          <strong>{firm.canonical_name}</strong>
          <span>{number.format(firm.observation_count)} public-record observation{firm.observation_count === 1 ? '' : 's'}</span>
          <small>{firm.source_classes.slice(0, 3).map(label).join(' · ') || 'Source observed'}</small>
        </td>
        <td><strong>{roleLabel(firm.primary_role)}</strong><small>{firm.roles.length > 1 ? `${firm.roles.length} observed roles` : 'Primary observed role'}</small></td>
        <td><strong>{number.format(firm.serviced_site_count)} serviced</strong><small>{number.format(firm.observed_site_count)} related · {number.format(firm.contracted_site_count)} contracted · {number.format(firm.project_site_count)} project</small></td>
        <td><strong>{number.format(firm.tower_account_count)}</strong><small>{number.format(firm.mapped_site_count)} mapped relationships</small></td>
        <td><strong>{firm.latest_observed_date ? formatDate(firm.latest_observed_date) : '—'}</strong><small>{firm.active_last_12m ? 'Observed ≤12 months' : firm.first_observed_date ? `First ${formatDate(firm.first_observed_date)}` : 'No dated observation'}</small></td>
        <td><strong>{number.format(firm.observed_contract_count)}</strong><small>{number.format(firm.active_contract_count)} active · {firm.observed_contract_value ? currency.format(firm.observed_contract_value) : 'no published value'}</small></td>
        <td><strong>{number.format(firm.observed_customer_count)}</strong><small>{number.format(firm.repeat_buyer_count)} repeat buyer{firm.repeat_buyer_count === 1 ? '' : 's'}</small></td>
        <td><strong>{number.format(firm.active_qualification_count)}</strong><small>{number.format(firm.qualification_count)} observed registration{firm.qualification_count === 1 ? '' : 's'}</small></td>
        <td><span className={`health-badge health-${firm.identity_confidence === 'VERIFY' || firm.identity_confidence === 'UNRESOLVED' ? 'warning' : 'healthy'}`}>{firm.identity_confidence}</span><small>{label(firm.resolution_method)}</small></td>
        <td className="row-arrow">›</td>
      </tr>)}</tbody></table></div>}

      <div className="firm-master-footer">
        <span><strong>Serviced</strong> requires explicit DWT provider/laboratory evidence. <strong>Related</strong> can also include procurement or exact-property project roles and is not an incumbent-service claim.</span>
        <div className="pagination">
          <button disabled={activePage === 0} onClick={() => setPage(value => Math.max(0, value - 1))}>Previous</button>
          <span>Page {activePage + 1} of {maxPage + 1} · {visible.length ? activePage * PAGE_SIZE + 1 : 0}–{Math.min((activePage + 1) * PAGE_SIZE, sorted.length)}</span>
          <button disabled={activePage === maxPage} onClick={() => setPage(value => Math.min(maxPage, value + 1))}>Next</button>
        </div>
      </div>
    </div>}
  </section>
}
