import { formatDate, formatTimestamp } from '../domain/labels'
import type { Metadata, SystemDetail, SystemSummary } from '../types/data'
import type { AcrisMetadataFields, AcrisPropertyActivity, AcrisSummaryFields } from '../types/acris'

const money = (value: number | null) => value == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value)
const partyAddress = (party: { address_1: string | null; address_2: string | null; city: string | null; state: string | null; zip: string | null }) => [party.address_1, party.address_2, party.city, party.state, party.zip].filter(Boolean).join(', ') || 'Address not published'

export function AcrisActivitySection({ row, detail, metadata }: { row: SystemSummary; detail: SystemDetail; metadata: Metadata }) {
  const meta = metadata as Metadata & AcrisMetadataFields
  const enrichedRow = row as SystemSummary & AcrisSummaryFields
  const enrichedDetail = detail as SystemDetail & { acris_activity?: AcrisPropertyActivity | null }

  if (!meta.acris_cache_available) {
    return <section><h3>ACRIS property activity</h3><div className="empty-inline">The independently verified ACRIS cache is unavailable for this snapshot, so TowerSignal omits ACRIS timing context rather than substituting or inferring transaction data.</div><p className="microcopy">Other TowerSignal sources and the NYC Priority Score remain independent of ACRIS.</p></section>
  }

  const activity = enrichedDetail.acris_activity
  if (!activity) {
    return <section><h3>ACRIS property activity</h3><div className="empty-inline">No commercially relevant ACRIS document was matched to this exact BBL in the current {meta.acris_cache_lookback_days ?? 365}-day verified cache.</div><p className="microcopy">No cached match is not evidence that the property has never been sold, financed, leased or otherwise recorded. The bounded cache is timing intelligence only and does not affect TowerSignal's NYC Priority Score.</p></section>
  }

  return <section><h3>ACRIS property activity</h3>
    <p>{activity.recent_document_count.toLocaleString()} relevant recorded document{activity.recent_document_count === 1 ? '' : 's'} in the verified {meta.acris_cache_lookback_days ?? 365}-day window{activity.latest_recorded_date ? ` · latest ${formatDate(activity.latest_recorded_date)}` : ''}.</p>
    <dl className="identity-grid"><div><dt>Deeds</dt><dd>{(enrichedRow.acris_deed_count ?? activity.deed_count).toLocaleString()}</dd></div><div><dt>Mortgages</dt><dd>{(enrichedRow.acris_mortgage_count ?? activity.mortgage_count).toLocaleString()}</dd></div><div><dt>Leases</dt><dd>{(enrichedRow.acris_lease_count ?? activity.lease_count).toLocaleString()}</dd></div><div><dt>Recorded party rows</dt><dd>{(enrichedRow.acris_recorded_party_count ?? activity.recorded_party_count).toLocaleString()}</dd></div></dl>
    {activity.documents.map((document, index) => <details key={`${document.document_id}-${index}`} open={index === 0}><summary><span>{document.recorded_date ? formatDate(document.recorded_date) : 'Recorded date not published'} · {document.doc_type ?? 'ACRIS document'}</span><strong>{document.document_amount != null ? money(document.document_amount) : document.document_id}</strong></summary><div className="violation-detail"><dl className="identity-grid"><div><dt>Document ID</dt><dd className="mono">{document.document_id}</dd></div><div><dt>CRFN</dt><dd>{document.crfn ?? '—'}</dd></div><div><dt>Document date</dt><dd>{document.document_date ? formatDate(document.document_date) : '—'}</dd></div><div><dt>Recorded date</dt><dd>{document.recorded_date ? formatDate(document.recorded_date) : '—'}</dd></div><div><dt>Document amount</dt><dd>{money(document.document_amount)}</dd></div><div><dt>Percent transferred</dt><dd>{document.percent_transferred == null ? '—' : `${document.percent_transferred}%`}</dd></div></dl>{document.legal_context.length > 0 && <p>{document.legal_context.map(item => [item.street_number, item.street_name, item.unit].filter(Boolean).join(' ')).filter(Boolean).join(' · ')}</p>}{document.parties.length === 0 ? <div className="empty-inline">No party rows were published for this exact document ID.</div> : <div className="signal-list">{document.parties.slice(0, 8).map((party, partyIndex) => <article className="signal-card" key={`${party.party_type ?? 'party'}-${party.name ?? partyIndex}-${partyIndex}`}><div className="signal-card-head"><strong>{party.name ?? 'Party name not published'}</strong><span>Party type {party.party_type ?? '—'}</span></div><p>{partyAddress(party)}</p></article>)}</div>}{document.parties.length > 8 && <p className="microcopy">{(document.parties.length - 8).toLocaleString()} additional recorded party rows are retained in the verified cache but omitted from this compact view.</p>}</div></details>)}
    {activity.recent_document_count > activity.displayed_document_count && <p className="microcopy">Showing the {activity.displayed_document_count.toLocaleString()} most recent documents of {activity.recent_document_count.toLocaleString()} matched documents for browser performance.</p>}
    <p className="microcopy">ACRIS is joined by exact borough/block/lot BBL and exact document ID only. A recorded document party is not asserted to be the current property owner, cooling-tower operator, procurement contact, service provider or vendor. ACRIS timing context does not change the NYC Priority Score. Verified cache generated {meta.acris_cache_generated_at ? formatTimestamp(meta.acris_cache_generated_at) : 'time unavailable'}.</p>
  </section>
}
