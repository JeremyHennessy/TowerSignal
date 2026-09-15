import type { LegionellaBuildingLink } from '../types/enforcement'
import { formatDate } from '../domain/labels'
import '../styles/official-building-evidence.css'

export function resultLabel(value: string): string {
  const labels: Record<string, string> = { PCR_POSITIVE_REMEDIATION_ORDER: 'PCR positive · remediation ordered', PCR_NEGATIVE: 'PCR negative', CULTURE_POSITIVE: 'Culture positive', CULTURE_NEGATIVE: 'Culture negative', CULTURE_PENDING: 'Culture result pending', PCR_LIST_CLEANING_COMPLETE: 'PCR list · cleaning complete', UNREGISTERED_BUILDING_LISTED: 'Unregistered building listed' }
  return labels[value] ?? value.replaceAll('_', ' ').toLowerCase()
}
export function OfficialBuildingEvidence({ records }: { records: LegionellaBuildingLink[] }) {
  if (!records.length) return null
  return <section className="official-building-evidence" aria-label="Official building health evidence">
    <h3>Official Legionella building evidence</h3>
    <p>Published building results linked to this account by normalized address and borough, resolving to one BIN. The source does not identify which individual system at a multi-system building was tested.</p>
    <div className="official-building-records">{records.map((record, index) => <article key={`${record.source_url}-${index}`}>
      <div><strong>{resultLabel(record.result)}</strong><span className={record.episode_status === 'CLOSED' ? 'official-status-closed' : 'official-status-followup'}>{record.episode_status === 'CLOSED' ? 'Historical · episode closed' : 'Published investigation evidence'}</span></div>
      <p>{record.address} · BIN {record.bin}</p>
      <small>{record.event_date ? `Order date ${formatDate(record.event_date)} · ` : ''}{record.date_basis === 'DOCUMENT_REVISION_DATE' ? 'Document revised' : 'Published'} {formatDate(record.source_date)}. Sample collection date is not supplied in this list.</small>
      <a href={record.source_url} target="_blank" rel="noreferrer">Read the named-building source ↗</a>
      {record.closure_source_url && <small>{record.episode_closed_at ? `Episode closure published ${formatDate(record.episode_closed_at)}.` : 'Cluster investigation reported closed; closure date is not supplied in this result record.'} <a href={record.closure_source_url} target="_blank" rel="noreferrer">Official closure status ↗</a></small>}
    </article>)}</div>
    <p className="microcopy">PCR positivity is not proof of live bacteria. Culture positivity is not proof that this building caused the outbreak. Historical results and published remediation/closure are retained, not treated as a current positive test.</p>
  </section>
}
