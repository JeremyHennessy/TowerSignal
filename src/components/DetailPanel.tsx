import { useEffect, useState } from 'react'
import { loadSystemDetail } from '../data/api'
import { formatDate, formatTimestamp } from '../domain/labels'
import { leadSummary } from '../utils/export'
import type { Metadata, SystemDetail, SystemSummary } from '../types/data'
import { StatusBadge } from './StatusBadge'

export function DetailPanel({ row, metadata, onClose }: { row: SystemSummary | null; metadata: Metadata; onClose: () => void }) {
  const [detail, setDetail] = useState<SystemDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  useEffect(() => {
    setDetail(null); setError(null); setCopied(false)
    if (!row) return
    loadSystemDetail(row.system_id).then(setDetail).catch(err => setError(err instanceof Error ? err.message : 'Unable to load system details'))
  }, [row])
  if (!row) return null
  const copy = async () => { await navigator.clipboard.writeText(leadSummary(row, metadata)); setCopied(true) }
  return <aside className="detail-panel" aria-label="Selected cooling tower detail">
    <div className="detail-header"><div><span className="eyebrow">Selected system</span><h2>{row.address ?? row.system_id}</h2><p>{row.borough} {row.zip} · System <span className="mono">{row.system_id}</span></p></div><button className="icon-button" onClick={onClose} aria-label="Close details">×</button></div>
    <div className="detail-actions"><button onClick={copy}>{copied ? 'Copied' : 'Copy lead summary'}</button><span className="score large">{row.priority_score}</span><span>Priority score</span></div>
    {error && <div className="error-state">{error}</div>}
    {!detail && !error && <div className="loading-state">Loading source-backed details…</div>}
    {detail && <>
      <section><h3>Identity</h3><dl className="identity-grid"><div><dt>BIN</dt><dd>{detail.identity.bin ?? '—'}</dd></div><div><dt>BBL</dt><dd>{detail.identity.bbl ?? '—'}</dd></div><div><dt>Active equipment</dt><dd>{detail.identity.active_equipment}</dd></div><div><dt>Coordinates</dt><dd>{detail.identity.coordinate_status === 'VALID' && detail.identity.latitude != null && detail.identity.longitude != null ? `${detail.identity.latitude.toFixed(4)}, ${detail.identity.longitude.toFixed(4)}` : detail.identity.coordinate_status === 'INVALID_SOURCE' ? `Unusable source coordinates (${detail.identity.source_latitude_raw ?? 'blank'}, ${detail.identity.source_longitude_raw ?? 'blank'})` : 'Not published'}</dd></div></dl></section>
      <section><h3>Current TowerSignal signals</h3>{detail.signals.length === 0 ? <div className="empty-inline">No current priority signal was generated.</div> : <div className="signal-list">{detail.signals.map(signal => <article key={signal.type} className={`signal-card signal-card-${signal.evidence_confidence.toLowerCase()}`}><div className="signal-card-head"><strong>{signal.title}</strong><StatusBadge value={signal.evidence_confidence} /></div><div className="fact-class">{signal.fact_class.replaceAll('_',' ')}</div>{signal.date && <div className="signal-date">{formatDate(signal.date)}</div>}<p>{signal.reason}</p></article>)}</div>}</section>
      <section><h3>Sample history</h3>{detail.sample_history.dates.length === 0 ? <div className="empty-inline">No usable public sample history is present in this registration record.</div> : <ol className="timeline">{[...detail.sample_history.dates].reverse().map((dateValue,index,dates) => <li key={dateValue}><strong>{formatDate(dateValue)}</strong>{index === 0 && <span className="latest-tag">Latest</span>}{index < dates.length - 1 && <small>{Math.round((new Date(`${dates[index]}T00:00:00`).getTime()-new Date(`${dates[index+1]}T00:00:00`).getTime())/86400000)} days since prior reported sample</small>}</li>)}</ol>}{detail.sample_history.malformed_values.length > 0 && <p className="warning-note">Unparseable public value(s) retained for provenance: {detail.sample_history.malformed_values.join(', ')}</p>}</section>
      <section><h3>NYC Health inspection history</h3>{detail.inspection_history.length === 0 ? <div className="empty-inline">No published NYC Health inspection history was joined to this system.</div> : detail.inspection_history.map((inspection,index) => <details key={`${inspection.inspection_date}-${inspection.inspection_type}-${index}`} open={index===0}><summary><span>{formatDate(inspection.inspection_date)} · {inspection.inspection_type}</span><strong>{inspection.violation_count} violation{inspection.violation_count === 1 ? '' : 's'}</strong></summary>{inspection.violation_count === 0 ? <p className="inspection-clear">Published row contains no violation/citation values.</p> : inspection.violations.map((violation,vIndex) => <div className="violation-detail" key={`${violation.summons_number}-${vIndex}`}><div><strong>{violation.violation_type ?? 'Violation'}</strong> · {violation.violation_code ?? 'No code'}</div><p>{violation.violation_text ?? violation.citation_text ?? 'No description published.'}</p><small>{violation.law_section ?? 'No law section'}{violation.summons_number ? ` · Summons ${violation.summons_number}` : ''}</small></div>)}</details>)}</section>
      <section><h3>Why this score</h3>{detail.scoring.components.length ? <ul className="score-list">{detail.scoring.components.map((component,index) => <li key={`${component.reason}-${index}`}><strong>+{component.points}</strong><span>{component.reason}</span></li>)}</ul> : <div className="empty-inline">No priority points were assigned.</div>}<p className="microcopy">Commercial research-priority score only. Not a health-risk, safety, or compliance score. Model {detail.scoring.priority_model_version}.</p></section>
      <section><h3>Source & provenance</h3><p>Generated {formatTimestamp(detail.metadata.generated_at)} · Rules {detail.metadata.rules_version} · Priority model {detail.metadata.priority_model_version}</p>{detail.metadata.sources.map(source => <div className="source-row" key={source.dataset_id}><strong>{source.name}</strong><span>{source.dataset_id} · {source.source_record_count.toLocaleString()} source rows</span><small>Retrieved {formatTimestamp(source.retrieved_at)}{source.source_last_updated_at ? ` · Source last updated ${formatTimestamp(source.source_last_updated_at)}` : ''}</small></div>)}</section>
    </>}
  </aside>
}
