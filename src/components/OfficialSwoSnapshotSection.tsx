import type { SystemDetail } from '../types/data'
import { formatDate } from '../domain/labels'
import { LaborLawDecisionSection } from './LaborLawDecisionSection'

type SnapshotRecord = {
  complaint_number: string
  bin: string
  borough?: string | null
  address?: string | null
  disposition_description?: string | null
  status_at_snapshot: 'ACTIVE' | 'RESCINDED'
  last_disposition_date?: string | null
  source_snapshot_committed_at: string
  current_status_claim: false
}

type SnapshotContext = {
  summary: { record_count?: number; active_at_snapshot_count?: number; rescinded_at_snapshot_count?: number; latest_disposition_date?: string | null }
  records: SnapshotRecord[]
  observation_status: 'MATCHED_DATED_OBSERVATION' | 'NO_MATCH_IN_DATED_SNAPSHOT' | 'NO_USABLE_BIN'
  source: {
    name?: string
    url?: string
    official_map_url?: string
    source_last_updated_at?: string | null
    source_observation_start_at?: string | null
    source_observation_end_at?: string | null
    source_health_status?: 'WARNING' | 'HEALTHY' | 'FAILED'
    source_health_reasons?: string[]
    current_status_available?: boolean
  }
}

type DetailWithSnapshot = SystemDetail & { property_enforcement_context?: { official_swo_snapshot?: SnapshotContext } }

export function OfficialSwoSnapshotSection({ detail }: { detail: DetailWithSnapshot }) {
  const context = detail.property_enforcement_context?.official_swo_snapshot
  const source = context?.source ?? {}
  const records = context?.records ?? []
  return <>
    {context && <section className="property-context-section" aria-label="Official DOB stop work order snapshot">
      <h3>Official DOB stop-work-order snapshot</h3>
      <div className="property-coverage-callout"><strong>Historical DOB snapshot · not current status</strong><p>Official DOB ACTIVE / RESCINDED observations are preserved exactly as published in the dated source. Release automation cannot verify a current SWO ledger, so TowerSignal does not carry these 2024 values forward as current.</p></div>
      <dl className="identity-grid"><div><dt>Source window</dt><dd>{source.source_observation_start_at && source.source_observation_end_at ? `${formatDate(source.source_observation_start_at)}–${formatDate(source.source_observation_end_at)}` : 'Dated source window'}</dd></div><div><dt>Snapshot updated</dt><dd>{source.source_last_updated_at ? formatDate(source.source_last_updated_at) : '2024'}</dd></div><div><dt>Exact BIN observations</dt><dd>{context.summary?.record_count ?? records.length}</dd></div><div><dt>Current status available</dt><dd>No</dd></div></dl>
      {records.length ? <div className="signal-list">{records.map((record, index) => <article className="signal-card" key={`${record.complaint_number}-${record.last_disposition_date ?? index}`}><div className="signal-card-head"><strong>{record.status_at_snapshot === 'ACTIVE' ? 'ACTIVE at dated snapshot' : 'RESCINDED at dated snapshot'}</strong><span className="status-chip">Exact BIN</span></div><p>{record.disposition_description ?? 'DOB stop-work-order disposition'}</p><dl className="identity-grid"><div><dt>Complaint</dt><dd>{record.complaint_number}</dd></div><div><dt>Last disposition</dt><dd>{record.last_disposition_date ? formatDate(record.last_disposition_date) : 'Date not published'}</dd></div><div><dt>BIN</dt><dd>{record.bin}</dd></div><div><dt>Address</dt><dd>{record.address ?? '—'}</dd></div></dl></article>)}</div> : <div className="empty-inline"><strong>{context.observation_status === 'NO_USABLE_BIN' ? 'No usable BIN for an exact snapshot join.' : 'No matching BIN observation in the dated DOB snapshot.'}</strong><p>This is not evidence that the property has no stop-work order now or had none outside the snapshot window.</p></div>}
      <p className="microcopy">Separate from TowerSignal's DOB complaint/disposition evidence. The official snapshot is source-backed historical context only and does not affect Priority Score.</p>
      {source.url && <a className="table-link" href={source.url} target="_blank" rel="noreferrer">Open pinned official DOB snapshot source ↗</a>}
    </section>}
    <LaborLawDecisionSection detail={detail} />
  </>
}
