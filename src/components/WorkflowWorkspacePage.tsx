import { useEffect, useState } from 'react'
import type { AcrisSummaryFields } from '../types/acris'
import type { ChangeEvent, ChangesPayload } from '../types/history'
import type { SystemSummary } from '../types/data'
import type { WorkflowAccountState, WorkflowMembership, WorkflowSavedView, WorkflowUser, WorkflowWatchlist } from '../types/workflow'
import { loadChanges } from '../data/api'
import { formatDate, formatTimestamp } from '../domain/labels'
import { ShareButton } from './ShareButton'
import { WorkflowScaleWorkspace } from './WorkflowScaleWorkspace'

const RECENT_CHANGE_WINDOW_MS = 7 * 86400000
const number = new Intl.NumberFormat('en-US')

type DomesticWaterSummaryFields = {
  dwt_planimetric_tank_count?: number
  dwt_compliance_record_count?: number
  dwt_self_report_record_count?: number
  dwt_violation_record_count?: number
}

type WorkflowSystem = SystemSummary & AcrisSummaryFields & DomesticWaterSummaryFields

type CoverageGroup = {
  title: string
  metrics: Array<{ label: string; value: number }>
}

function isSamplingFollowUp(row: WorkflowSystem) {
  return row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE')
}

function isComplianceChange(event: ChangeEvent) {
  return event.event_type.startsWith('SAMPLE')
    || event.event_type.startsWith('SAMPLING')
    || event.event_type.startsWith('INSPECTION')
    || event.event_type.startsWith('VIOLATION')
    || event.event_type.startsWith('OATH_')
}

function isPropertyProjectChange(event: ChangeEvent) {
  return event.event_type.startsWith('HPD_') || event.event_type.startsWith('PLUTO_') || event.event_type.startsWith('DOB_')
}

export function WorkflowWorkspacePage({
  user,
  systems,
  accounts,
  watchlists,
  memberships,
  savedViews,
  onOpenAccount,
}: {
  user: WorkflowUser | null
  systems: WorkflowSystem[]
  accounts: WorkflowAccountState[]
  watchlists: WorkflowWatchlist[]
  memberships: WorkflowMembership[]
  savedViews: WorkflowSavedView[]
  onOpenAccount: (row: WorkflowSystem) => void
}) {
  const [changes, setChanges] = useState<ChangesPayload | null>(null)
  const [changeLoadFailed, setChangeLoadFailed] = useState(false)

  useEffect(() => {
    let active = true
    loadChanges()
      .then(payload => { if (active) setChanges(payload) })
      .catch(() => { if (active) setChangeLoadFailed(true) })
    return () => { active = false }
  }, [])

  const byId = new Map(systems.map(row => [row.system_id, row]))
  const today = new Date().toISOString().slice(0, 10)
  const recentCutoff = Date.now() - RECENT_CHANGE_WINDOW_MS
  const recentEvents = (changes?.events ?? []).filter(event => new Date(event.detected_at).getTime() >= recentCutoff)
  const scopeIds = new Set([...accounts.map(account => account.system_id), ...memberships.map(item => item.system_id)])
  const scopedRows = systems.filter(row => scopeIds.has(row.system_id))
  const missingScopeCount = [...scopeIds].filter(systemId => !byId.has(systemId)).length

  const eventsBySystem = new Map<string, ChangeEvent[]>()
  recentEvents.forEach(event => {
    if (!scopeIds.has(event.system_id)) return
    const current = eventsBySystem.get(event.system_id) ?? []
    current.push(event)
    eventsBySystem.set(event.system_id, current)
  })

  const scopedEvents = [...eventsBySystem.values()].flat()
  const samplingFollowUp = scopedRows.filter(isSamplingFollowUp)
  const recentViolations = scopedRows.filter(row => row.recent_confirmed_violation)
  const oathEvidence = scopedRows.filter(row => (row.oath_case_count ?? 0) > 0)
  const recentDob = scopedRows.filter(row => (row.dob_recent_activity_count ?? 0) > 0)
  const ownerKnown = scopedRows.filter(row => Boolean(row.pluto_owner_name))
  const contactReady = scopedRows.filter(row => (row.hpd_contact_count ?? 0) > 0)
  const recentAcris = scopedRows.filter(row => (row.acris_recent_document_count ?? 0) > 0)
  const roofMapped = scopedRows.filter(row => (row.planimetric_building_tower_count ?? 0) > 0)
  const buildingMapped = scopedRows.filter(row => (row.building_footprint_count ?? 0) > 0)
  const multiEquipment = scopedRows.filter(row => row.active_equipment > 1)
  const dwtPhysical = scopedRows.filter(row => (row.dwt_planimetric_tank_count ?? 0) > 0)
  const dwtOversight = scopedRows.filter(row => (row.dwt_compliance_record_count ?? 0) > 0)
  const dwtSelfReports = scopedRows.filter(row => (row.dwt_self_report_record_count ?? 0) > 0)
  const dwtAny = scopedRows.filter(row => (row.dwt_planimetric_tank_count ?? 0) > 0 || (row.dwt_compliance_record_count ?? 0) > 0 || (row.dwt_self_report_record_count ?? 0) > 0)
  const dwtViolation = scopedRows.filter(row => (row.dwt_violation_record_count ?? 0) > 0)
  const highPriority = scopedRows.filter(row => row.priority_score >= 70)

  const coverageGroups: CoverageGroup[] = [
    { title: 'Compliance & timing', metrics: [{ label: 'Sampling follow-up', value: samplingFollowUp.length }, { label: 'Recent confirmed violations', value: recentViolations.length }, { label: 'OATH case evidence', value: oathEvidence.length }, { label: 'Recent DOB activity', value: recentDob.length }] },
    { title: 'Ownership & access', metrics: [{ label: 'Owner context', value: ownerKnown.length }, { label: 'Contact-ready', value: contactReady.length }, { label: 'Recent ACRIS activity', value: recentAcris.length }, { label: 'Building outline', value: buildingMapped.length }] },
    { title: 'Field & physical', metrics: [{ label: 'Cooling-tower roof geometry', value: roofMapped.length }, { label: 'Multi-equipment sites', value: multiEquipment.length }, { label: 'Mapped DWT roof tanks', value: dwtPhysical.length }, { label: 'Building footprint context', value: buildingMapped.length }] },
    { title: 'Domestic water', metrics: [{ label: 'Any DWT context', value: dwtAny.length }, { label: 'DOHMH oversight', value: dwtOversight.length }, { label: 'Self-reported inspections', value: dwtSelfReports.length }, { label: 'DWT violation records', value: dwtViolation.length }] },
    { title: 'Monitoring & change', metrics: [{ label: 'Accounts changed · 7d', value: eventsBySystem.size }, { label: 'Change events · 7d', value: scopedEvents.length }, { label: 'Compliance changes · 7d', value: scopedEvents.filter(isComplianceChange).length }, { label: 'Property/project changes · 7d', value: scopedEvents.filter(isPropertyProjectChange).length }] },
    { title: 'Commercial readiness', metrics: [{ label: 'High priority', value: highPriority.length }, { label: 'Contact-ready', value: contactReady.length }, { label: 'Private account states', value: accounts.length }, { label: 'Watchlisted accounts', value: new Set(memberships.map(item => item.system_id)).size }] },
  ]

  const futureLanes = [
    ['Field service operations', 'Work orders · access instructions · service notes · photos · QR/NFC references'],
    ['Water-treatment operations', 'Sample-point map · treatment targets · field readings · chemistry trend history'],
    ['Documents & system topology', 'MPP · P&ID · valve schedule · system schematic · equipment manuals'],
    ['Relationships & contracts', 'Property manager · operator · current service provider · awarded contract relationships with explicit evidence basis'],
  ]

  return <section className="product-page workflow-workspace-page">
    <div className="product-page-heading workflow-page-heading">
      <div><span className="page-kicker">New York City · private operating workspace</span><h1 aria-label="Workflow workspace">Workflow <span className="private-chip">Private</span></h1><p>Monitor a large account portfolio, triage source changes and due actions, and update private workflow state without treating cards or Kanban columns as the source of truth.</p><div className="workflow-summary-meta"><span>Workflow scope <strong>{number.format(scopedRows.length)}</strong></span><span>NYC market <strong>{number.format(systems.length)}</strong></span>{changes?.observed_at && <span>Data observed <strong>{formatTimestamp(changes.observed_at)}</strong></span>}{changes?.history_started_at && <span>History since <strong>{formatDate(changes.history_started_at)}</strong></span>}{changeLoadFailed && <span className="workflow-meta-warning">Monitor history unavailable in this view</span>}{missingScopeCount > 0 && <span className="workflow-meta-warning"><strong>{missingScopeCount}</strong> saved account{missingScopeCount === 1 ? '' : 's'} not in current snapshot</span>}</div></div>
      <div className="page-actions"><ShareButton label="Share public page link" /></div>
    </div>

    {!user && <div className="workflow-login-callout"><div><span className="roadmap-status">PRIVATE WORKSPACE</span><strong>Sign in from the profile control to sync workflow state across sessions and devices.</strong><p>Saved prospect views can remain local, but account notes, status, watchlists and next actions require an authenticated private workspace.</p></div></div>}

    <WorkflowScaleWorkspace systems={scopedRows} marketCount={systems.length} accounts={accounts} watchlists={watchlists} memberships={memberships} savedViews={savedViews} recentEvents={recentEvents.filter(event => scopeIds.has(event.system_id))} eventsBySystem={eventsBySystem} today={today} onOpenAccount={onOpenAccount} />

    <details className="workflow-coverage-details"><summary><div><strong>Portfolio evidence coverage</strong><p>The former intelligence-card grid is retained as a compact reference instead of occupying the primary workflow. Operational work stays in the command workspace above.</p></div><span>{coverageGroups.length} evidence groups</span></summary><div className="workflow-coverage-matrix">{coverageGroups.map(group => <article key={group.title}><strong>{group.title}</strong><dl>{group.metrics.map(metric => <div key={metric.label}><dt>{metric.label}</dt><dd>{number.format(metric.value)}</dd></div>)}</dl></article>)}</div><div className="workflow-coverage-roadmap"><span className="page-kicker">Planned evidence extensions</span><div>{futureLanes.map(([title, fields]) => <article key={title}><strong>{title}</strong><p>{fields}</p></article>)}</div></div></details>
  </section>
}
