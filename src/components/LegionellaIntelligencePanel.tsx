import { Fragment, useEffect, useMemo, useState } from 'react'
import type { LegionellaAlertPayload } from '../types/enforcement'
import type { LegionellaPropertyMatches } from '../types/legionellaIntelligence'
import { displayHeadline, officialDate, publicationKind, relatedEvidence, resultLabel } from '../utils/legionellaIntelligence'
import '../styles/legionella-intelligence.css'

const PAGE_SIZE = 6
const views = [{ key: 'all', label: 'All updates' }, { key: 'linked', label: 'Linked buildings' }, { key: 'reference', label: 'Reference library' }] as const
type View = typeof views[number]['key']

export function LegionellaIntelligencePanel() {
  const [alerts, setAlerts] = useState<LegionellaAlertPayload | null>(null)
  const [matches, setMatches] = useState<LegionellaPropertyMatches | null>(null)
  const [alertsError, setAlertsError] = useState(false)
  const [matchesError, setMatchesError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [view, setView] = useState<View>('all')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    async function read(name: string): Promise<unknown> {
      const response = await fetch(`${import.meta.env.BASE_URL}data/${name}`, { cache: 'no-store', signal: controller.signal })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      return response.json()
    }
    read('legionella-alerts.json').then(value => {
      const payload = value as LegionellaAlertPayload
      if (payload?.domain !== 'LEGIONELLA_PUBLIC_HEALTH_ALERTS' || !Array.isArray(payload.items) || !Number.isFinite(payload.summary?.source_channel_count)) throw new Error('Invalid alert contract')
      if (active) { setAlerts(payload); setAlertsError(false) }
    }).catch(() => { if (active) setAlertsError(true) })
    read('legionella-property-matches.json').then(value => {
      const payload = value as LegionellaPropertyMatches
      if (payload?.domain !== 'LEGIONELLA_PROPERTY_MATCHES' || !Array.isArray(payload.matched_observations) || !Array.isArray(payload.unresolved) || !Number.isFinite(payload.summary?.named_buildings_matched)) throw new Error('Invalid matching contract')
      if (active) { setMatches(payload); setMatchesError(false) }
    }).catch(() => { if (active) setMatchesError(true) })
    return () => { active = false; controller.abort() }
  }, [attempt])

  const rows = useMemo(() => (alerts?.items ?? []).map(item => ({ item, title: displayHeadline(item), kind: publicationKind(item), evidence: relatedEvidence(item, matches) }))
    .sort((a, b) => (b.item.published_date || '').localeCompare(a.item.published_date || '') || a.title.localeCompare(b.title)), [alerts, matches])
  const matching = useMemo(() => rows.filter(row => {
    if (view === 'linked' && !row.evidence.buildings.length && !row.evidence.unresolved.length) return false
    if (view === 'reference' && row.kind !== 'Guidance & reference' && row.item.published_date) return false
    const search = [row.title, row.item.agency, row.item.url, ...row.evidence.records.map(record => record.address), ...row.evidence.unresolved.map(record => record.address)].join(' ').toLowerCase()
    return search.includes(query.trim().toLowerCase())
  }), [rows, view, query])
  const pages = Math.max(1, Math.ceil(matching.length / PAGE_SIZE))
  const activePage = Math.min(page, pages - 1)
  const visible = matching.slice(activePage * PAGE_SIZE, (activePage + 1) * PAGE_SIZE)
  const latest = rows.find(row => row.item.published_date)?.item.published_date

  function chooseView(next: View) { setView(next); setPage(0); setExpanded(null) }
  return <section className="legionella-intelligence" aria-labelledby="legionella-intelligence-title">
    <header className="li-heading">
      <div><span className="li-eyebrow">Public health intelligence</span><h2 id="legionella-intelligence-title">Legionnaires official intelligence</h2><p>Official updates, source findings and the registered accounts connected to them.</p></div>
      {alerts && <span className="li-channel-badge"><span aria-hidden="true">◉</span> {alerts.summary.source_channel_count} official channels</span>}
    </header>
    {alertsError && <div className="li-notice" role="alert">Official updates could not be loaded. This is not a report of zero alerts. <button onClick={() => setAttempt(value => value + 1)}>Retry intelligence</button></div>}
    {!alerts && !alertsError && <p className="li-loading" role="status">Loading official intelligence…</p>}
    {alerts && <>
      <div className="li-metrics" aria-label="Official intelligence coverage">
        <div><strong>{alerts.items.length.toLocaleString()}</strong><span>Retained publications</span></div>
        <div><strong>{matches ? matches.summary.named_buildings_matched.toLocaleString() : '—'}</strong><span>Named buildings matched</span></div>
        <div><strong>{matches ? matches.summary.systems_with_named_building_evidence.toLocaleString() : '—'}</strong><span>Linked registered systems</span></div>
        <div className="li-date-metric"><strong>{officialDate(latest)}</strong><span>Latest dated publication</span></div>
      </div>
      {matchesError && <div className="li-notice" role="status">Building matching is unavailable for this snapshot. Publications remain available; missing matches do not mean no affected buildings.</div>}
      {alerts.summary.retrieval_error_count > 0 && <div className="li-notice" role="status">{alerts.summary.retrieval_error_count} source retrieval issue{alerts.summary.retrieval_error_count === 1 ? '' : 's'} reported. Retained publications are still shown; collection coverage is incomplete.</div>}
      <div className="li-toolbar">
        <div className="li-view-toggle" role="group" aria-label="Intelligence views">{views.map(option => <button key={option.key} type="button" aria-pressed={view === option.key} onClick={() => chooseView(option.key)}>{option.label}</button>)}</div>
        <label className="li-search"><span className="li-sr-only">Search official intelligence</span><span aria-hidden="true">⌕</span><input type="search" placeholder="Search updates or buildings" value={query} onChange={event => { setQuery(event.target.value); setPage(0); setExpanded(null) }} /></label>
      </div>
      <div className="li-table-wrap">
        <table className="li-table" aria-label="Official Legionnaires publications">
          <thead><tr><th scope="col">Published</th><th scope="col">Update & source</th><th scope="col">Evidence</th><th scope="col">Linked accounts</th></tr></thead>
          <tbody>{visible.map(({ item, title, kind, evidence }) => <Fragment key={item.item_id}>
            <tr className={expanded === item.item_id ? 'li-update-row li-update-expanded' : 'li-update-row'}>
              <td className="li-date-cell"><time dateTime={item.published_date || undefined}>{officialDate(item.published_date)}</time><span>{kind}</span></td>
              <td className="li-update-cell"><a href={item.url} target="_blank" rel="noreferrer" className="li-headline">{title}<span aria-hidden="true"> ↗</span></a><span className="li-source">{new URL(item.url).hostname.replace(/^www\./, '')} · {item.document_type === 'PDF' ? 'PDF document' : 'Official source'}</span></td>
              <td className="li-evidence-cell">{evidence.buildings.length > 0 ? <><span className={`li-pill ${evidence.historical ? 'li-pill-history' : 'li-pill-named'}`}>{evidence.historical ? 'Historical cluster' : evidence.direct ? 'Named-building evidence' : 'Related cluster evidence'}</span><span className="li-cell-note">{evidence.direct ? 'Addresses in this source' : 'Linked through a separate source'}</span></> : <><span className="li-pill li-pill-reference">{evidence.unresolved.length ? 'Match review needed' : kind === 'Guidance & reference' ? 'Reference' : 'Official update'}</span><span className="li-cell-note">{!matches ? 'Matching not available' : 'No named-building link established'}</span></>}</td>
              <td className="li-links-cell">{evidence.buildings.length > 0 || evidence.unresolved.length > 0 ? <button type="button" className="li-match-button" aria-expanded={expanded === item.item_id} aria-controls={`li-matches-${item.item_id}`} onClick={() => setExpanded(current => current === item.item_id ? null : item.item_id)}><strong>{evidence.buildings.length} building{evidence.buildings.length === 1 ? '' : 's'} <span aria-hidden="true">{expanded === item.item_id ? '−' : '+'}</span></strong><span>{evidence.systems} linked system{evidence.systems === 1 ? '' : 's'}{evidence.unresolved.length > 0 ? ` · ${evidence.unresolved.length} unresolved` : ''}</span></button> : <span className="li-unlinked">{matches ? 'Not linked' : 'Not assessed'}</span>}</td>
            </tr>
            {expanded === item.item_id && <tr className="li-expanded-row"><td colSpan={4}><div id={`li-matches-${item.item_id}`} className="li-match-detail">
              <div className="li-match-detail-heading"><div><h3>Buildings connected to this update</h3><p>{evidence.direct ? 'The source names these buildings. The linked accounts share the exact normalized address, borough and a single registry BIN.' : 'These buildings are named in a separate official source for the same cluster, not necessarily in this article. Each finding retains its own source and date.'}</p></div><span className="li-scope">Building-level match</span></div>
              <div className="li-building-grid">{evidence.buildings.map(records => {
                const building = records[0]
                const ids = [...new Set(records.flatMap(record => record.system_ids))].sort()
                return <article className="li-building" key={`${building.cluster_id}-${building.bin}`}><strong>{building.address}</strong><small>{building.borough} · BIN {building.bin}</small>{[...records].sort((a, b) => b.document_date.localeCompare(a.document_date)).map(record => <div className="li-finding" key={record.observation_id}><a href={record.source_url} target="_blank" rel="noreferrer">{resultLabel(record.result)} ↗</a><span>Document {officialDate(record.document_date)}</span>{record.completion === 'CLEANING_REPORTED_COMPLETE' && <small>Cleaning reported complete</small>}{record.cluster_status === 'CLOSED_REPORTED' && <small>Cluster investigation reported closed</small>}{record.action === 'REMEDIATION_ORDER_REPORTED' && <small>Cleaning order reported; completion not established</small>}</div>)}<div className="li-system-links">{ids.map(id => <a key={id} href={`#/account/${encodeURIComponent(id)}`} aria-label={`Open tower account ${id}`}>Account {id} <span aria-hidden="true">→</span></a>)}</div></article>
              })}</div>
              {evidence.unresolved.length > 0 && <details className="li-unresolved"><summary>{evidence.unresolved.length} published address record{evidence.unresolved.length === 1 ? '' : 's'} need identity review</summary><ul>{evidence.unresolved.map(record => <li key={record.observation_id}><strong>{record.address}</strong> · {record.borough} · {record.match_status === 'AMBIGUOUS' ? 'Ambiguous registry match' : 'No exact registry match established'}</li>)}</ul></details>}
              <p className="li-boundary">A building match does not identify which system tested positive or establish the source of illness. PCR findings, culture findings and geographic context are not interchangeable.</p>
            </div></td></tr>}
          </Fragment>)}</tbody>
        </table>
        {visible.length === 0 && <div className="li-empty" role="status"><strong>{view === 'linked' && !matches ? 'Building matches are not available yet.' : 'No publications match this view.'}</strong><span>Change the view or clear the search to see the retained official publications.</span><button onClick={() => { setQuery(''); chooseView('all') }}>Show all updates</button></div>}
      </div>
      <footer className="li-footer"><div><span aria-live="polite">{matching.length ? activePage * PAGE_SIZE + 1 : 0}–{Math.min((activePage + 1) * PAGE_SIZE, matching.length)} of {matching.length} publications</span><small>Collection {officialDate(alerts.generated_at)} · Building results are not outbreak attribution.</small></div><div className="li-pagination"><button aria-label="Previous intelligence page" disabled={activePage === 0} onClick={() => { setPage(activePage - 1); setExpanded(null) }}>←</button><span>Page {activePage + 1} / {pages}</span><button aria-label="Next intelligence page" disabled={activePage === pages - 1} onClick={() => { setPage(activePage + 1); setExpanded(null) }}>→</button></div></footer>
    </>}
  </section>
}
