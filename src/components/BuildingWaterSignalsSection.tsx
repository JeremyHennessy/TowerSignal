import { formatDate, formatTimestamp } from '../domain/labels'
import type { SystemDetail } from '../types/data'

const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 })

function text(row: Record<string, unknown>, key: string): string {
  const value = row[key]
  return value == null || value === '' ? '—' : String(value)
}

function dateText(row: Record<string, unknown>, ...keys: string[]): string {
  for (const key of keys) {
    const value = row[key]
    if (typeof value === 'string' && value.trim()) return formatDate(value)
  }
  return '—'
}

function metric(value: number): string {
  return number.format(value)
}

function categoryCounts(values: Record<string, number>): string {
  const rows = Object.entries(values).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  return rows.length ? rows.map(([label, count]) => `${label}: ${metric(count)}`).join(' · ') : '—'
}

function waterUse(row: Record<string, unknown>, key: string): string {
  const value = row[key]
  return typeof value === 'number' ? `${number.format(value)} kgal` : text(row, key)
}

export function BuildingWaterSignalsSection({ detail }: { detail: SystemDetail }) {
  const context = detail.nyc_building_water_signals
  return <section className="building-water-signals-section">
    <h3>NYC building-water signals</h3>
    {!context ? <>
      <div className="empty-inline">No exact-BBL/BIN NYC 311, HPD, DOB or LL84 building-water signal was attached to this cooling-tower property.</div>
      <p className="microcopy">Address text, street-infrastructure complaints and multi-identifier LL84 benchmarking rows are not used as fallback account evidence.</p>
    </> : <>
      <dl className="identity-grid">
        <div><dt>Exact property signals</dt><dd>{metric(context.summary.record_count)}</dd></div>
        <div><dt>311 building requests</dt><dd>{metric(context.summary.water_311_building_signal_count)}</dd></div>
        <div><dt>Open HPD water violations</dt><dd>{metric(context.summary.hpd_open_water_violation_count)}</dd></div>
        <div><dt>DOB water work records</dt><dd>{metric(context.summary.dob_water_job_filing_count + context.summary.dob_water_permit_count)}</dd></div>
        <div><dt>LL84 water benchmarks</dt><dd>{metric(context.summary.ll84_water_benchmark_count)}</dd></div>
        <div><dt>Latest observation</dt><dd>{context.summary.latest_observation_date ? formatDate(context.summary.latest_observation_date) : '—'}</dd></div>
      </dl>
      <p className="microcopy">Category mix: {categoryCounts(context.summary.category_counts)}</p>

      {context.water_311_requests.length > 0 && <details className="domestic-water-history" open>
        <summary>311 building-water service requests · {metric(context.water_311_requests.length)}</summary>
        <div className="signal-list">{context.water_311_requests.slice(0, 8).map((row, index) => <article className="signal-card" key={`${text(row, 'request_id')}-${index}`}>
          <div className="signal-card-head"><strong>{text(row, 'category')}</strong><span>{dateText(row, 'created_date')}</span></div>
          <p>{[text(row, 'complaint_type'), text(row, 'descriptor'), text(row, 'descriptor_2')].filter(value => value !== '—').join(' · ') || 'No complaint detail published.'}</p>
          <dl className="identity-grid"><div><dt>Status</dt><dd>{text(row, 'status')}</dd></div><div><dt>Request ID</dt><dd>{text(row, 'request_id')}</dd></div><div><dt>BBL</dt><dd>{text(row, 'bbl')}</dd></div><div><dt>Linkage</dt><dd>{text(row, 'property_link_confidence')}</dd></div></dl>
          {text(row, 'resolution_description') !== '—' && <p className="microcopy">{text(row, 'resolution_description')}</p>}
        </article>)}</div>
      </details>}

      {context.hpd_open_water_violations.length > 0 && <details className="domestic-water-history" open>
        <summary>HPD open water/plumbing violations · {metric(context.hpd_open_water_violations.length)}</summary>
        <div className="signal-list">{context.hpd_open_water_violations.slice(0, 8).map((row, index) => <article className="signal-card" key={`${text(row, 'violation_id')}-${index}`}>
          <div className="signal-card-head"><strong>{text(row, 'category')}</strong><span>{dateText(row, 'inspection_date', 'current_status_date')}</span></div>
          <p>{text(row, 'nov_description')}</p>
          <dl className="identity-grid"><div><dt>Class</dt><dd>{text(row, 'class')}</dd></div><div><dt>Status</dt><dd>{text(row, 'current_status')}</dd></div><div><dt>BBL/BIN</dt><dd>{[text(row, 'bbl'), text(row, 'bin')].filter(value => value !== '—').join(' / ') || '—'}</dd></div><div><dt>Linkage</dt><dd>{text(row, 'property_link_confidence')}</dd></div></dl>
        </article>)}</div>
      </details>}

      {(context.dob_water_job_filings.length + context.dob_water_permits.length) > 0 && <details className="domestic-water-history" open>
        <summary>DOB water work roles · {metric(context.dob_water_job_filings.length + context.dob_water_permits.length)}</summary>
        <div className="signal-list">{[...context.dob_water_job_filings, ...context.dob_water_permits].slice(0, 8).map((row, index) => <article className="signal-card" key={`${text(row, 'activity_id')}-${index}`}>
          <div className="signal-card-head"><strong>{text(row, 'category')}</strong><span>{dateText(row, 'issued_date', 'approved_date', 'filing_date')}</span></div>
          <p>{text(row, 'job_description')}</p>
          <dl className="identity-grid"><div><dt>Record</dt><dd>{text(row, 'source_record_id') !== '—' ? text(row, 'source_record_id') : text(row, 'job_filing_number')}</dd></div><div><dt>Applicant business</dt><dd>{text(row, 'applicant_business_raw')}</dd></div><div><dt>Role evidence</dt><dd>{text(row, 'relationship_evidence')}</dd></div><div><dt>Service assignment</dt><dd>{text(row, 'service_assignment_confidence')}</dd></div></dl>
        </article>)}</div>
      </details>}

      {context.ll84_water_benchmarks.length > 0 && <details className="domestic-water-history">
        <summary>LL84 water benchmarking rows · {metric(context.ll84_water_benchmarks.length)}</summary>
        <div className="signal-list">{context.ll84_water_benchmarks.slice(0, 8).map((row, index) => <article className="signal-card" key={`${text(row, 'benchmark_id')}-${index}`}>
          <div className="signal-card-head"><strong>{text(row, 'property_name') !== '—' ? text(row, 'property_name') : 'LL84 water benchmark'}</strong><span>{text(row, 'report_year')}</span></div>
          <dl className="identity-grid"><div><dt>Property ID</dt><dd>{text(row, 'property_id')}</dd></div><div><dt>Metered areas</dt><dd>{text(row, 'metered_areas_water')}</dd></div><div><dt>All water use</dt><dd>{waterUse(row, 'water_use_all_sources_kgal')}</dd></div><div><dt>Municipal potable total</dt><dd>{waterUse(row, 'municipal_potable_total_kgal')}</dd></div></dl>
        </article>)}</div>
      </details>}

      <p className="microcopy">{context.evidence_boundaries.property_link} {context.evidence_boundaries.roles} {context.evidence_boundaries.ll84} Cache generated {context.source.generated_at ? formatTimestamp(context.source.generated_at) : 'time unavailable'}.</p>
    </>}
  </section>
}
