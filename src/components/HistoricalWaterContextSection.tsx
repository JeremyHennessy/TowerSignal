import { formatDate, formatTimestamp } from '../domain/labels'
import type { SystemDetail } from '../types/data'

const number = new Intl.NumberFormat('en-US')

function categoryCounts(values: Record<string, number>): string {
  const rows = Object.entries(values).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  return rows.length ? rows.map(([label, count]) => `${label.replaceAll('_', ' ')}: ${number.format(count)}`).join(' · ') : '—'
}

export function HistoricalWaterContextSection({ detail }: { detail: SystemDetail }) {
  const context = detail.nyc_historical_water_context
  if (!context) return null
  const summary = context.summary
  return <section className="building-water-signals-section historical-water-context-section">
    <h3>Historical water context</h3>
    <div className="property-coverage-callout">
      <strong>2010–2024 reported building-water history</strong>
      <p>This is long-run property context only. It is not a current condition, current sales trigger, compliance finding, or provider assignment.</p>
    </div>
    <dl className="identity-grid">
      <div><dt>Reported requests</dt><dd>{number.format(summary.request_count)}</dd></div>
      <div><dt>Years observed</dt><dd>{number.format(summary.year_count)}</dd></div>
      <div><dt>First reported</dt><dd>{summary.first_reported_date ? formatDate(summary.first_reported_date) : '—'}</dd></div>
      <div><dt>Latest historical</dt><dd>{summary.latest_reported_date ? formatDate(summary.latest_reported_date) : '—'}</dd></div>
      <div><dt>Recurrent history</dt><dd>{summary.recurrent_history ? 'Yes' : 'No'}</dd></div>
      <div><dt>2024 activity</dt><dd>{summary.has_2024_activity ? 'Yes' : 'No'}</dd></div>
    </dl>
    <p className="microcopy">Category mix: {categoryCounts(summary.category_counts)}</p>
    <p className="microcopy">Observed years: {summary.years.join(', ') || '—'}</p>
    <p className="microcopy">{context.evidence_boundaries.historical_not_current} {context.evidence_boundaries.property_link} {context.evidence_boundaries.raw_rows} {context.evidence_boundaries.provider} Cache generated {context.source.generated_at ? formatTimestamp(context.source.generated_at) : 'time unavailable'}.</p>
  </section>
}
