import { formatTimestamp } from '../domain/labels'
import type { SystemDetail } from '../types/data'

function countList(values: Record<string, number>): string {
  const entries = Object.entries(values).filter(([, count]) => count > 0)
  return entries.length ? entries.map(([label, count]) => `${label}: ${count.toLocaleString()}`).join(' · ') : '—'
}

export function LeadServiceLineSection({ detail }: { detail: SystemDetail }) {
  const context = detail.nyc_lead_service_lines
  return <section className="lead-service-line-section">
    <h3>NYC service-line records</h3>
    {!context ? <>
      <div className="empty-inline">No exact-BBL NYC DEP service-line record was attached to this cooling-tower property.</div>
      <p className="microcopy">This section uses exact source-reported DEP BBL only. Address similarity is not used as fallback evidence.</p>
    </> : <>
      <dl className="identity-grid">
        <div><dt>Exact-BBL records</dt><dd>{context.summary.record_count.toLocaleString()}</dd></div>
        <div><dt>Material categories</dt><dd>{countList(context.summary.material_counts)}</dd></div>
        <div><dt>Record types</dt><dd>{countList(context.summary.record_type_counts)}</dd></div>
        <div><dt>City-owned flag</dt><dd>{countList(context.summary.city_owned_counts)}</dd></div>
      </dl>
      <details className="domestic-water-history" open>
        <summary>Source service-line rows · {context.records.length.toLocaleString()}</summary>
        <div className="planimetric-feature-list">
          {context.records.map((record, index) => <article className="planimetric-feature" key={`${record.record_id ?? 'service-line'}-${index}`}>
            <div className="planimetric-feature-head"><strong>{record.material ?? 'Material not published'}</strong><span>{record.record_type ?? 'Record type unavailable'}</span></div>
            <dl className="identity-grid">
              <div><dt>DEP record ID</dt><dd>{record.record_id ?? '—'}</dd></div>
              <div><dt>BBL</dt><dd>{record.bbl ?? '—'}</dd></div>
              <div><dt>Address</dt><dd>{record.address ?? '—'}</dd></div>
              <div><dt>City owned</dt><dd>{record.city_owned ?? '—'}</dd></div>
            </dl>
          </article>)}
        </div>
      </details>
      <p className="microcopy">{context.evidence_boundaries.property_link} {context.evidence_boundaries.material} Source generated {context.source.generated_at ? formatTimestamp(context.source.generated_at) : 'date unavailable'}.</p>
    </>}
  </section>
}
