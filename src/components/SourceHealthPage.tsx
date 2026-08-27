import { useEffect, useState } from 'react'
import type { SystemsPayload } from '../types/data'
import type { ProcurementBundle, ProcurementSourceHealth } from '../types/procurement'
import { loadProcurement } from '../data/api'
import { formatTimestamp } from '../domain/labels'
import { ShareButton } from './ShareButton'

const number = new Intl.NumberFormat('en-US')

function procurementHealthRows(procurement: ProcurementBundle | null): ProcurementSourceHealth[] {
  if (!procurement) return []
  return [procurement.cityRecord.source_health, ...Object.values(procurement.checkbook.source_health)]
}

export function SourceHealthPage({ payload }: { payload: SystemsPayload }) {
  const [procurement, setProcurement] = useState<ProcurementBundle | null>(null)
  const [procurementError, setProcurementError] = useState<string | null>(null)

  useEffect(() => {
    loadProcurement()
      .then(setProcurement)
      .catch(error => setProcurementError(error instanceof Error ? error.message : 'Unable to load procurement source health'))
  }, [])

  const health = payload.metadata.source_health ?? []
  const procurementHealth = procurementHealthRows(procurement)
  const healthy = health.filter(source => source.status === 'HEALTHY').length
  const warning = health.filter(source => source.status === 'WARNING').length
  const failed = health.filter(source => source.status === 'FAILED').length
  const coverages = health.map(source => source.coverage_percentage).filter((value): value is number => value != null)
  const averageCoverage = coverages.length > 0 ? coverages.reduce((sum, value) => sum + value, 0) / coverages.length : null
  const retrievedRows = health.reduce((sum, source) => sum + source.retrieved_record_count, 0)
  const procurementRecords = procurementHealth.reduce((sum, source) => sum + source.record_count, 0)

  return <section className="product-page source-health-page">
    <div className="product-page-heading">
      <div><span className="page-kicker">New York City · data trust</span><h1>Source Health &amp; Coverage</h1><p>Freshness, coverage and join health for the source-backed account and procurement intelligence shown across TowerSignal.</p></div>
      <div className="page-actions"><ShareButton label="Share this view" /></div>
    </div>

    <div className="reference-metric-grid source-health-metrics">
      <article><span className="reference-metric-icon success">✓</span><div><small>Healthy account sources</small><strong>{healthy}/{health.length || '—'}</strong><span>{failed > 0 ? `${failed} failed` : 'No failed sources'}</span></div></article>
      <article><span className="reference-metric-icon warning">◷</span><div><small>Warnings</small><strong>{warning}</strong><span>Require review, not silent fallback</span></div></article>
      <article><span className="reference-metric-icon">◎</span><div><small>Average account coverage</small><strong>{averageCoverage == null ? '—' : `${averageCoverage.toFixed(1)}%`}</strong><span>Across sources publishing coverage</span></div></article>
      <article><span className="reference-metric-icon success">⌂</span><div><small>NYC accounts</small><strong>{number.format(payload.summary.registered_systems)}</strong><span>Current normalized systems</span></div></article>
      <article><span className="reference-metric-icon">▤</span><div><small>Procurement source rows</small><strong>{procurement ? number.format(procurementRecords) : '—'}</strong><span>City Record + Checkbook scoped rows</span></div></article>
    </div>

    {health.length === 0 ? <div className="reference-empty-state"><strong>Source-health metrics are not available in this payload.</strong><span>TowerSignal will not infer a healthy state when source diagnostics are missing.</span></div> : <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>{health.length} account-intelligence sources</strong><span>Generated {formatTimestamp(payload.metadata.generated_at)}</span></div></div>
      <div className="reference-table-scroll"><table className="reference-table source-health-table"><thead><tr><th>Source</th><th>Status</th><th>Coverage</th><th>Retrieved</th><th>Normalized</th><th>Matched</th><th>Attached</th><th>Represented</th><th>Health note</th></tr></thead><tbody>{health.map(source => <tr key={source.source_key}>
        <td><strong>{source.name}</strong><small>{source.dataset_id} · {source.entity_unit}</small></td>
        <td><span className={`health-badge health-${source.status.toLowerCase()}`}>{source.status}</span></td>
        <td><strong>{source.coverage_percentage == null ? 'n/a' : `${source.coverage_percentage.toFixed(1)}%`}</strong>{source.coverage_change_percentage_points != null && <small>{source.coverage_change_percentage_points >= 0 ? '+' : ''}{source.coverage_change_percentage_points.toFixed(1)} pp vs prior</small>}</td>
        <td>{number.format(source.retrieved_record_count)}</td>
        <td>{number.format(source.normalized_entity_count)}</td>
        <td>{number.format(source.matched_entity_count)}</td>
        <td>{number.format(source.attached_entity_count)}</td>
        <td>{number.format(source.displayed_entity_count)}</td>
        <td><span>{source.coverage_note}</span>{source.status_reasons.length > 0 && <small>{source.status_reasons.join(' · ')}</small>}</td>
      </tr>)}</tbody></table></div>
    </div>}

    <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>Procurement sources</strong><span>Retrieval, normalization and linkage remain separate from account-source coverage.</span></div></div>
      {procurementError ? <div className="reference-empty-state"><strong>Procurement source health unavailable.</strong><span>{procurementError}</span><span>No healthy status is inferred when the production procurement payload cannot be loaded.</span></div> : !procurement ? <div className="reference-empty-state"><strong>Loading procurement source health…</strong></div> : <div className="reference-table-scroll"><table className="reference-table procurement-health-table"><thead><tr><th>Source</th><th>Status</th><th>Source rows</th><th>Relevant</th><th>Contracts</th><th>Notices</th><th>Companies resolved</th><th>Vendors unresolved</th><th>Facility links</th><th>Exact tower links</th><th>Guards</th></tr></thead><tbody>{procurementHealth.map(source => <tr key={source.source}>
        <td><strong>{source.source}</strong><small>{source.freshness ?? 'freshness not published'}</small></td>
        <td><span className={`health-badge health-${source.status.toLowerCase()}`}>{source.status}</span></td>
        <td>{number.format(source.record_count)}</td>
        <td>{number.format(source.relevant_record_count)}</td>
        <td>{number.format(source.normalized_contract_count)}</td>
        <td>{number.format(source.normalized_notice_count)}</td>
        <td>{number.format(source.resolved_company_count)}</td>
        <td>{number.format(source.unresolved_vendor_count)}</td>
        <td>{number.format(source.facility_link_count)}</td>
        <td>{number.format(source.exact_tower_link_count)}</td>
        <td><span>{source.pagination_complete ? 'Pagination complete' : 'Pagination incomplete'}</span><small>{source.schema_valid ? 'Schema valid' : 'Schema invalid'}</small></td>
      </tr>)}</tbody></table></div>}
    </div>

    <div className="source-health-footnote">Source health distinguishes expected scope limits from unexpected data loss. Procurement rows remain unlinked to cooling-tower accounts until an exact or explicitly reviewed facility relationship is available.</div>
  </section>
}
