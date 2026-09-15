import { useEffect, useState } from 'react'
import { formatDate, formatTimestamp } from '../domain/labels'
import type { LegionellaBuilding, LegionellaIncident, LegionellaTowerLinks } from '../types/legionella'
import { initialFilters } from './Filters'
import '../styles/legionella-links.css'

const resultLabels: Record<string, string> = {
  PCR_POSITIVE: 'PCR-positive list', CULTURE_POSITIVE: 'Culture positive', CULTURE_NEGATIVE: 'Culture negative', CULTURE_PENDING: 'Culture pending in this report',
}
const remediationLabels: Record<string, string> = { CLEANING_ORDER_REPORTED: 'Cleaning ordered', CLEANING_COMPLETE_REPORTED: 'Cleaning complete reported' }

function incidentLink(eventId: string, kind: string, mode = 'prospect') {
  // Explicit empty criteria clear prior filters, including a previously selected borough.
  const query = new URLSearchParams(Object.fromEntries(Object.keys(initialFilters).map(key => [key, ''])))
  query.set('legionellaEvent', eventId)
  query.set('legionellaMatch', kind)
  return `#/${mode}?${query}`
}

function BuildingEvidence({ building }: { building: LegionellaBuilding }) {
  return <div className="legionella-observations">{building.observations.map(observation => <div key={observation.observation_id}>
    <strong>{resultLabels[observation.result] ?? observation.result}</strong>
    <span>{observation.source_date ? `Reported ${formatDate(observation.source_date)}` : 'Live-page observation; test date not specified'}</span>
    {remediationLabels[observation.remediation] && <span>{remediationLabels[observation.remediation]}</span>}
    {observation.source_note && <small>{observation.source_note}</small>}
    <a href={observation.source_url} target="_blank" rel="noreferrer" title={`Source SHA-256 ${observation.content_sha256}`}>Source evidence</a>
  </div>)}</div>
}

function IncidentCard({ incident, payload, systemId }: { incident: LegionellaIncident; payload: LegionellaTowerLinks; systemId?: string }) {
  const relation = systemId ? payload.system_links[systemId]?.find(link => link.event_id === incident.event_id) : undefined
  const buildings = systemId ? incident.buildings.filter(building => building.resolution.systems.some(system => system.system_id === systemId)) : incident.buildings
  const status = incident.status === 'CONCLUDED_AS_REPORTED' ? 'Investigation concluded · historical results' : incident.status === 'INVESTIGATING_AS_REPORTED' ? 'Investigation ongoing as reported' : 'Incident status requires review'
  return <article className="legionella-incident" data-event-id={incident.event_id}>
    <div className="legionella-incident-heading"><div><span className="page-kicker">{status}</span><h4>{incident.name}</h4></div><span>{incident.borough}</span></div>
    {relation ? <p className="legionella-match-label"><strong>{relation.relationship === 'NAMED_BUILDING' ? 'Named building match' : 'Area context only'}</strong>{relation.relationship === 'NAMED_BUILDING' ? ' · Officially listed address resolved to this building’s BIN. Individual system not identified.' : ` · Registry ZIP matches ${incident.zip_codes.join(' / ')}. This source does not identify this building or report a test result for it.`}</p> : <p><strong>{incident.named_building_count}</strong> named buildings matched · <strong>{incident.named_system_count}</strong> registered systems at those buildings · <strong>{incident.area_only_system_count}</strong> additional area-only systems</p>}
    {relation?.relationship === 'NAMED_BUILDING' && !relation.shares_published_zip && <p className="legionella-match-note">The published address matches this building, although its registry ZIP differs from the alert ZIPs. It is included by address and BIN, not by geographic inference.</p>}
    <div className="legionella-actions"><a href={incidentLink(incident.event_id, 'named')}>View named systems</a><a href={incidentLink(incident.event_id, 'area')}>View area-only systems</a><a href={incidentLink(incident.event_id, 'named', 'map')}>Map named systems</a></div>
    {systemId ? buildings.map(building => <div key={building.published_address}><strong>Published address: {building.published_address}</strong><BuildingEvidence building={building} />{building.resolution.systems.length > 1 && <p className="microcopy">{building.resolution.systems.length} registered systems share this building. The notice does not specify which system or unit was tested.</p>}</div>) : <details className="legionella-building-details"><summary>Published building list and matched tower accounts ({incident.published_building_count})</summary><div className="table-scroll"><table className="legionella-building-table"><thead><tr><th>Published address</th><th>Matched tower accounts</th><th>Dated source evidence</th></tr></thead><tbody>{buildings.map(building => <tr key={building.published_address}>
      <td><strong>{building.published_address}</strong><small>{building.resolution.bin ? `BIN ${building.resolution.bin}` : building.resolution.status}</small></td>
      <td>{building.resolution.systems.length ? building.resolution.systems.map(system => <a key={system.system_id} href={`#/account/${system.system_id}`}>{system.address}<small>System {system.system_id} · ZIP {system.zip}</small></a>) : <span>Needs identity review. No account was invented or force-matched.</span>}{building.resolution.systems.length > 1 && <small>Building-level evidence; individual system unspecified.</small>}</td>
      <td><BuildingEvidence building={building} /></td>
    </tr>)}</tbody></table></div></details>}
    {incident.unresolved_building_count > 0 && !systemId && <p className="legionella-match-note">{incident.unresolved_building_count} published addresses remain unmatched or ambiguous and are retained for review.</p>}
    <details><summary>Related incident reports ({incident.related_articles.length})</summary><p className="microcopy">These reports concern the same incident. Named-building links come from the explicit building lists above, not from every article independently.</p><ul className="legionella-article-list">{incident.related_articles.map(article => <li key={article.item_id}><a href={article.url} target="_blank" rel="noreferrer">{payload.source_documents.find(source => source.source_url === article.url)?.title || article.title || 'Official incident report'}</a><span>{article.published_date ? formatDate(article.published_date) : 'Publication date unavailable'}</span></li>)}</ul></details>
  </article>
}

export function LegionellaLinksPanel({ systemId }: { systemId?: string }) {
  const [payload, setPayload] = useState<LegionellaTowerLinks | null>(null)
  const [error, setError] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${import.meta.env.BASE_URL}data/legionella-tower-links.json`, { cache: 'no-store', signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const data = await response.json() as LegionellaTowerLinks
        if (data.domain !== 'LEGIONELLA_TOWER_LINKS' || !Array.isArray(data.events) || !data.system_links || !Array.isArray(data.source_documents)) throw new Error('Malformed tower links')
        setPayload(data)
      })
      .catch(() => { if (!controller.signal.aborted) setError(true) })
    return () => controller.abort()
  }, [])
  const ids = new Set(systemId ? payload?.system_links[systemId]?.map(link => link.event_id) ?? [] : payload?.events.map(event => event.event_id) ?? [])
  return <section className="table-card legionella-linked-intelligence" aria-label="Legionnaires official intelligence">
    <div className="legionella-panel-heading"><div><span className="page-kicker">Public-health event intelligence</span><h3>Legionnaires incidents linked to towers</h3></div>{payload && <small>Sources checked {formatTimestamp(payload.generated_at)}</small>}</div>
    {error ? <p role="status">Tower matching is unavailable in this session. This is not a finding of zero incidents or a negative test result.</p> : !payload ? <p role="status">Loading source-backed tower matches…</p> : <>
      {payload.events.filter(event => ids.has(event.event_id)).map(incident => <IncidentCard key={incident.event_id} incident={incident} payload={payload} systemId={systemId} />)}
      {systemId && ids.size === 0 && <p>No location match in the reviewed incidents. This is not a negative test result or a complete outbreak history for this property.</p>}
      <p className="microcopy">{payload.evidence_boundary}</p>
      {!systemId && <p className="microcopy">{payload.coverage.related_article_count} of {payload.coverage.alert_items_considered} retained items linked to these incidents. {payload.coverage.scope} <a href={`${import.meta.env.BASE_URL}data/legionella-alerts.json`} target="_blank" rel="noreferrer">All retained source records</a></p>}
    </>}
  </section>
}
