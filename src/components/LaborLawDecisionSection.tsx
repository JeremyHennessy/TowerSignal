import type { SystemDetail } from '../types/data'
import { formatDate } from '../domain/labels'

type LaborLawRecord = {
  decision_id: string
  title?: string | null
  decision_url?: string | null
  publication_date?: string | null
  labor_law_sections?: string[]
  index_numbers?: string[]
  case_numbers?: string[]
  nyscef_document_numbers?: string[]
  published_subject_address?: string | null
  matched_normalized_address?: string | null
  property_system_ids?: string[]
  match_basis: 'PUBLISHED_DECISION_EXPLICIT_WORKSITE_ADDRESS_EXACT'
  fact_class: 'CONFIRMED_FACT'
  evidence_confidence: 'CONFIRMED'
  building_level_context: true
  liability_claim: false
  source?: string | null
}

type LaborLawContext = {
  records: LaborLawRecord[]
  source: {
    name?: string
    url?: string
    retrieved_at?: string
    source_health_status?: 'WARNING' | 'HEALTHY' | 'FAILED'
    source_health_reasons?: string[]
    source_query_scope?: string
    current_filing_status_available?: boolean
  }
  evidence_boundaries: {
    coverage?: string
    property_identity?: string
    building_level?: string
    liability?: string
    scoring?: string
    absence?: string
  }
  generated_at?: string
}

type DetailWithLaborLaw = SystemDetail & { labor_law_published_decisions?: LaborLawContext }

export function LaborLawDecisionSection({ detail }: { detail: DetailWithLaborLaw }) {
  const context = detail.labor_law_published_decisions
  const records = context?.records ?? []
  if (!context || records.length === 0) return null
  return <section className="property-context-section" aria-label="Labor Law published decision evidence">
    <h3>Labor Law published-decision evidence</h3>
    <div className="property-coverage-callout"><strong>Published court decision · partial case coverage</strong><p>{context.evidence_boundaries.coverage ?? 'Official Reports covers appellate decisions and selected trial-court decisions; this is not a comprehensive filing or docket feed.'}</p></div>
    <div className="signal-list">{records.map(record => <article className="signal-card" key={record.decision_id}><div className="signal-card-head"><strong>{record.title ?? 'Published Labor Law decision'}</strong><span className="status-chip">Exact worksite address</span></div><dl className="identity-grid"><div><dt>Decision date</dt><dd>{record.publication_date ? formatDate(record.publication_date) : 'Date not published'}</dd></div><div><dt>Published worksite</dt><dd>{record.published_subject_address ?? '—'}</dd></div><div><dt>Labor Law sections</dt><dd>{record.labor_law_sections?.join(', ') || 'Mentioned; section not parsed'}</dd></div><div><dt>Index / case</dt><dd>{[...(record.index_numbers ?? []), ...(record.case_numbers ?? [])].join(', ') || 'Not parsed from published text'}</dd></div></dl>{record.decision_url && <a className="table-link" href={record.decision_url} target="_blank" rel="noreferrer">Open official published decision ↗</a>}</article>)}</div>
    <p className="microcopy">Building-level litigation context only. The decision text itself supplied the subject worksite address and TowerSignal matched that address exactly. It does not identify an individual cooling tower, prove current liability or safety condition, establish service responsibility, or affect Priority Score.</p>
  </section>
}
