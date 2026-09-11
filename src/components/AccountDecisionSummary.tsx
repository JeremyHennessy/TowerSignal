import type { ChangeEvent } from '../types/history'
import type { SystemDetail, SystemSummary } from '../types/data'
import type { WorkflowAccountState } from '../types/workflow'
import { formatDate, signalLabel } from '../domain/labels'

function changeLabel(value: string) {
  return value.replaceAll('_', ' ').toLowerCase().replace(/(^|\s)\S/g, match => match.toUpperCase())
}

function contactLabel(detail: SystemDetail) {
  const contacts = detail.hpd_registration?.contacts ?? []
  const preferred = contacts.find(contact => /agent|head officer|corporate owner|individual owner/i.test(contact.type ?? '')) ?? contacts[0]
  if (!preferred) return 'No public HPD contact match'
  return preferred.corporation_name ?? preferred.person_name ?? preferred.description ?? preferred.type ?? 'HPD contact published'
}

function projectLabel(detail: SystemDetail) {
  const jobs = detail.dob_activity_history ?? []
  if (!jobs.length) return 'No exact-BBL DOB filing match'
  const latest = jobs.find(job => job.activity_date)?.activity_date
  return `${jobs.length.toLocaleString()} filing${jobs.length === 1 ? '' : 's'}${latest ? ` · latest ${formatDate(latest)}` : ''}`
}

function nextActionLabel(account: WorkflowAccountState | undefined) {
  if (!account) return 'No private workflow state'
  if (account.next_action_date) return `${formatDate(account.next_action_date)} · ${account.status}`
  return `${account.status} · no date`
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
  const whyNow = row.recent_confirmed_violation
    ? `Confirmed recent violation · ${signalLabel(row.primary_signal)}`
    : signalLabel(row.primary_signal)
  const scoreDrivers = row.score_components.slice(0, 4)

  return <section className="account-decision-summary" aria-labelledby="account-decision-summary-title">
    <div className="account-decision-head">
      <div><span className="page-kicker">Account decision summary</span><h3 id="account-decision-summary-title">What matters before the next action</h3><p>One operating layer above the source evidence. Every conclusion below stays tied to the current public snapshot or private workflow state.</p></div>
      <div className="account-decision-score"><strong>{row.priority_score}</strong><span>Priority</span><small>{row.evidence_confidence.replaceAll('_', ' ')}</small></div>
    </div>

    <div className="account-decision-grid">
      <article className="urgent"><small>Why now</small><strong>{whyNow}</strong><span>{row.days_since_latest_sample == null ? 'Sampling age unavailable' : `${row.days_since_latest_sample.toLocaleString()} days since latest public sample`}</span></article>
      <article><small>Account scale</small><strong>{row.active_equipment.toLocaleString()} active unit{row.active_equipment === 1 ? '' : 's'}</strong><span>{row.planimetric_building_tower_count ? `${row.planimetric_building_tower_count} mapped roof footprint${row.planimetric_building_tower_count === 1 ? '' : 's'}` : 'No mapped roof footprint in current summary'}</span></article>
      <article><small>Recent change</small><strong>{historyEvents.length ? `${historyEvents.length} observed change${historyEvents.length === 1 ? '' : 's'}` : 'No preserved recent change'}</strong><span>{latestChange ? `${changeLabel(latestChange.event_type)} · ${formatDate(latestChange.detected_at)}` : 'No TowerSignal change in the current history set'}</span></article>
      <article><small>Contact path</small><strong>{contactLabel(detail)}</strong><span>{(detail.hpd_registration?.contacts.length ?? 0).toLocaleString()} published HPD contact row{detail.hpd_registration?.contacts.length === 1 ? '' : 's'}</span></article>
      <article><small>Project activity</small><strong>{projectLabel(detail)}</strong><span>{row.dob_recent_activity_count ? `${row.dob_recent_activity_count} recent lifecycle update${row.dob_recent_activity_count === 1 ? '' : 's'}` : 'No recent lifecycle update in summary'}</span></article>
      <article><small>Next action</small><strong>{nextActionLabel(workflowAccount)}</strong><span>{workflowAccount?.note ? workflowAccount.note : 'Use Workflow to set private follow-up context'}</span></article>
    </div>

    <div className="account-score-drivers">
      <span>Score drivers</span>
      {scoreDrivers.length ? scoreDrivers.map((component, index) => <div key={`${component.reason}-${index}`}><strong>+{component.points}</strong><span>{component.reason}</span></div>) : <div><strong>0</strong><span>No priority points assigned</span></div>}
    </div>
  </section>
}
