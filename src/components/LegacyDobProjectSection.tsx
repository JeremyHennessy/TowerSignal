import { formatDate } from '../domain/labels'
import type { SystemDetail } from '../types/data'

interface LegacyDobProjectRecord {
  source_row_id: string | null
  job_number: string | null
  document_number: string | null
  bbl: string
  bin: string | null
  job_type: string | null
  job_status: string | null
  job_status_description: string | null
  activity_date: string | null
  latest_action_date: string | null
  prefiling_date: string | null
  approved_date: string | null
  fully_permitted_date: string | null
  signoff_date: string | null
  plumbing: boolean
  mechanical: boolean
  boiler: boolean
  equipment: boolean
  job_description: string | null
  other_description: string | null
  explicit_cooling_tower_mention: boolean
  recent_relevant_project: boolean
  commercial_relevance: 'COOLING_TOWER_EXPLICIT' | 'RECENT_MECHANICAL_BOILER_PLUMBING_OR_EQUIPMENT'
  applicant_name: string | null
  applicant_professional_title: string | null
  applicant_license_number: string | null
  owner_business_name: string | null
  initial_cost_raw: string | null
  relationship_boundary: 'RECORDED_DOB_APPLICANT_NOT_PROOF_OF_SERVICE_CONTRACT'
}

interface LegacyDobProjectContext {
  summary: {
    record_count: number
    explicit_cooling_tower_count: number
    recent_relevant_project_count: number
    latest_activity_date: string | null
  }
  records: LegacyDobProjectRecord[]
  evidence_boundaries: Record<string, string>
  source: {
    dataset_id: string
    name: string
    source_last_updated_at?: string | null
  }
}

type DetailWithLegacy = SystemDetail & { legacy_dob_project_context?: LegacyDobProjectContext | null }

const MAX_VISIBLE = 20

function relevanceLabel(record: LegacyDobProjectRecord): string {
  return record.explicit_cooling_tower_mention ? 'Explicit cooling-tower history' : 'Recent mechanical / plumbing / equipment'
}

function workFlags(record: LegacyDobProjectRecord): string {
  return [
    record.mechanical ? 'Mechanical' : null,
    record.plumbing ? 'Plumbing' : null,
    record.boiler ? 'Boiler' : null,
    record.equipment ? 'Equipment' : null,
  ].filter(Boolean).join(' · ') || 'No retained work-type flag'
}

export function LegacyDobProjectSection({ detail }: { detail: SystemDetail }) {
  const context = (detail as DetailWithLegacy).legacy_dob_project_context
  if (!context || context.records.length === 0) return null
  const visible = context.records.slice(0, MAX_VISIBLE)
  const hidden = Math.max(0, context.records.length - visible.length)

  return <section className="legacy-dob-project-section">
    <h3>Legacy DOB / BIS project evidence</h3>
    <p>{context.summary.record_count.toLocaleString()} retained exact-BBL historical project record{context.summary.record_count === 1 ? '' : 's'} · {context.summary.explicit_cooling_tower_count.toLocaleString()} explicit cooling-tower mention{context.summary.explicit_cooling_tower_count === 1 ? '' : 's'} · {context.summary.recent_relevant_project_count.toLocaleString()} recent mechanical/plumbing/boiler/equipment record{context.summary.recent_relevant_project_count === 1 ? '' : 's'}.</p>
    <div className="signal-list">
      {visible.map((record, index) => <details key={`${record.source_row_id ?? record.job_number ?? 'legacy-dob'}-${index}`} open={index === 0}>
        <summary><span>{record.activity_date ? formatDate(record.activity_date) : 'Date not published'} · {record.job_number ?? record.source_row_id ?? 'Legacy DOB filing'}</span><strong>{relevanceLabel(record)}</strong></summary>
        <div className="violation-detail">
          <p>{record.job_description ?? record.other_description ?? 'No project description published.'}</p>
          <dl className="identity-grid">
            <div><dt>Recorded applicant</dt><dd>{record.applicant_name ?? '—'}</dd></div>
            <div><dt>Applicant role</dt><dd>{[record.applicant_professional_title, record.applicant_license_number ? `license ${record.applicant_license_number}` : null].filter(Boolean).join(' · ') || '—'}</dd></div>
            <div><dt>Recorded owner business</dt><dd>{record.owner_business_name ?? '—'}</dd></div>
            <div><dt>Work flags</dt><dd>{workFlags(record)}</dd></div>
            <div><dt>Job type</dt><dd>{record.job_type ?? '—'}</dd></div>
            <div><dt>Status</dt><dd>{record.job_status_description ?? record.job_status ?? '—'}</dd></div>
            <div><dt>Prefiling</dt><dd>{record.prefiling_date ? formatDate(record.prefiling_date) : '—'}</dd></div>
            <div><dt>Approved</dt><dd>{record.approved_date ? formatDate(record.approved_date) : '—'}</dd></div>
            <div><dt>Fully permitted</dt><dd>{record.fully_permitted_date ? formatDate(record.fully_permitted_date) : '—'}</dd></div>
            <div><dt>Signoff</dt><dd>{record.signoff_date ? formatDate(record.signoff_date) : '—'}</dd></div>
            <div><dt>Initial cost</dt><dd>{record.initial_cost_raw ?? '—'}</dd></div>
            <div><dt>Source identity</dt><dd>{record.source_row_id ?? '—'}</dd></div>
          </dl>
        </div>
      </details>)}
    </div>
    {hidden > 0 && <p className="microcopy">Showing the {MAX_VISIBLE} highest-priority retained records; {hidden.toLocaleString()} additional bounded source records remain in the account payload.</p>}
    <p className="microcopy"><strong>Historical project context only.</strong> Records come from legacy DOB/BIS/eFiling/HUB filings joined to this account by exact canonical BBL. Cooling-tower classification requires explicit published source text. Applicant and owner names are recorded project roles—not proof of a maintenance contract, current service provider, current ownership or cooling-tower responsibility. This evidence does not alter Priority Score 1.0 and is not backfilled into Monitor as a newly occurring event.</p>
  </section>
}
