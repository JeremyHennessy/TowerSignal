import type { ChangeEvent } from '../types/history'
import type { Metadata, SystemDetail, SystemSummary } from '../types/data'
import { formatDate, formatTimestamp } from '../domain/labels'

const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

function display(value: string | null | undefined): string {
  return value?.trim() || 'Not published'
}

function latestInspection(detail: SystemDetail) {
  return [...detail.inspection_history]
    .sort((left, right) => (right.inspection_date ?? '').localeCompare(left.inspection_date ?? ''))[0]
}

function latestViolationInspection(detail: SystemDetail) {
  return [...detail.inspection_history]
    .filter(item => item.violation_count > 0)
    .sort((left, right) => (right.inspection_date ?? '').localeCompare(left.inspection_date ?? ''))[0]
}

function latestOathCase(detail: SystemDetail) {
  return [...(detail.oath_case_history ?? [])]
    .sort((left, right) => (right.violation_date ?? right.hearing_date ?? '').localeCompare(left.violation_date ?? left.hearing_date ?? ''))[0]
}

export function ClientSiteReport({
  row,
  detail,
  metadata,
  historyEvents,
}: {
  row: SystemSummary
  detail: SystemDetail
  metadata: Metadata
  historyEvents: ChangeEvent[]
}) {
  const inspection = latestInspection(detail)
  const violationInspection = latestViolationInspection(detail)
  const oathCase = latestOathCase(detail)
  const missingSample = detail.signals.find(signal => signal.type === 'NO_PUBLIC_SAMPLE_DATE')
  const currentSignals = detail.signals.slice(0, 6)
  const owner = detail.building_context?.owner_name ?? row.pluto_owner_name ?? null
  const propertyBbl = detail.identity.property_bbl ?? row.property_bbl ?? detail.identity.bbl ?? row.bbl ?? null
  const registryBbl = detail.identity.registry_bbl ?? row.registry_bbl ?? null
  const latestHistory = [...historyEvents].sort((a, b) => b.detected_at.localeCompare(a.detected_at))[0]
  const sourceCount = detail.metadata.sources.length
  const buildingArea = detail.building_context?.building_area_sqft ?? row.pluto_building_area_sqft ?? null
  const mappedTowers = detail.planimetric_building_tower_features?.length ?? row.planimetric_building_tower_count ?? 0

  return <article className="client-pdf-report" aria-label="Client-ready site intelligence report" aria-hidden="true">
    <header className="client-pdf-cover">
      <div className="client-pdf-brand"><span>TS</span><strong>TowerSignal</strong></div>
      <div className="client-pdf-cover-copy">
        <p className="client-pdf-kicker">Site Intelligence Report</p>
        <h1>{row.address ?? row.system_id}</h1>
        <p>{row.borough}{row.zip ? ` · ${row.zip}` : ''} · Cooling Tower System {row.system_id}</p>
      </div>
      <div className="client-pdf-cover-meta">
        <div><span>Report generated</span><strong>{formatTimestamp(detail.metadata.generated_at)}</strong></div>
        <div><span>Priority</span><strong>{row.priority_score}/100</strong></div>
        <div><span>Evidence confidence</span><strong>{row.evidence_confidence.replaceAll('_', ' ')}</strong></div>
      </div>
    </header>

    <section className="client-pdf-section client-pdf-summary">
      <div className="client-pdf-section-heading">
        <div><span>01</span><h2>Site snapshot</h2></div>
        <p>Current public-record view of the registered cooling-tower system and attached property evidence.</p>
      </div>
      <div className="client-pdf-stat-grid">
        <div><small>Registered equipment</small><strong>{row.active_equipment.toLocaleString()}</strong><span>active unit{row.active_equipment === 1 ? '' : 's'}</span></div>
        <div><small>Mapped tower features</small><strong>{mappedTowers.toLocaleString()}</strong><span>exact-BIN physical context</span></div>
        <div><small>Latest public sample</small><strong>{detail.sample_history.latest_sample_date ? formatDate(detail.sample_history.latest_sample_date) : 'Not published'}</strong><span>{detail.sample_history.sample_count.toLocaleString()} reported date{detail.sample_history.sample_count === 1 ? '' : 's'}</span></div>
        <div><small>NYC Health inspections</small><strong>{detail.inspection_history.length.toLocaleString()}</strong><span>{violationInspection ? `latest cited ${formatDate(violationInspection.inspection_date)}` : 'no joined cited inspection'}</span></div>
        <div><small>Property owner</small><strong>{display(owner)}</strong><span>{propertyBbl ? `Property BBL ${propertyBbl}` : 'exact property BBL not available'}</span></div>
        <div><small>Building area</small><strong>{buildingArea == null ? 'Not published' : `${number.format(buildingArea)} sq ft`}</strong><span>{detail.building_context ? 'NYC DCP PLUTO' : 'property context unavailable'}</span></div>
      </div>
    </section>

    <section className="client-pdf-section">
      <div className="client-pdf-section-heading">
        <div><span>02</span><h2>Current findings</h2></div>
        <p>TowerSignal commercial timing signals are derived from public records and remain distinct from legal or health determinations.</p>
      </div>
      {missingSample && <div className="client-pdf-alert">
        <strong>VERIFY · No public Legionella sample date</strong>
        <p>{missingSample.reason}</p>
      </div>}
      <div className="client-pdf-findings">
        {currentSignals.length ? currentSignals.map(signal => <div key={signal.type}>
          <div><strong>{signal.title}</strong><span>{signal.evidence_confidence.replaceAll('_', ' ')}</span></div>
          <p>{signal.reason}</p>
          {signal.date && <small>Source date {formatDate(signal.date)}</small>}
        </div>) : <div className="client-pdf-empty"><strong>No current priority signal generated.</strong><p>Review the underlying source evidence before drawing conclusions about current operating or compliance status.</p></div>}
      </div>
    </section>

    <section className="client-pdf-section client-pdf-page-break">
      <div className="client-pdf-section-heading">
        <div><span>03</span><h2>Compliance &amp; sampling evidence</h2></div>
        <p>Published sampling, inspection and adjudication records joined to this system using TowerSignal's documented identity rules.</p>
      </div>
      <div className="client-pdf-two-column">
        <div className="client-pdf-card">
          <h3>Sampling record</h3>
          <dl>
            <div><dt>Reported sample dates</dt><dd>{detail.sample_history.sample_count.toLocaleString()}</dd></div>
            <div><dt>Latest public sample</dt><dd>{detail.sample_history.latest_sample_date ? formatDate(detail.sample_history.latest_sample_date) : 'Not published'}</dd></div>
            <div><dt>Latest interval</dt><dd>{detail.sample_history.latest_sample_interval_days == null ? 'Not available' : `${detail.sample_history.latest_sample_interval_days.toLocaleString()} days`}</dd></div>
          </dl>
          <p className="client-pdf-note">A missing or old public sample date is a verification signal. It does not establish that sampling did not occur.</p>
        </div>
        <div className="client-pdf-card">
          <h3>Inspection record</h3>
          <dl>
            <div><dt>Joined inspections</dt><dd>{detail.inspection_history.length.toLocaleString()}</dd></div>
            <div><dt>Latest inspection</dt><dd>{inspection ? formatDate(inspection.inspection_date) : 'Not published'}</dd></div>
            <div><dt>Latest cited inspection</dt><dd>{violationInspection ? formatDate(violationInspection.inspection_date) : 'None in joined history'}</dd></div>
          </dl>
          {violationInspection?.violations[0] && <p className="client-pdf-note">{violationInspection.violations[0].violation_text ?? violationInspection.violations[0].citation_text ?? 'Published violation citation attached.'}</p>}
        </div>
      </div>
      <div className="client-pdf-two-column">
        <div className="client-pdf-card">
          <h3>OATH lifecycle</h3>
          {oathCase ? <dl>
            <div><dt>Ticket</dt><dd>{oathCase.ticket_number}</dd></div>
            <div><dt>Hearing status</dt><dd>{display(oathCase.hearing_status)}</dd></div>
            <div><dt>Hearing result</dt><dd>{display(oathCase.hearing_result)}</dd></div>
            <div><dt>Penalty imposed</dt><dd>{oathCase.penalty_imposed == null ? 'Not published' : money.format(oathCase.penalty_imposed)}</dd></div>
          </dl> : <p>No OATH case was exact-matched to this system's published NYC Health summons numbers.</p>}
        </div>
        <div className="client-pdf-card">
          <h3>Recent observed change</h3>
          {latestHistory ? <dl>
            <div><dt>Observed</dt><dd>{formatTimestamp(latestHistory.detected_at)}</dd></div>
            <div><dt>Event</dt><dd>{latestHistory.event_type.replaceAll('_', ' ')}</dd></div>
            <div><dt>Source</dt><dd>{latestHistory.source}</dd></div>
          </dl> : <p>No TowerSignal change has been observed for this system in the retained history window.</p>}
        </div>
      </div>
    </section>

    <section className="client-pdf-section">
      <div className="client-pdf-section-heading">
        <div><span>04</span><h2>Property &amp; project context</h2></div>
        <p>Property information is attached only where source-native identifiers support the join.</p>
      </div>
      <div className="client-pdf-two-column">
        <div className="client-pdf-card">
          <h3>Identity</h3>
          <dl>
            <div><dt>System ID</dt><dd>{row.system_id}</dd></div>
            <div><dt>BIN</dt><dd>{display(detail.identity.bin)}</dd></div>
            <div><dt>Property BBL</dt><dd>{display(propertyBbl)}</dd></div>
            <div><dt>Registry/base BBL</dt><dd>{registryBbl && registryBbl !== propertyBbl ? registryBbl : 'Same as property BBL'}</dd></div>
            <div><dt>Owner</dt><dd>{display(owner)}</dd></div>
          </dl>
        </div>
        <div className="client-pdf-card">
          <h3>Commercial context</h3>
          <dl>
            <div><dt>HPD contact rows</dt><dd>{(detail.hpd_registration?.contacts.length ?? 0).toLocaleString()}</dd></div>
            <div><dt>DOB NOW filings</dt><dd>{(detail.dob_activity_history?.length ?? 0).toLocaleString()}</dd></div>
            <div><dt>Recent DOB activity</dt><dd>{(row.dob_recent_activity_count ?? 0).toLocaleString()}</dd></div>
            <div><dt>Explicit cooling-tower filings</dt><dd>{(row.dob_explicit_cooling_tower_count ?? 0).toLocaleString()}</dd></div>
          </dl>
        </div>
      </div>
    </section>

    <section className="client-pdf-section client-pdf-page-break">
      <div className="client-pdf-section-heading">
        <div><span>05</span><h2>Sources &amp; provenance</h2></div>
        <p>{sourceCount.toLocaleString()} source dataset{sourceCount === 1 ? '' : 's'} contribute to the generated site record.</p>
      </div>
      <div className="client-pdf-source-list">
        {detail.metadata.sources.map(source => <div key={source.dataset_id}>
          <strong>{source.name}</strong>
          <span>{source.dataset_id}</span>
          <small>{source.source_record_count.toLocaleString()} source row{source.source_record_count === 1 ? '' : 's'}{source.matched_record_count != null ? ` · ${source.matched_record_count.toLocaleString()} exact-matched` : ''} · retrieved {formatTimestamp(source.retrieved_at)}</small>
        </div>)}
      </div>
      <div className="client-pdf-methodology">
        <strong>Interpretation boundary</strong>
        <p>TowerSignal compiles public regulatory, property and infrastructure records for commercial research. A signal is not a legal, engineering, health or compliance determination. Verify current operating, testing, maintenance and remediation status directly before relying on the report.</p>
        <p>Rules {metadata.rules_version} · Priority model {metadata.priority_model_version} · Site record generated {formatTimestamp(detail.metadata.generated_at)}</p>
      </div>
    </section>

    <footer className="client-pdf-footer">
      <span>TowerSignal · Site Intelligence Report</span>
      <span>{row.address ?? row.system_id} · System {row.system_id}</span>
    </footer>
  </article>
}
