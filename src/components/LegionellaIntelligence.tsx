import { useEffect, useMemo, useState } from 'react'
import type { LegionellaAlertItem, LegionellaAlertPayload } from '../types/enforcement'
import { formatDate, formatTimestamp } from '../domain/labels'
import { sourceDay } from '../domain/changePresentation'
import '../styles/home-intelligence.css'
import { resultLabel } from './OfficialBuildingEvidence'

function itemKind(item: LegionellaAlertItem): string {
  const path = new URL(item.url).pathname
  if (path.includes('/about/press/') || path.includes('/mayors-office/news')) return 'News release'
  if (item.document_type === 'NOTIFY_NYC_ALERT' || path.includes('/han/')) return 'Health alert'
  return item.document_type === 'PDF' ? 'Source document' : 'Guidance'
}
function titleText(item: LegionellaAlertItem): string {
  const raw = (item.title ?? 'Official Legionella update').replace(/\s+-\s+(NYC Health|NYC Mayor's Office)\s*$/i, '')
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)+$/.test(raw)) return raw
  return raw.split('-').map(word => /^(nyc|nys|pcr|ues|dohmh)$/.test(word) ? word.toUpperCase() : word[0].toUpperCase() + word.slice(1)).join(' ')
}
function agencyText(item: LegionellaAlertItem): string {
  // An item's discovery channel is not necessarily its publisher.
  return new URL(item.url).pathname.includes('/mayors-office/') ? "NYC Mayor's Office" : item.agency
}
function validPayload(value: unknown): value is LegionellaAlertPayload {
  const payload = value as LegionellaAlertPayload | null
  return payload?.domain === 'LEGIONELLA_PUBLIC_HEALTH_ALERTS' && Array.isArray(payload.items)
    && typeof payload.summary?.source_channel_count === 'number'
    && payload.items.every(item => {
      try { return typeof item.item_id === 'string' && new URL(item.url).protocol === 'https:' } catch { return false }
    })
}

export function LegionellaIntelligence() {
  const [payload, setPayload] = useState<LegionellaAlertPayload | null>(null)
  const [error, setError] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('news')
  const [page, setPage] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    setError(false)
    fetch(`${import.meta.env.BASE_URL}data/legionella-alerts.json`, { cache: 'no-store', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const result: unknown = await response.json()
        if (!validPayload(result)) throw new Error('Malformed official intelligence payload')
        if (!controller.signal.aborted) setPayload(result)
      })
      .catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [attempt])
  const items = useMemo(() => (payload?.items ?? []).filter(item => {
    const news = ['News release', 'Health alert'].includes(itemKind(item))
    if (category === 'news' && !news || category === 'documents' && news) return false
    return `${titleText(item)} ${agencyText(item)} ${(item.building_links ?? []).map(link => link.address).join(' ')}`.toLowerCase().includes(query.trim().toLowerCase())
  }).sort((a, b) => (sourceDay(b.published_date) ?? '').localeCompare(sourceDay(a.published_date) ?? '') || a.item_id.localeCompare(b.item_id)), [payload, category, query])
  const pageSize = 6
  const pages = Math.max(1, Math.ceil(items.length / pageSize))
  const activePage = Math.min(page, pages - 1)
  const visible = items.slice(activePage * pageSize, (activePage + 1) * pageSize)

  return <section className="home-intelligence" aria-label="Legionnaires official intelligence">
    <header className="home-intelligence-header">
      <div><span className="page-kicker">Public health watch</span><h2>Legionnaires official intelligence</h2><p>Official updates linked to named buildings and their registered tower accounts.</p></div>
      <div className="home-intelligence-status">{payload && <><span>{payload.summary.source_channel_count} official channels</span><small>Source check {formatDate(payload.generated_at)}</small></>}<a href="#/source-health">Source health & coverage →</a></div>
    </header>
    {error ? <div className="home-intelligence-empty" role="alert"><strong>Official intelligence could not be loaded.</strong><p>This does not mean there are no alerts.</p><button onClick={() => setAttempt(value => value + 1)}>Try again</button></div>
      : !payload ? <p className="home-intelligence-empty" role="status">Loading official public health intelligence…</p>
        : <>
          <div className="home-intelligence-toolbar">
            <div className="home-intelligence-tabs" role="tablist" aria-label="Official intelligence categories">{[['news', 'News & alerts'], ['documents', 'Guidance & documents'], ['all', 'All records']].map(([value, label]) => <button key={value} role="tab" aria-selected={category === value} className={category === value ? 'active' : ''} onClick={() => { setCategory(value); setPage(0) }}>{label}</button>)}</div>
            <label><span className="intelligence-sr-only">Search official intelligence</span><input type="search" placeholder="Search headlines, sources or buildings" value={query} onChange={event => { setQuery(event.target.value); setPage(0) }} /></label>
          </div>
          {payload.summary.retrieval_error_count > 0 && <p className="home-intelligence-warning">{payload.summary.retrieval_error_count} source retrievals failed. Retained records are shown; source coverage is incomplete.</p>}
          {items.length === 0 ? <div className="home-intelligence-empty"><strong>No records match these filters.</strong><p>Try another category or search term.</p></div> : <div className="home-intelligence-scroll"><table className="home-intelligence-table">
            <thead><tr><th scope="col">Published / revised</th><th scope="col">Official update</th><th scope="col">Source</th><th scope="col"><span className="intelligence-sr-only">Open source</span></th></tr></thead>
            <tbody>{visible.map(item => <tr key={item.item_id}>
              <td data-label="Published"><time dateTime={sourceDay(item.published_date) ?? undefined}>{sourceDay(item.published_date) ? formatDate(sourceDay(item.published_date)) : 'Date not published'}</time><span className="home-intelligence-kind">{itemKind(item)}</span></td>
              <td><a className="home-intelligence-title" href={item.url} target="_blank" rel="noreferrer">{titleText(item)}</a>{Boolean(item.building_links?.length) && <span className="home-intelligence-match-count">{item.linked_building_count} named buildings · {item.building_links?.length} system links</span>}<details className="home-intelligence-provenance"><summary>Evidence & tower links</summary><p>Source retrieved {formatTimestamp(item.retrieved_at)}. The date above is the publication or document-revision date, not the collection date.</p>{item.building_links?.length ? <><p>{item.building_links[0].link_basis === 'RELATED_EPISODE_UPDATE' ? 'Related investigation update. These buildings are identified in separate official result lists, not necessarily named in this article. Each result links to its actual source.' : 'Buildings explicitly named in this source, resolved to a unique BIN. All registered systems at that building are listed; individual tested-system identity is not published.'}</p><ul className="home-intelligence-tower-links">{item.building_links.map(link => <li key={link.system_id}><a href={`#/account/${link.system_id}`}>{link.system_address} →</a><small>{link.system_id} · BIN {link.bin} · {resultLabel(link.result)}{link.episode_status === 'CLOSED' ? ' · Historical / episode closed' : ''}</small><a href={link.source_url} target="_blank" rel="noreferrer">Building evidence source ↗</a></li>)}</ul></> : <p>No verified named-building match for this record. General guidance or a neighborhood mention is not evidence against an individual tower.</p>}</details></td>
              <td data-label="Source"><span className="home-intelligence-agency">{agencyText(item)}</span><small>{item.document_type === 'PDF' ? 'Official PDF' : 'Official source'}</small></td>
              <td><a className="home-intelligence-open" href={item.url} target="_blank" rel="noreferrer" aria-label={`Open official source: ${titleText(item)}`}>Read source <span aria-hidden="true">↗</span></a></td>
            </tr>)}</tbody>
          </table></div>}
          <p className="home-intelligence-link-note">Building matches are not outbreak-source attribution. Positive tests, completed cleaning and historical results remain distinct. <a href="data/legionella-tower-links.json" target="_blank" rel="noreferrer">Matching coverage & unresolved addresses ↗</a></p>
          <footer className="home-intelligence-footer"><span>{items.length ? `${activePage * pageSize + 1}–${Math.min((activePage + 1) * pageSize, items.length)} of ${items.length}` : '0 matching records'} · {payload.items.length} retained records</span><div><button disabled={activePage === 0} onClick={() => setPage(value => value - 1)}>Previous</button><span>{activePage + 1} / {pages}</span><button disabled={activePage === pages - 1} onClick={() => setPage(value => value + 1)}>Next</button></div></footer>
        </>}
  </section>
}
