import type { SystemsPayload } from '../types/data'
import { formatTimestamp } from '../domain/labels'
import { ShareButton } from './ShareButton'

const number = new Intl.NumberFormat('en-US')

export function SourceHealthPage({ payload }: { payload: SystemsPayload }) {
  const health = payload.metadata.source_health ?? []
  const healthy = health.filter(source => source.status === 'HEALTHY').length
  const warning = health.filter(source => source.status === 'WARNING').length
  const failed = health.filter(source => source.status === 'FAILED').length
  const coverages = health.map(source => source.coverage_percentage).filter((value): value is number => value != null)
  const averageCoverage = coverages.length > 0 ? coverages.reduce((sum, value) => sum + value, 0) / coverages.length : null
  const retrievedRows = health.reduce((sum, source) => sum + source.retrieved_record_count, 0)

  return <section className="product-page source-health-page">
    <div className="product-page-heading">
      <div><span className="page-kicker">New York City · data trust</span><h1>Source Health &amp; Coverage</h1><p>Freshness, coverage and join health for the source-backed account intelligence shown across TowerSignal.</p></div>
      <div className="page-actions"><ShareButton label="Share this view" /></div>
    </div>

    <div className="reference-metric-grid source-health-metrics">
      <article><span className="reference-metric-icon success">✓</span><div><small>Healthy sources</small><strong>{healthy}/{health.length || '—'}</strong><span>{failed > 0 ? `${failed} failed` : 'No failed sources'}</span></div></article>
      <article><span className="reference-metric-icon warning">◷</span><div><small>Warnings</small><strong>{warning}</strong><span>Require review, not silent fallback</span></div></article>
      <article><span className="reference-metric-icon">◎</span><div><small>Average coverage</small><strong>{averageCoverage == null ? '—' : `${averageCoverage.toFixed(1)}%`}</strong><span>Across sources publishing coverage</span></div></article>
      <article><span className="reference-metric-icon success">⌂</span><div><small>NYC accounts</small><strong>{number.format(payload.summary.registered_systems)}</strong><span>Current normalized systems</span></div></article>
      <article><span className="reference-metric-icon">▤</span><div><small>Retrieved rows</small><strong>{number.format(retrievedRows)}</strong><span>Across health-tracked sources</span></div></article>
    </div>

    {health.length === 0 ? <div className="reference-empty-state"><strong>Source-health metrics are not available in this payload.</strong><span>TowerSignal will not infer a healthy state when source diagnostics are missing.</span></div> : <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>{health.length} tracked sources</strong><span>Generated {formatTimestamp(payload.metadata.generated_at)}</span></div></div>
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

    <div className="source-health-footnote">Source health distinguishes expected scope limits from unexpected data loss. A warning or failed source should remain visible rather than being replaced with fixture data.</div>
  </section>
}
