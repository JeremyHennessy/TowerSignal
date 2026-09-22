import type { ChangeEvent } from '../types/history'
import type { SystemDetail, SystemSummary } from '../types/data'
import type { WorkflowAccountState } from '../types/workflow'
import { formatDate, signalLabel } from '../domain/labels'

const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

function changeLabel(value: string) {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, match => match.toUpperCase())
}

function nextActionLabel(account: WorkflowAccountState | undefined) {
  if (!account) return 'No private follow-up set'
  if (account.next_action_date) return `${formatDate(account.next_action_date)} · ${account.status}`
  return `${account.status} · no follow-up date`
}

function latestViolation(detail: SystemDetail) {
  const inspection = [...detail.inspection_history]
    .filter(item => item.violation_count > 0)
    .sort((left, right) => (right.inspection_date ?? '').localeCompare(left.inspection_date ?? ''))[0]
  return { inspection, violation: inspection?.violations[0] }
}

function infrastructureSummary(detail: SystemDetail) {
  const context = detail.nyc_lead_service_lines
  const first = context?.records[0]
  if (!context || context.summary.record_count === 0) {
    return {
      title: 'No exact-BBL NYC DEP service-line record',
      detail: 'No service-line material is promoted into this account summary.',
    }
  }
  const materials = Object.entries(context.summary.material_counts)
    .filter(([, count]) => count > 0)
    .map(([material, count]) => `${material}${count > 1 ? ` ×${count}` : ''}`)
    .join(' · ')
  return {
    title: `${materials || 'Material published'} · NYC DEP service line`,
    detail: `${context.summary.record_count.toLocaleString()} exact-BBL record${context.summary.record_count === 1 ? '' : 's'}${first?.record_type ? ` · ${first.record_type}` : ''}${first?.city_owned ? ` · city-owned ${first.city_owned}` : ''}`,
  }
}

export function AccountDecisionSummary({
  row,
  detail,
  historyEvents,
  workflowAccount,
}: {
  row: SystemSummary
  detail: SystemDetail
  historyEvents: ChangeEvent[]
  workflowAccount?: WorkflowAccountState
}) {
  const latestChange = [...historyEvents].sort((a, b) => b.detected_at.localeCompare(a.detected_at))[0]
  const scoreDrivers = row.score_components.slice(0, 4)
  const violationEvidence = latestViolation(detail)
  // The trigger label, date and explanation must describe the same evidence.
  // Historic Health violations remain in History; they are not dates for a
  // current building-follow-up or equipment-scale signal.
  const currentSignal = detail.signals.find(signal => signal.type === (row.recent_confirmed_violation ? 'CONFIRMED_RECENT_VIOLATION' : row.primary_signal))
  const violationDate = row.recent_confirmed_violation
    ? currentSignal?.date ?? violationEvidence.inspection?.inspection_date ?? row.latest_violation_date
    : currentSignal?.date ?? null
  const violationText = row.recent_confirmed_violation
    ? violationEvidence.violation?.violation_text ?? violationEvidence.violation?.citation_text ?? row.violation_types[0] ?? currentSignal?.reason ?? 'Review the attached NYC Health evidence.'
    : currentSignal?.reason ?? 'No primary-signal detail is attached. Review the source records before acting.'
  const mappedTowers = detail.planimetric_building_tower_features?.length ?? row.planimetric_building_tower_count ?? 0
  const buildingOutlines = detail.building_footprints?.length ?? row.building_footprint_count ?? 0
  const buildingArea = detail.building_context?.building_area_sqft ?? row.pluto_building_area_sqft ?? null
  const sampleCount = detail.sample_history.sample_count
  const inspectionCount = detail.inspection_history.length
  const missingPublicSampleSignal = detail.signals.find(signal => signal.type === 'NO_PUBLIC_SAMPLE_DATE')
  const owner = detail.building_context?.owner_name ?? row.pluto_owner_name ?? null
  const propertyBbl = detail.identity.property_bbl ?? row.property_bbl ?? detail.identity.bbl ?? row.bbl ?? null
  const registryBbl = detail.identity.registry_bbl ?? row.registry_bbl ?? null
  const identityStatus = detail.identity.bbl_identity_status ?? row.bbl_identity_status ?? ''
  const identityConflict = identityStatus.includes('CONFLICT') || identityStatus.includes('MULTIPLE_MAPPLUTO')
  const reconciledIdentity = identityStatus === 'RECONCILED_REGISTRY_BASE_TO_MAPPLUTO_BBL'
  const propertyTitle = identityConflict
    ? 'Property identity needs review'
    : owner ?? (propertyBbl ? `Property BBL ${propertyBbl}` : 'No exact property identity')
  const propertyDetail = identityConflict
    ? `Registry BBL ${registryBbl ?? 'unavailable'} conflicts with exact-BIN MapPLUTO context. Property-level joins are not treated as complete.`
    : reconciledIdentity
      ? `Property BBL ${propertyBbl} · registry/base BBL ${registryBbl} · exact-BIN MapPLUTO reconciliation`
      : propertyBbl
        ? `Property BBL ${propertyBbl} · NYC DCP PLUTO context`
        : 'TowerSignal does not infer a parcel when no exact source identity is available.'
  const infrastructure = infrastructureSummary(detail)
  const whyNow = row.recent_confirmed_violation ? 'Confirmed recent violation' : signalLabel(row.primary_signal)

  return <section className="account-decision-summary" aria-labelledby="account-decision-summary-title">
    <div className="account-decision-head">
      <div><span className="page-kicker">Account decision summary</span><h3 id="account-decision-summary-title">What matters before the next action</h3><p>Current source-backed view of compliance timing, physical scale, sampling, property identity and private follow-up. Missing source matches stay explicit instead of being inferred.</p></div>
      <div className="account-decision-score"><strong>{row.priority_score}</strong><span>Priority</span><small>{row.evidence_confidence.replaceAll('_', ' ')}</small></div>
    </div>

    <div className="account-decision-grid account-decision-evidence-grid">
      <article className="urgent"><small>Compliance trigger</small><strong>{violationDate ? `${whyNow} · ${formatDate(violationDate)}` : whyNow}</strong><span>{violationText}</span></article>
      <article><small>Cooling-tower footprint</small><strong>{row.active_equipment.toLocaleString()} registered unit{row.active_equipment === 1 ? '' : 's'} · {mappedTowers.toLocaleString()} mapped footprint{mappedTowers === 1 ? '' : 's'}</strong><span>{buildingOutlines ? `${buildingOutlines.toLocaleString()} exact-BIN building outline${buildingOutlines === 1 ? '' : 's'}` : 'No mapped building outline'}{buildingArea ? ` · ${number.format(buildingArea)} sq ft PLUTO building` : ''}</span></article>
      <article className={missingPublicSampleSignal ? 'urgent' : undefined}><small>Sampling &amp; inspections{missingPublicSampleSignal ? ' · VERIFY' : ''}</small><strong>{detail.sample_history.latest_sample_date ? `Latest sample ${formatDate(detail.sample_history.latest_sample_date)}` : missingPublicSampleSignal ? 'No public Legionella sample dates reported' : 'Latest sample date unavailable'}</strong><span>{missingPublicSampleSignal ? `${missingPublicSampleSignal.reason} · ${inspectionCount.toLocaleString()} NYC Health inspection${inspectionCount === 1 ? '' : 's'}` : `${sampleCount.toLocaleString()} reported sample date${sampleCount === 1 ? '' : 's'}${detail.sample_history.latest_sample_interval_days != null ? ` · ${detail.sample_history.latest_sample_interval_days.toLocaleString()}-day latest interval` : ''} · ${inspectionCount.toLocaleString()} NYC Health inspection${inspectionCount === 1 ? '' : 's'}`}</span></article>
      <article className={identityConflict ? 'urgent' : undefined}><small>Property identity{identityConflict ? ' · VERIFY' : ''}</small><strong>{propertyTitle}</strong><span>{propertyDetail}</span></article>
      <article><small>Infrastructure evidence</small><strong>{infrastructure.title}</strong><span>{infrastructure.detail}</span></article>
      <article><small>Next action</small><strong>{nextActionLabel(workflowAccount)}</strong><span>{workflowAccount?.note ? workflowAccount.note : 'Use Summary workflow controls to set private disposition, notes and follow-up timing.'}</span></article>
    </div>

    <div className="account-decision-context" aria-label="Account evidence context">
      <span><strong>{historyEvents.length.toLocaleString()}</strong> preserved TowerSignal change{historyEvents.length === 1 ? '' : 's'}{latestChange ? ` · latest ${changeLabel(latestChange.event_type)} ${formatDate(latestChange.detected_at)}` : ''}</span>
      <span><strong>{(detail.hpd_registration?.contacts.length ?? 0).toLocaleString()}</strong> exact-match HPD contact row{detail.hpd_registration?.contacts.length === 1 ? '' : 's'}</span>
      <span><strong>{(detail.dob_activity_history?.length ?? 0).toLocaleString()}</strong> exact-BBL DOB filing{detail.dob_activity_history?.length === 1 ? '' : 's'}</span>
    </div>

    <div className="account-score-drivers">
      <span>Score drivers</span>
      {scoreDrivers.length ? scoreDrivers.map((component, index) => <div key={`${component.reason}-${index}`}><strong>+{component.points}</strong><span>{component.reason}</span></div>) : <div><strong>0</strong><span>No priority points assigned</span></div>}
    </div>
  </section>
}
