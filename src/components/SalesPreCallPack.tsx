import { formatDate } from '../domain/labels'
import type { AcrisPropertyActivity, AcrisSummaryFields } from '../types/acris'
import type { SystemSummary } from '../types/data'
import type { SystemDetailWithDomesticWater } from './DomesticWaterSection'
import { AccountSectionNavigator } from './AccountSectionNavigator'

type SalesTone = 'ready' | 'attention' | 'verify' | 'missing'

type SalesFact = {
  label: string
  value: string
  detail: string
  tone: SalesTone
}

type SalesDetail = SystemDetailWithDomesticWater & { acris_activity?: AcrisPropertyActivity | null }

const plural = (value: number, singular: string, pluralLabel = `${singular}s`) => `${value.toLocaleString()} ${value === 1 ? singular : pluralLabel}`
const compactNumber = (value: number | null | undefined) => value == null ? '—' : new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 }).format(value)
const confidenceLabel = (value: SystemSummary['evidence_confidence']) => value === 'CONFIRMED' ? 'Confirmed evidence' : value === 'STRONG_SIGNAL' ? 'Strong signal' : 'Verify'

function statusFor(row: SystemSummary): { label: string; tone: SalesTone } {
  if (row.recent_confirmed_violation) return { label: 'High-priority timing', tone: 'attention' }
  if (row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE')) return { label: 'Follow-up opportunity', tone: 'verify' }
  if (row.priority_score >= 70) return { label: 'High-priority account', tone: 'attention' }
  return { label: 'Research-ready', tone: 'ready' }
}

function primaryTimingCue(row: SystemSummary, detail: SalesDetail): string {
  const confirmed = detail.signals.find(signal => signal.evidence_confidence === 'CONFIRMED')
  const signal = confirmed ?? detail.signals[0]
  if (signal) return `Current signal · ${signal.title}`
  if ((row.dob_recent_activity_count ?? 0) > 0) return 'Recent DOB project activity'
  if ((detail.acris_activity?.recent_document_count ?? 0) > 0) return 'Recent ACRIS property activity'
  return 'Account scale / routine research'
}

function openingAngle(row: SystemSummary, detail: SalesDetail): string {
  if (row.recent_confirmed_violation) {
    return 'Use the recent public inspection activity as context for understanding the current service and testing workflow. Do not characterize the account as noncompliant from the TowerSignal signal alone.'
  }
  if (row.signal_types.includes('POTENTIAL_SAMPLING_GAP')) {
    return 'Use the public sampling-timing signal to ask how current testing is managed and whether the public record reflects present operations.'
  }
  if (row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE')) {
    return 'Use the absence of a usable public sample date as a verification question: who manages testing, and does the public record reflect the current program?'
  }
  if ((row.dob_recent_activity_count ?? 0) > 0) {
    return 'Use the recent mechanical or property-project activity to ask whether tower scope, access, equipment or vendor timing is changing.'
  }
  if ((detail.acris_activity?.recent_document_count ?? 0) > 0) {
    return 'Use the recent recorded property activity to ask whether facilities or procurement responsibilities have changed.'
  }
  return 'Lead with the building’s cooling-tower scale and operational complexity, then qualify who owns the water-treatment and service relationship.'
}

function contactPath(detail: SalesDetail): { value: string; detail: string; tone: SalesTone } {
  const contacts = detail.hpd_registration?.contacts ?? []
  const first = contacts[0]
  if (first) {
    const name = first.corporation_name ?? first.person_name ?? first.description ?? 'HPD contact'
    return {
      value: `${name}${contacts.length > 1 ? ` + ${contacts.length - 1} more` : ''}`,
      detail: 'Public HPD filing contact only. Confirm the person responsible for facilities, procurement and cooling-tower service before outreach.',
      tone: 'ready',
    }
  }
  if (detail.building_context?.owner_name) {
    return {
      value: detail.building_context.owner_name,
      detail: 'PLUTO owner context is available, but it is not asserted to be the service decision-maker or procurement contact.',
      tone: 'verify',
    }
  }
  return {
    value: 'Research contact before outreach',
    detail: 'No defensible HPD contact or PLUTO owner path is represented in the current account payload.',
    tone: 'missing',
  }
}

function callObjective(detail: SalesDetail): string {
  const contacts = detail.hpd_registration?.contacts ?? []
  return contacts.length
    ? 'Qualify current service ownership, incumbent vendor, agreement timing and the facilities/procurement path for the next action.'
    : 'Establish the correct facilities or property-management decision-maker, then qualify current service ownership, incumbent vendor and agreement timing.'
}

function buildQuestions(row: SystemSummary, detail: SalesDetail): string[] {
  const towers = detail.planimetric_building_tower_features ?? []
  const contacts = detail.hpd_registration?.contacts ?? []
  const domestic = detail.domestic_water
  const questions = [
    'Who owns the cooling-tower water-treatment, testing, maintenance and service relationship today?',
    'Which company is the incumbent service provider, and when does the current agreement renew, rebid or come up for review?',
  ]
  if (contacts.length === 0) questions.push('Who is the correct facilities or property-management decision-maker for cooling-tower service decisions?')
  if (towers.length > 0 && towers.length !== row.active_equipment) questions.push(`The registration shows ${row.active_equipment.toLocaleString()} active units while the 2022 physical layer shows ${towers.length.toLocaleString()} tower footprints. What is the current equipment configuration?`)
  if (row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE')) questions.push('Does the public sampling record reflect the current testing cadence, and who manages that program?')
  if (row.recent_confirmed_violation) questions.push('Has the recent public inspection finding changed service, testing or maintenance procedures?')
  if ((row.dob_recent_activity_count ?? 0) > 0) questions.push('Are recent mechanical or roof projects affecting cooling-tower scope, access or vendor timing?')
  if ((detail.acris_activity?.recent_document_count ?? 0) > 0) questions.push('Did recent property activity change facilities, ownership or procurement decision-makers?')
  if ((domestic?.summary.planimetric_tank_count ?? 0) > 0) questions.push('Are cooling-tower and domestic-water services managed by the same facilities team or vendors?')
  return questions.slice(0, 6)
}

function verificationItems(row: SystemSummary, detail: SalesDetail): string[] {
  const towers = detail.planimetric_building_tower_features ?? []
  const contacts = detail.hpd_registration?.contacts ?? []
  const items: string[] = []
  if (!row.bbl) items.push('A usable BBL is not published for this account, so BBL-based PLUTO, HPD, DOB and ACRIS enrichment may be unavailable.')
  if (contacts.length === 0) items.push('No public HPD contact is matched; do not infer the sales contact from unrelated filing parties.')
  if (towers.length > 0 && towers.length !== row.active_equipment) items.push(`Registered active equipment (${row.active_equipment}) and 2022 mapped tower footprints (${towers.length}) differ; confirm current configuration.`)
  if (towers.length > 0) items.push('Planimetric tower footprints are based on 2022 imagery and do not prove the current equipment configuration.')
  if (row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE')) items.push('Sampling-timing signals are commercial follow-up cues and do not establish current noncompliance or current tower operation.')
  items.push('The incumbent cooling-tower service provider is not established by this account payload unless separate source-backed vendor or procurement evidence is available.')
  return items
}

function talkingPoints(row: SystemSummary, detail: SalesDetail): SalesFact[] {
  const enrichedRow = row as SystemSummary & AcrisSummaryFields
  const towers = detail.planimetric_building_tower_features ?? []
  const inspections = detail.inspection_history ?? []
  const violationCount = inspections.reduce((sum, inspection) => sum + inspection.violation_count, 0)
  const dobJobs = detail.dob_activity_history ?? []
  const latestDob = dobJobs.find(job => job.activity_date)?.activity_date
  const acris = detail.acris_activity
  const domestic = detail.domestic_water
  const building = detail.building_context
  const points: SalesFact[] = [
    {
      label: 'Cooling-tower scale',
      value: `${plural(row.active_equipment, 'registered active unit')}${towers.length ? ` · ${plural(towers.length, 'mapped 2022 footprint')}` : ''}`,
      detail: towers.length && towers.length !== row.active_equipment ? 'Counts differ across registration and physical imagery; use this as a qualification question, not a configuration claim.' : 'Registration and physical evidence are separate public-source views of the account.',
      tone: towers.length && towers.length !== row.active_equipment ? 'verify' : 'ready',
    },
    {
      label: 'Sampling context',
      value: row.latest_sample_date ? `${formatDate(row.latest_sample_date)}${row.days_since_latest_sample == null ? '' : ` · ${row.days_since_latest_sample.toLocaleString()} days old`}` : 'No usable public sample date',
      detail: row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE') ? 'TowerSignal generated a follow-up signal from the public sampling record.' : 'Current public registration sampling context.',
      tone: row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE') ? 'verify' : 'ready',
    },
    {
      label: 'Inspection history',
      value: `${plural(inspections.length, 'joined inspection')} · ${plural(violationCount, 'violation citation')}`,
      detail: row.latest_inspection_date ? `Latest joined inspection ${formatDate(row.latest_inspection_date)}.` : 'No joined NYC Health inspection date is represented.',
      tone: row.recent_confirmed_violation ? 'attention' : inspections.length ? 'ready' : 'missing',
    },
  ]

  if (building) {
    const buildingBits = [
      building.building_area_sqft ? `${compactNumber(building.building_area_sqft)} sq ft` : null,
      building.floors != null ? `${building.floors.toLocaleString()} floors` : null,
      building.year_built ? `built ${building.year_built}` : null,
    ].filter(Boolean)
    points.push({
      label: 'Property scale',
      value: buildingBits.join(' · ') || 'PLUTO context matched',
      detail: building.owner_name ? `PLUTO owner context: ${building.owner_name}.` : 'Exact-BBL PLUTO building context is available.',
      tone: 'ready',
    })
  }

  if (dobJobs.length > 0) {
    points.push({
      label: 'Project timing',
      value: `${plural(dobJobs.length, 'DOB filing')}${latestDob ? ` · latest ${formatDate(latestDob)}` : ''}`,
      detail: `${(row.dob_explicit_cooling_tower_count ?? 0).toLocaleString()} explicit cooling-tower description match; ${(row.dob_mechanical_or_boiler_count ?? 0).toLocaleString()} mechanical/boiler context record(s).`,
      tone: (row.dob_recent_activity_count ?? 0) > 0 ? 'ready' : 'verify',
    })
  }

  if (acris) {
    points.push({
      label: 'Property activity',
      value: `${plural(acris.recent_document_count, 'recent ACRIS document')}${acris.latest_recorded_date ? ` · latest ${formatDate(acris.latest_recorded_date)}` : ''}`,
      detail: `${(enrichedRow.acris_deed_count ?? acris.deed_count).toLocaleString()} deeds · ${(enrichedRow.acris_mortgage_count ?? acris.mortgage_count).toLocaleString()} mortgages · ${(enrichedRow.acris_lease_count ?? acris.lease_count).toLocaleString()} leases. Recorded parties are not asserted to be service contacts.`,
      tone: 'ready',
    })
  }

  if (domestic && (domestic.summary.planimetric_tank_count > 0 || domestic.summary.compliance_record_count > 0 || domestic.summary.self_report_record_count > 0)) {
    points.push({
      label: 'Adjacent water assets',
      value: `${plural(domestic.summary.planimetric_tank_count, 'mapped rooftop drinking-water tank')} · ${plural(domestic.summary.compliance_record_count + domestic.summary.self_report_record_count, 'DOHMH record')}`,
      detail: 'Domestic-water evidence is a separate source family and may be useful for broader facility-service qualification.',
      tone: 'ready',
    })
  }

  return points
}

function factCard(point: SalesFact) {
  return <article key={point.label} className={`sales-fact sales-fact-${point.tone}`}>
    <span>{point.label}</span>
    <strong>{point.value}</strong>
    <small>{point.detail}</small>
  </article>
}

export function SalesPreCallPack({ row, detail }: { row: SystemSummary; detail: SystemDetailWithDomesticWater }) {
  const enrichedDetail = detail as SalesDetail
  const towers = enrichedDetail.planimetric_building_tower_features ?? []
  const contact = contactPath(enrichedDetail)
  const status = statusFor(row)
  const questions = buildQuestions(row, enrichedDetail)
  const verify = verificationItems(row, enrichedDetail)
  const points = talkingPoints(row, enrichedDetail)
  const primaryPoints = points.slice(0, 3)
  const additionalPoints = points.slice(3)

  return <div className="sales-precall-pack" aria-labelledby="sales-precall-pack-title">
    <AccountSectionNavigator />
    <div className="sales-pack-header">
      <div>
        <span className="eyebrow">Sales pre-call pack</span>
        <h3 id="sales-precall-pack-title">Pre-call sales brief</h3>
        <p>Source-backed account context for deciding why to call, who to reach, what to ask and what still needs verification.</p>
      </div>
      <span className={`sales-pack-status sales-pack-status-${status.tone}`}>{status.label}</span>
    </div>

    <div className="sales-pack-metrics" aria-label="Sales pre-call summary">
      <article><small>Why call now</small><strong>{primaryTimingCue(row, enrichedDetail)}</strong></article>
      <article><small>Account scale</small><strong>{plural(row.active_equipment, 'registered active unit')}{towers.length ? ` · ${plural(towers.length, 'mapped footprint')}` : ''}</strong></article>
      <article className={`sales-pack-metric-${contact.tone}`}><small>Contact path</small><strong>{contact.value}</strong><span>{contact.detail}</span></article>
      <article><small>Timing evidence</small><strong>{confidenceLabel(row.evidence_confidence)}</strong><span>Priority score {row.priority_score}; evidence class is not win probability.</span></article>
    </div>

    <div className="sales-pack-objective">
      <span>Call objective</span>
      <strong>{callObjective(enrichedDetail)}</strong>
    </div>

    <div className="sales-pack-flow">
      <section className="sales-pack-panel">
        <h4>Before the call</h4>
        <div className="sales-opening-angle"><span>Best opening angle</span><p>{openingAngle(row, enrichedDetail)}</p></div>
        <div className="sales-talking-points sales-talking-points-primary">
          <strong>Top source-backed talking points</strong>
          <div className="sales-primary-fact-grid">{primaryPoints.map(factCard)}</div>
        </div>
        {additionalPoints.length > 0 && <details className="sales-pack-expand">
          <summary><strong>More account talking points</strong><span>{additionalPoints.length}</span></summary>
          <div className="sales-expanded-facts">{additionalPoints.map(factCard)}</div>
        </details>}
      </section>

      <section className="sales-pack-panel sales-call-panel">
        <h4>During the call</h4>
        <div className="sales-call-starter"><span>Start with</span><p>{questions[0]}</p></div>
        <details className="sales-pack-expand">
          <summary><strong>Qualification questions</strong><span>{questions.length}</span></summary>
          <ol className="sales-question-list">{questions.map(question => <li key={question}>{question}</li>)}</ol>
        </details>
        <details className="sales-pack-expand sales-pack-verify-details">
          <summary><strong>Verify before asserting</strong><span>{verify.length}</span></summary>
          <div className="sales-verify-block"><ul>{verify.map(item => <li key={item}>{item}</li>)}</ul></div>
        </details>
      </section>
    </div>

    <details className="sales-pack-evidence">
      <summary>How this sales brief was assembled</summary>
      <p>The brief uses the same account-level public evidence shown below: cooling-tower registration, reported sampling dates, NYC Health inspections, exact-matched building/contact/project/property activity when available, physical planimetric evidence and domestic-water context. It does not infer an incumbent vendor, contract renewal date, procurement authority, current compliance state or current equipment configuration when those facts are not published.</p>
    </details>

    <p className="microcopy">This pack is a sales-research aid. It separates public facts, TowerSignal commercial timing signals and questions that still require confirmation. Verify current service responsibility, operating status and decision-maker authority before relying on the brief in outreach.</p>
  </div>
}
