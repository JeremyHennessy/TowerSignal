import type { NysMetadata, NysSystem } from '../types/nys'
import { formatDate, formatTimestamp } from '../domain/labels'

const resultLabel = (value: string | null) => {
  if (!value) return '—'
  const labels: Record<string, string> = {
    lt10: '<10',
    lt20: '<20',
    gteq20butlt100: '≥20 to <100',
    gteq100butlt1000: '≥100 to <1,000',
    gteq1000: '≥1,000',
    gt10lt1000: '>10 to <1,000',
  }
  return labels[value] ?? value
}

export function NysDetailPanel({ row, metadata, onClose }: { row: NysSystem | null; metadata: NysMetadata; onClose: () => void }) {
  if (!row) return null
  const sourceHealth = metadata.source_health?.find(entry => entry.source_key === 'nys_registry')
  return <aside className="detail-panel" aria-label="Selected NYS cooling tower equipment detail">
    <div className="detail-header"><div><span className="eyebrow">NYS registry equipment</span><h2>{row.address ?? row.system_id}</h2><p>{row.city ?? 'City unavailable'} {row.zip ?? ''} · Equipment <span className="mono">{row.source_equipment_id}</span></p></div><button className="icon-button" onClick={onClose} aria-label="Close details">×</button></div>

    <section><h3>Source-native status</h3><dl className="identity-grid"><div><dt>Registration compliance</dt><dd>{row.regulation_compliance ?? '—'}</dd></div><div><dt>Cooling-tower status</dt><dd>{row.ct_status?.replaceAll('_', ' ') ?? '—'}</dd></div><div><dt>Last sample result</dt><dd>{resultLabel(row.latest_sample_result)}</dd></div><div><dt>Last sample date</dt><dd>{row.latest_sample_date ? formatDate(row.latest_sample_date) : '—'}</dd></div><div><dt>Operation duration</dt><dd>{row.operation_duration ?? '—'}</dd></div><div><dt>Property equipment records</dt><dd>{row.property_equipment_count.toLocaleString()}</dd></div></dl><p className="microcopy">These values are represented directly from the New York State Cooling Tower Registry Weekly Extract. TowerSignal does not apply NYC Priority Score, NYC Health inspection rules, OATH, PLUTO or HPD semantics to this NYS source regime.</p></section>

    <section><h3>Location & identity</h3><dl className="identity-grid"><div><dt>TowerSignal ID</dt><dd className="mono">{row.system_id}</dd></div><div><dt>Source Equipment_ID</dt><dd className="mono">{row.source_equipment_id}</dd></div><div><dt>Published county</dt><dd>{row.source_county ?? '—'}</dd></div><div><dt>Coordinate status</dt><dd>{row.coordinate_status}</dd></div><div><dt>Coordinates</dt><dd>{row.latitude != null && row.longitude != null ? `${row.latitude.toFixed(5)}, ${row.longitude.toFixed(5)}` : 'Not mapped'}</dd></div><div><dt>Exact property key</dt><dd>{row.property_key ?? '—'}</dd></div></dl><p className="microcopy">Published county is preserved for provenance but is not used alone to infer NYC geography because the live source contains demonstrably inconsistent county labels. Property grouping uses only case/whitespace-normalized published street address + city + ZIP; no fuzzy or geocoded entity match is performed.</p></section>

    <section><h3>Source recency fields</h3><dl className="identity-grid"><div><dt>Last update counter</dt><dd>{row.last_update_days == null ? '—' : `${row.last_update_days} days`}</dd></div><div><dt>Last sampled counter</dt><dd>{row.last_sampled_days == null ? '—' : `${row.last_sampled_days} days`}</dd></div></dl><p className="microcopy">These are relative counters published by the source. TowerSignal displays them as context but does not convert their daily increment into historical change events or independently infer non-compliance from them.</p></section>

    <section><h3>Source & provenance</h3><div className="source-row"><strong>{metadata.source.name}</strong><span>Dataset {metadata.source.dataset_id} · retrieved {formatTimestamp(metadata.source.retrieved_at)}</span><small>Source updated {metadata.source.source_last_updated_at ? formatTimestamp(metadata.source.source_last_updated_at) : 'not published'} · current source rows {metadata.source.source_record_count.toLocaleString()}</small></div>{sourceHealth && <div className="source-row"><strong>Source health: {sourceHealth.status}</strong><span>{sourceHealth.attached_entity_count.toLocaleString()} attached · {sourceHealth.displayed_entity_count.toLocaleString()} represented</span><small>{sourceHealth.coverage_note}</small></div>}<p className="microcopy">{metadata.source.scope_note}</p></section>
  </aside>
}