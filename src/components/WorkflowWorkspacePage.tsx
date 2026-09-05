import type { AcrisSummaryFields } from '../types/acris'
import type { ChangeEvent, ChangesPayload } from '../types/history'
import type { SystemSummary } from '../types/data'
import type { AccountDisposition, WorkflowAccountState, WorkflowMembership, WorkflowSavedView, WorkflowUser, WorkflowWatchlist } from '../types/workflow'
import { formatDate, formatTimestamp } from '../domain/labels'
import { ShareButton } from './ShareButton'

const columns: Array<{ value: AccountDisposition; label: string }> = [
  { value: 'new', label: 'New' },
  { value: 'investigate', label: 'Investigate' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'follow-up', label: 'Follow-up' },
  { value: 'monitor', label: 'Monitor' },
  { value: 'dismissed', label: 'Dismissed' },
]

const number = new Intl.NumberFormat('en-US')

type DomesticWaterSummaryFields = {
  dwt_planimetric_bin_match?: boolean
  dwt_planimetric_tank_count?: number
  dwt_compliance_record_count?: number
  dwt_self_report_record_count?: number
  dwt_latest_status?: string | null
  dwt_latest_reported_tank_count?: number | null
  dwt_latest_activity_type?: string | null
  dwt_latest_activity_year?: string | null
  dwt_latest_self_report_inspection_date?: string | null
  dwt_violation_record_count?: number
}

type WorkflowSystem = SystemSummary & AcrisSummaryFields & DomesticWaterSummaryFields

type CategoryMetric = {
  label: string
  value: number
  note: string
}

type AttentionItem = {
  row: WorkflowSystem
  account: WorkflowAccountState | undefined
  events: ChangeEvent[]
}

function statusLabel(value: AccountDisposition | undefined) {
  if (!value) return 'No workflow status'
  return columns.find(column => column.value === value)?.label ?? value
}

function isSamplingFollowUp(row: WorkflowSystem) {
  return row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE')
}

function isDue(account: WorkflowAccountState | undefined, today: string) {
  return Boolean(account?.next_action_date && account.next_action_date <= today)
}

function isComplianceChange(event: ChangeEvent) {
  return event.event_type.startsWith('SAMPLE')
    || event.event_type.startsWith('SAMPLING')
    || event.event_type.startsWith('INSPECTION')
    || event.event_type.startsWith('VIOLATION')
    || event.event_type.startsWith('OATH_')
}

function isPropertyProjectChange(event: ChangeEvent) {
  return event.event_type.startsWith('HPD_')
    || event.event_type.startsWith('PLUTO_')
    || event.event_type.startsWith('DOB_')
}

function attentionReasons(item: AttentionItem, today: string) {
  const reasons: string[] = []
  if (isDue(item.account, today)) reasons.push(item.account?.next_action_date && item.account.next_action_date < today ? 'Overdue action' : 'Action due today')
  if (item.events.length > 0) reasons.push(`${item.events.length} new source change${item.events.length === 1 ? '' : 's'}`)
  if (item.row.recent_confirmed_violation) reasons.push('Recent confirmed violation')
  if (isSamplingFollowUp(item.row)) reasons.push('Sampling follow-up')
  if ((item.row.dwt_violation_record_count ?? 0) > 0) reasons.push('DWT violation record')
  if ((item.row.dob_recent_activity_count ?? 0) > 0) reasons.push('Recent DOB activity')
  if ((item.row.hpd_contact_count ?? 0) > 0) reasons.push('Contact-ready')
  return reasons.slice(0, 4)
}

export function WorkflowWorkspacePage({
  user,
  systems,
  accounts,
  watchlists,
  memberships,
  savedViews,
  changes,
  generatedAt,
  onOpenAccount,
}: {
  user: WorkflowUser | null
  systems: WorkflowSystem[]
  accounts: WorkflowAccountState[]
  watchlists: WorkflowWatchlist[]
  memberships: WorkflowMembership[]
  savedViews: WorkflowSavedView[]
  changes: ChangesPayload
  generatedAt: string
  onOpenAccount: (row: WorkflowSystem) => void
}) {
  const byId = new Map(systems.map(row => [row.system_id, row]))
  const accountById = new Map(accounts.map(account => [account.system_id, account]))
  const membershipCounts = new Map<string, number>()
  memberships.forEach(item => membershipCounts.set(item.watchlist_id, (membershipCounts.get(item.watchlist_id) ?? 0) + 1))

  const today = new Date().toISOString().slice(0, 10)
  const watchedIds = new Set(memberships.map(item => item.system_id))
  const scopeIds = new Set([...accounts.map(account => account.system_id), ...memberships.map(item => item.system_id)])
  const scopedRows = systems.filter(row => scopeIds.has(row.system_id))
  const missingScopeCount = [...scopeIds].filter(systemId => !byId.has(systemId)).length

  const eventsBySystem = new Map<string, ChangeEvent[]>()
  changes.events.forEach(event => {
    if (!scopeIds.has(event.system_id)) return
    const list = eventsBySystem.get(event.system_id) ?? []
    list.push(event)
    eventsBySystem.set(event.system_id, list)
  })

  const due = accounts
    .filter(account => account.next_action_date && account.next_action_date <= today && byId.has(account.system_id))
    .sort((a, b) => String(a.next_action_date).localeCompare(String(b.next_action_date)))
  const upcoming = accounts
    .filter(account => account.next_action_date && byId.has(account.system_id))
    .sort((a, b) => String(a.next_action_date).localeCompare(String(b.next_action_date)))
    .slice(0, 12)
  const unscheduledFollowUps = accounts.filter(account => !account.next_action_date && (account.status === 'investigate' || account.status === 'contacted' || account.status === 'follow-up')).length

  const changedAccounts = scopedRows.filter(row => eventsBySystem.has(row.system_id))
  const scopeEvents = [...eventsBySystem.values()].flat()
  const highPriority = scopedRows.filter(row => row.priority_score >= 70)
  const contactReady = scopedRows.filter(row => (row.hpd_contact_count ?? 0) > 0)
  const samplingFollowUp = scopedRows.filter(isSamplingFollowUp)
  const recentViolations = scopedRows.filter(row => row.recent_confirmed_violation)
  const oathEvidence = scopedRows.filter(row => (row.oath_case_count ?? 0) > 0)
  const recentDob = scopedRows.filter(row => (row.dob_recent_activity_count ?? 0) > 0)
  const ownerKnown = scopedRows.filter(row => Boolean(row.pluto_owner_name))
  const recentAcris = scopedRows.filter(row => (row.acris_recent_document_count ?? 0) > 0)
  const roofMapped = scopedRows.filter(row => (row.planimetric_building_tower_count ?? 0) > 0)
  const buildingMapped = scopedRows.filter(row => (row.building_footprint_count ?? 0) > 0)
  const multiEquipment = scopedRows.filter(row => row.active_equipment > 1)
  const dwtPhysical = scopedRows.filter(row => (row.dwt_planimetric_tank_count ?? 0) > 0)
  const dwtOversight = scopedRows.filter(row => (row.dwt_compliance_record_count ?? 0) > 0)
  const dwtSelfReports = scopedRows.filter(row => (row.dwt_self_report_record_count ?? 0) > 0)
  const dwtAny = scopedRows.filter(row => (row.dwt_planimetric_tank_count ?? 0) > 0 || (row.dwt_compliance_record_count ?? 0) > 0 || (row.dwt_self_report_record_count ?? 0) > 0)
  const dwtViolation = scopedRows.filter(row => (row.dwt_violation_record_count ?? 0) > 0)
  const activeFollowUp = accounts.filter(account => account.status === 'investigate' || account.status === 'follow-up').length

  const attention = scopedRows
    .map<AttentionItem>(row => ({ row, account: accountById.get(row.system_id), events: eventsBySystem.get(row.system_id) ?? [] }))
    .sort((a, b) => {
      const dueDiff = Number(isDue(b.account, today)) - Number(isDue(a.account, today))
      if (dueDiff !== 0) return dueDiff
      const changedDiff = Number(b.events.length > 0) - Number(a.events.length > 0)
      if (changedDiff !== 0) return changedDiff
      const aDate = a.account?.next_action_date ?? '9999-12-31'
      const bDate = b.account?.next_action_date ?? '9999-12-31'
      const dateDiff = aDate.localeCompare(bDate)
      if (dateDiff !== 0) return dateDiff
      return b.row.priority_score - a.row.priority_score
    })
    .slice(0, 8)

  const summaryParts: string[] = []
  if (due.length > 0) summaryParts.push(`${due.length} due or overdue action${due.length === 1 ? '' : 's'}`)
  if (changedAccounts.length > 0) summaryParts.push(`${changedAccounts.length} account${changedAccounts.length === 1 ? '' : 's'} with new source changes`)
  if (highPriority.length > 0) summaryParts.push(`${highPriority.length} high-priority account${highPriority.length === 1 ? '' : 's'}`)
  if (samplingFollowUp.length > 0) summaryParts.push(`${samplingFollowUp.length} sampling follow-up signal${samplingFollowUp.length === 1 ? '' : 's'}`)
  const operationalSummary = scopedRows.length === 0
    ? 'No current accounts are in the private workflow scope yet. Add an account to a watchlist or save a workflow status from an account profile to build an operational queue here.'
    : summaryParts.length > 0
      ? `Your private workflow covers ${scopedRows.length.toLocaleString()} current NYC account${scopedRows.length === 1 ? '' : 's'}. Most important now: ${summaryParts.join(' · ')}.`
      : `Your private workflow covers ${scopedRows.length.toLocaleString()} current NYC account${scopedRows.length === 1 ? '' : 's'}. No dated follow-up, fresh monitored change, high-priority account or sampling follow-up is currently pressing.`

  const categories: Array<{ title: string; purpose: string; metrics: CategoryMetric[]; next: string }> = [
    {
      title: 'Compliance & timing',
      purpose: 'Why an account may need attention now.',
      metrics: [
        { label: 'Sampling follow-up', value: samplingFollowUp.length, note: 'Gap or missing public sample date' },
        { label: 'Recent confirmed violations', value: recentViolations.length, note: 'Current public violation evidence' },
        { label: 'OATH case evidence', value: oathEvidence.length, note: 'Exact-matched summons lifecycle' },
        { label: 'Recent DOB activity', value: recentDob.length, note: 'Project / permit timing context' },
      ],
      next: 'Private service intervals, work-order dates and service-event timing belong here when available.',
    },
    {
      title: 'Ownership, access & property',
      purpose: 'Who controls the site and whether outreach has a defensible path.',
      metrics: [
        { label: 'Owner context', value: ownerKnown.length, note: 'PLUTO owner field present' },
        { label: 'Contact-ready', value: contactReady.length, note: 'HPD contact evidence attached' },
        { label: 'Recent ACRIS activity', value: recentAcris.length, note: 'Recent real-property filing context' },
        { label: 'Current building outline', value: buildingMapped.length, note: 'Exact-BIN OTI footprint' },
      ],
      next: 'Property manager, operator, access-contact and decision-maker relationships will extend this category.',
    },
    {
      title: 'Field & physical',
      purpose: 'What a technician or field team can orient to before arriving.',
      metrics: [
        { label: 'Cooling-tower roof geometry', value: roofMapped.length, note: '2022 physical tower features' },
        { label: 'Building footprint context', value: buildingMapped.length, note: 'Current OTI building outline' },
        { label: 'Multi-equipment sites', value: multiEquipment.length, note: 'More than one active registered unit' },
        { label: 'Mapped DWT roof tanks', value: dwtPhysical.length, note: '2022 rooftop water-tank polygons' },
      ],
      next: 'Roof-access notes, exact equipment inventory, photos, QR/NFC, sample points and technician observations will stay in this lane.',
    },
    {
      title: 'Domestic water',
      purpose: 'Separate physical tank evidence from regulatory and self-reported inspection history.',
      metrics: [
        { label: 'Any DWT context', value: dwtAny.length, note: 'At least one domestic-water evidence family' },
        { label: 'DOHMH oversight', value: dwtOversight.length, note: 'Official exact-BIN records' },
        { label: 'Self-reported inspections', value: dwtSelfReports.length, note: 'Certified-inspector / owner submissions' },
        { label: 'DWT violation records', value: dwtViolation.length, note: 'Published violation / summons evidence' },
      ],
      next: 'Tank service history, treatment readings and longitudinal water-quality trends will extend this category without being mixed into cooling-tower compliance.',
    },
    {
      title: 'Monitoring & change',
      purpose: 'What changed since the previous preserved public observation.',
      metrics: [
        { label: 'Accounts changed', value: changedAccounts.length, note: 'Distinct workflow accounts with events' },
        { label: 'Change events', value: scopeEvents.length, note: 'All current preserved events in scope' },
        { label: 'Compliance / timing changes', value: scopeEvents.filter(isComplianceChange).length, note: 'Sample, inspection, violation or OATH' },
        { label: 'Property / project changes', value: scopeEvents.filter(isPropertyProjectChange).length, note: 'HPD, PLUTO or DOB' },
      ],
      next: 'Domestic-water deltas and private service-event changes can join this lane once deterministic history rules are defined.',
    },
    {
      title: 'Commercial readiness',
      purpose: 'Which workflow accounts are actionable without changing the public Priority Score.',
      metrics: [
        { label: 'High priority', value: highPriority.length, note: 'Public Priority Score 70+' },
        { label: 'Contact-ready', value: contactReady.length, note: 'Public contact evidence available' },
        { label: 'Investigate / follow-up', value: activeFollowUp, note: 'Private workflow disposition' },
        { label: 'Watched accounts', value: watchedIds.size, note: 'Across private watchlists' },
      ],
      next: 'Observed service-provider, bidder and contract relationships will remain explicitly evidence-labeled rather than inferred from generic vendor similarity.',
    },
  ]

  const futureLanes = [
    { title: 'Field service operations', current: 'Roof geometry, equipment counts and physical context are available now.', next: 'Work orders · access instructions · service notes · photos · QR/NFC references' },
    { title: 'Water-treatment operations', current: 'Cooling-tower sampling signals and DWT inspection evidence are separated today.', next: 'Sample-point map · treatment targets · field readings · chemistry trend history' },
    { title: 'Documents & system topology', current: 'Public DOB/project evidence provides bounded project context.', next: 'MPP · P&ID · valve schedule · system schematic · equipment manuals' },
    { title: 'Relationships & contracts', current: 'Owner/contact evidence and source-reported DWT inspection-firm names are preserved.', next: 'Property manager · operator · current service provider · awarded contract relationships with explicit evidence basis' },
  ]

  return <section className="product-page workflow-workspace-page">
    <div className="product-page-heading workflow-page-heading">
      <div><span className="page-kicker">New York City · private command workspace</span><h1>Workflow <span className="private-chip">Private</span></h1><p>Turn public-source intelligence into a usable operating queue. Private notes, status, watchlists and next actions remain separate from the source-backed evidence that explains why an account matters.</p></div>
      <div className="page-actions"><ShareButton label="Share public page link" /></div>
    </div>

    {!user && <div className="workflow-login-callout"><div><span className="roadmap-status">PRIVATE WORKSPACE</span><strong>Sign in from the profile control to sync workflow state across sessions and devices.</strong><p>Your existing browser-local saved views remain available. Account notes, status and watchlists require an authenticated private workspace.</p></div></div>}

    <section className="workflow-command-summary" aria-labelledby="workflow-summary-heading">
      <div className="workflow-command-copy">
        <span className="page-kicker">Operational summary</span>
        <h2 id="workflow-summary-heading">What matters now</h2>
        <p>{operationalSummary}</p>
        <div className="workflow-summary-meta">
          <span>Workflow scope <strong>{number.format(scopedRows.length)}</strong></span>
          <span>NYC market <strong>{number.format(systems.length)}</strong></span>
          <span>Data refreshed <strong>{formatTimestamp(generatedAt)}</strong></span>
          <span>History since <strong>{formatDate(changes.history_started_at)}</strong></span>
          {missingScopeCount > 0 && <span className="workflow-meta-warning"><strong>{missingScopeCount}</strong> saved account{missingScopeCount === 1 ? '' : 's'} not in current snapshot</span>}
        </div>
      </div>
      <div className="workflow-command-metrics">
        <article className={due.length > 0 ? 'urgent' : ''}><small>Due / overdue</small><strong>{number.format(due.length)}</strong><span>Dated private next actions</span></article>
        <article><small>Changed accounts</small><strong>{number.format(changedAccounts.length)}</strong><span>Fresh preserved source events</span></article>
        <article><small>High priority</small><strong>{number.format(highPriority.length)}</strong><span>Public Priority Score 70+</span></article>
        <article><small>Contact-ready</small><strong>{number.format(contactReady.length)}</strong><span>HPD contact evidence</span></article>
      </div>
    </section>

    <section className="workflow-section-block">
      <div className="workflow-block-heading"><div><span className="page-kicker">Action first</span><h2>Attention queue</h2><p>Due actions first, then accounts with current source changes, then earlier next-action dates and public Priority Score. This ordering does not alter TowerSignal Priority Score.</p></div><strong>{attention.length}</strong></div>
      {attention.length === 0 ? <div className="reference-empty-state compact"><span>Add accounts to a watchlist or save workflow status from an account profile. The highest-attention items will surface here automatically.</span></div> : <div className="workflow-attention-list">
        {attention.map(item => <article className="workflow-attention-card" key={item.row.system_id} onClick={() => onOpenAccount(item.row)}>
          <div className="workflow-attention-main"><div><span className="workflow-account-location">{[item.row.borough, item.row.zip].filter(Boolean).join(' · ') || item.row.system_id}</span><strong>{item.row.address ?? item.row.system_id}</strong></div><span className={item.row.priority_score >= 70 ? 'workflow-priority high' : 'workflow-priority'}>P{item.row.priority_score}</span></div>
          <div className="workflow-attention-reasons">{attentionReasons(item, today).map(reason => <span key={reason}>{reason}</span>)}{attentionReasons(item, today).length === 0 && <span>Workflow account</span>}</div>
          <footer><span className="status-chip">{statusLabel(item.account?.status)}</span><span>{item.account?.next_action_date ? `Next ${formatDate(item.account.next_action_date)}` : 'No dated next action'}</span><button className="table-link" onClick={event => { event.stopPropagation(); onOpenAccount(item.row) }}>Open account →</button></footer>
        </article>)}
      </div>}
    </section>

    <section className="workflow-section-block workflow-intelligence-block">
      <div className="workflow-block-heading"><div><span className="page-kicker">Evidence organized by use</span><h2>Account intelligence groups</h2><p>Current data is grouped by how teams use it. New sources should enter the relevant lane rather than creating another unstructured block on this page.</p></div><strong>{number.format(scopedRows.length)} scoped</strong></div>
      <div className="workflow-intelligence-grid">
        {categories.map(category => <article className="workflow-intelligence-card" key={category.title}>
          <header><strong>{category.title}</strong><p>{category.purpose}</p></header>
          <dl>{category.metrics.map(metric => <div key={metric.label}><dt>{metric.label}</dt><dd><strong>{number.format(metric.value)}</strong><span>{metric.note}</span></dd></div>)}</dl>
          <footer><span>Future-ready</span><p>{category.next}</p></footer>
        </article>)}
      </div>
    </section>

    <section className="workflow-section-block">
      <div className="workflow-block-heading"><div><span className="page-kicker">Private operating tools</span><h2>Follow-up, saved views & watchlists</h2><p>Keep reusable prospecting criteria separate from account-specific action state.</p></div><strong>{number.format(savedViews.length + watchlists.length)}</strong></div>
      <div className="workflow-operations-grid">
        <div className="workflow-operations-card workflow-next-actions">
          <header><div><strong>Next actions</strong><span>{upcoming.length === 0 ? 'No dated next actions saved' : 'Earliest saved actions'}</span></div><small>{unscheduledFollowUps > 0 ? `${unscheduledFollowUps} active follow-up status${unscheduledFollowUps === 1 ? '' : 'es'} without a date` : 'No unscheduled active follow-up'}</small></header>
          {upcoming.length === 0 ? <div className="reference-empty-state compact"><span>Add a status, note and next-action date from any account profile.</span></div> : <div className="workflow-action-list">{upcoming.map(account => {
            const row = byId.get(account.system_id)
            return <article className="workflow-action-card" key={account.system_id}>
              <div><span>{row ? [row.borough, row.zip].filter(Boolean).join(' · ') : account.system_id}</span><strong>{row?.address ?? account.system_id}</strong></div>
              <span className="status-chip">{statusLabel(account.status)}</span>
              <p>{account.note || 'No private note saved.'}</p>
              <strong className={account.next_action_date && account.next_action_date <= today ? 'due-date' : ''}>{account.next_action_date ? formatDate(account.next_action_date) : '—'}</strong>
              {row ? <button className="table-link" onClick={() => onOpenAccount(row)}>Open →</button> : <span>Unavailable</span>}
            </article>
          })}</div>}
        </div>

        <div className="workflow-reusable-grid">
          <section className="workflow-operations-card"><div className="workflow-sidebar-heading"><span className="page-kicker">Saved views</span><strong>{savedViews.length}</strong></div>{savedViews.length === 0 ? <p>No saved views yet. Save prospect filters you expect to reuse.</p> : <div className="workflow-tool-list">{savedViews.slice(0, 12).map(view => <div key={view.id}><span>▤</span><strong>{view.name}</strong></div>)}</div>}</section>
          <section className="workflow-operations-card"><div className="workflow-sidebar-heading"><span className="page-kicker">Watchlists</span><strong>{watchlists.length}</strong></div>{watchlists.length === 0 ? <p>Sign in to create private watchlists and monitoring groups.</p> : <div className="workflow-tool-list">{watchlists.map(watchlist => <div key={watchlist.id}><span>★</span><strong>{watchlist.name}</strong><small>{membershipCounts.get(watchlist.id) ?? 0}</small></div>)}</div>}</section>
        </div>
      </div>
    </section>

    <section className="workflow-section-block">
      <div className="workflow-block-heading"><div><span className="page-kicker">Pipeline state</span><h2>Accounts by status</h2><p>Private disposition only. Public evidence and Priority Score remain unchanged by a workflow status.</p></div><strong>{number.format(accounts.length)}</strong></div>
      <div className="workflow-kanban">{columns.map(column => {
        const items = accounts.filter(account => account.status === column.value)
        return <section key={column.value} className="kanban-column"><header><span className={`kanban-dot kanban-${column.value}`} />{column.label}<strong>{items.length}</strong></header><div>{items.slice(0, 5).map(account => {
          const row = byId.get(account.system_id)
          return <article key={account.system_id} className="kanban-card" onClick={() => row && onOpenAccount(row)}><strong>{row?.address ?? account.system_id}</strong><span>{row ? [row.borough, row.zip].filter(Boolean).join(' · ') : 'Account not present in current public snapshot'}</span>{account.note && <p>{account.note}</p>}<footer>{row && <span className={row.priority_score >= 70 ? 'priority-text-high' : ''}>P{row.priority_score}</span>}<span>{account.next_action_date ? formatDate(account.next_action_date) : 'No next action'}</span></footer></article>
        })}{items.length > 5 && <div className="kanban-more">+ {items.length - 5} more</div>}</div></section>
      })}</div>
    </section>

    <section className="workflow-section-block workflow-future-block">
      <div className="workflow-block-heading"><div><span className="page-kicker">Future data organization</span><h2>Reserved data lanes</h2><p>Future ingestion should extend these categories instead of adding unrelated one-off sections. This keeps the workflow usable as TowerSignal grows beyond public compliance records.</p></div></div>
      <div className="workflow-future-grid">{futureLanes.map(lane => <article key={lane.title}><strong>{lane.title}</strong><p>{lane.current}</p><span>Next fields</span><p>{lane.next}</p></article>)}</div>
    </section>
  </section>
}
