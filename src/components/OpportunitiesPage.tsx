import type { SystemSummary, SystemsPayload } from '../types/data'
import type { AcrisSummaryFields } from '../types/acris'
import { formatDate } from '../domain/labels'
import { ShareButton } from './ShareButton'

const number = new Intl.NumberFormat('en-US')

function signalLabel(value: string): string {
  const labels: Record<string, string> = {
    CONFIRMED_RECENT_VIOLATION: 'Confirmed violation',
    POTENTIAL_SAMPLING_GAP: 'Sampling follow-up',
    NO_PUBLIC_SAMPLE_DATE: 'No public sample date',
    MULTIPLE_ACTIVE_EQUIPMENT: 'Multiple equipment',
    RECENT_NYC_HEALTH_INSPECTION: 'Recent inspection',
    NO_CURRENT_SIGNAL: 'No current timing signal',
  }
  return labels[value] ?? value.replaceAll('_', ' ').toLowerCase()
}

export function OpportunitiesPage({ payload, onOpenAccount }: { payload: SystemsPayload; onOpenAccount: (row: SystemSummary) => void }) {
  const rows = payload.systems
  const highPriority = rows.filter(row => row.priority_score >= 70)
  const sampleFollowUp = rows.filter(row => row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE'))
  const contactReady = rows.filter(row => (row.hpd_contact_count ?? 0) > 0)
  const recentDob = rows.filter(row => (row.dob_recent_activity_count ?? 0) > 0)
  const ranked = [...rows]
    .filter(row => row.priority_score >= 50 || (row.dob_recent_activity_count ?? 0) > 0 || (row.hpd_contact_count ?? 0) > 0)
    .sort((a, b) => b.priority_score - a.priority_score || (b.dob_recent_activity_count ?? 0) - (a.dob_recent_activity_count ?? 0))
    .slice(0, 50)

  return <section className="product-page opportunities-page">
    <div className="product-page-heading">
      <div><span className="page-kicker">New York City · commercial timing</span><h1>Opportunities workspace</h1><p>Prioritize accounts with current public-record timing, contact and project context. Procurement is kept separate until source-backed bid and award records are connected.</p></div>
      <div className="page-actions"><ShareButton label="Share this view" /></div>
    </div>

    <div className="reference-metric-grid">
      <article><span className="reference-metric-icon urgent">↗</span><div><small>High priority</small><strong>{number.format(highPriority.length)}</strong><span>Priority score 70+</span></div></article>
      <article><span className="reference-metric-icon warning">◷</span><div><small>Sampling follow-up</small><strong>{number.format(sampleFollowUp.length)}</strong><span>Gap or missing-date signals</span></div></article>
      <article><span className="reference-metric-icon success">◎</span><div><small>Contact-ready</small><strong>{number.format(contactReady.length)}</strong><span>HPD contacts matched</span></div></article>
      <article><span className="reference-metric-icon">⌁</span><div><small>Recent DOB context</small><strong>{number.format(recentDob.length)}</strong><span>Activity in the last 365 days</span></div></article>
    </div>

    <div className="roadmap-data-banner">
      <div><span className="roadmap-status">ROADMAP DATA</span><strong>Procurement intelligence is not in the current production account payload.</strong><p>City Record and Checkbook NYC are planned for open solicitations, awards, vendors, contract amounts and buying history. TowerSignal does not display illustrative bids as live opportunities.</p></div>
      <div className="roadmap-source-list"><span>City Record</span><span>Checkbook NYC</span><span>Exact property linkage only</span></div>
    </div>

    <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>Current timing opportunities</strong><span>{number.format(ranked.length)} highest-ranked accounts shown from the current source-backed snapshot</span></div></div>
      <div className="reference-table-scroll"><table className="reference-table opportunity-table"><thead><tr><th>Account</th><th>Priority</th><th>Strongest reason</th><th>Equipment</th><th>Contact</th><th>DOB activity</th><th>OATH</th><th>Recorded property activity</th><th>Action</th></tr></thead><tbody>{ranked.map(row => {
        const acris = row as SystemSummary & AcrisSummaryFields
        return <tr key={row.system_id} onClick={() => onOpenAccount(row)}>
          <td><strong>{row.address ?? row.system_id}</strong><small>{[row.borough, row.zip].filter(Boolean).join(' · ')} · {row.system_id}</small></td>
          <td><span className={`priority-pill ${row.priority_score >= 70 ? 'priority-pill-high' : 'priority-pill-medium'}`}>{row.priority_score}</span></td>
          <td><strong>{signalLabel(row.primary_signal)}</strong><small>{row.evidence_confidence}</small></td>
          <td>{row.active_equipment}<small>active</small></td>
          <td>{(row.hpd_contact_count ?? 0) > 0 ? <span className="ready-label">Contact-ready</span> : <span className="muted-label">No HPD contact</span>}</td>
          <td>{row.dob_recent_activity_count ?? 0}<small>{row.latest_dob_activity_date ? `latest ${formatDate(row.latest_dob_activity_date)}` : 'no recent activity'}</small></td>
          <td>{row.oath_case_count ?? 0}<small>{(row.oath_case_count ?? 0) > 0 ? 'exact case match' : 'none matched'}</small></td>
          <td>{acris.acris_recent_document_count ?? 0}<small>recent exact-BBL docs</small></td>
          <td><button className="table-link" onClick={event => { event.stopPropagation(); onOpenAccount(row) }}>Open profile →</button></td>
        </tr>
      })}</tbody></table></div>
    </div>
  </section>
}
