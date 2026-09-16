import { useEffect, useMemo, useState } from 'react'
import type { SystemsPayload } from '../types/data'
import { formatTimestamp } from '../domain/labels'
import { countOrNull, enforcementCoverage, legionellaChannelRows, parseLegionellaHealth, safeSourceUrl, timestampOrNull, type LegionellaHealthPayload } from '../domain/sourceHealthExpansion'

const number = new Intl.NumberFormat('en-US')
const count = (value: number | null | undefined) => value == null ? 'Not reported' : number.format(value)
const date = (value: unknown) => timestampOrNull(value) ? formatTimestamp(String(value)) : 'Not reported'

const refreshContracts = [
  {
    source: 'Core NYC registry & building context',
    cadence: 'Daily · 10:17 UTC',
    path: 'Canonical Pages release',
    scope: 'Cooling-tower registrations and inspections, MapPLUTO, DOB NOW, HPD registrations/contacts, building footprints and planimetric tower context.',
    note: 'Live publisher queries are rebuilt daily. Historical publisher snapshots such as 2022 planimetrics keep their source-native observation date.',
  },
  {
    source: 'Property enforcement',
    cadence: 'Daily · 10:17 UTC',
    path: 'Canonical Pages release',
    scope: 'HPD violations, DOB SWO complaint/disposition evidence and FISP / Local Law 11 filings.',
    note: 'Exact BBL/BIN attachment only. SWO evidence is not an active-order ledger; FISP is not a generic Labor Law feed.',
  },
  {
    source: 'Legionnaires public-health intelligence',
    cadence: 'Daily · 10:17 UTC',
    path: 'Canonical Pages release + durable history',
    scope: 'Official NYC/NYS Legionella and Legionnaires channels, including the NYC Health topic and alert/news channels.',
    note: 'Current observations replace stable item identities while prior verified official items can be retained. ZIP context is not property attribution.',
  },
  {
    source: 'Water, CMS, procurement & NYS support',
    cadence: 'Daily · 10:17 UTC',
    path: 'Canonical Pages release',
    scope: 'Domestic-water, NYC water signals, CMS facilities, lead service lines, distribution water, City Record, NYS authorities, Open Book, NYCHA and NYS water-system sources.',
    note: 'Each collector retains its own exact-identity and source-availability guard. A missing source remains unverified rather than becoming zero.',
  },
  {
    source: 'ACRIS property activity',
    cadence: 'Daily · 08:23 UTC',
    path: 'Verified durable cache → daily Pages release',
    scope: 'Bounded recent ACRIS activity for the current TowerSignal property universe.',
    note: 'Built and independently sampled before persistence. The daily release rejects a cache older than 2 days.',
  },
  {
    source: 'Checkbook NYC procurement',
    cadence: 'Daily · 08:41 UTC',
    path: 'Verified durable cache → daily Pages release',
    scope: 'NYC Checkbook contract/vendor evidence used by procurement and company intelligence.',
    note: 'Validated before persistence. The daily release rejects a cache older than 2 days.',
  },
  {
    source: 'OATH lifecycle cache',
    cadence: 'Every 6 hours · :23 UTC',
    path: 'Verified durable history cache',
    scope: 'OATH summons lifecycle evidence; current exact summons matches are also queried during the NYC production build.',
    note: 'Six-hour refresh is intentionally stronger than the daily minimum.',
  },
  {
    source: 'Historical 311 building-water context',
    cadence: 'Daily · 10:17 UTC',
    path: 'Canonical Pages release',
    scope: '2010–2024 DEP water/lead service requests aggregated immediately by exact current TowerSignal BBL.',
    note: 'Recomputed daily for identity coverage, but the evidence remains historical and never becomes a current-condition or current-sales trigger.',
  },
] as const

function SourceLink({ url, label = 'Official source' }: { url: unknown; label?: string }) {
  const href = safeSourceUrl(url)
  return href ? <a href={href} target="_blank" rel="noreferrer">{label}</a> : <span>Source link not reported</span>
}

export function SourceHealthExpansion({ payload }: { payload: SystemsPayload }) {
  const properties = useMemo(() => enforcementCoverage(payload), [payload])
  const [alerts, setAlerts] = useState<LegionellaHealthPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    fetch(`${import.meta.env.BASE_URL}data/legionella-alerts.json`, { cache: 'no-store', signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error(`Legionnaires source health request failed: HTTP ${response.status}`)
        return response.json() as Promise<unknown>
      })
      .then(value => { if (!controller.signal.aborted) setAlerts(parseLegionellaHealth(value)) })
      .catch(reason => { if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Legionnaires source health unavailable') })
    return () => controller.abort()
  }, [])
  const channels = alerts ? legionellaChannelRows(alerts) : []

  return <>
    <div className="reference-table-card" data-testid="property-enforcement-source-health">
      <div className="reference-table-heading"><div><strong>Property enforcement coverage</strong><span>HPD violations, DOB SWO disposition evidence and Local Law 11 / FISP. Counts follow the currently loaded NYC accounts.</span></div></div>
      <div className="disclaimer">Dataset rows are the publisher's full dataset count. Retained records are the normalized, exact-key cohort records, not a claimed raw retrieval count. Matched properties are distinct BBLs or BINs; represented systems can share a property. Coverage is observed prevalence across {number.format(payload.systems.length)} systems, not completeness of citywide enforcement. Available means published provenance and account measurements are present; it is not a substitute for pagination or schema diagnostics.</div>
      <div className="reference-table-scroll"><table className="reference-table source-health-table"><thead><tr><th>Source</th><th>Availability</th><th>Dataset rows</th><th>Retained records</th><th>Requested properties</th><th>Matched properties</th><th>Represented systems</th><th>System coverage</th><th>Freshness &amp; evidence scope</th></tr></thead><tbody>
        {properties.map(source => <tr key={source.id}>
          <td><strong>{source.name}</strong><small>{source.id} · exact {source.unit}</small><SourceLink url={source.source?.url} /></td>
          <td><span className={`health-badge${source.available ? '' : ' health-warning'}`}>{source.available ? 'AVAILABLE' : 'UNVERIFIED'}</span></td>
          <td>{count(source.sourceRecords)}</td><td>{count(source.records)}</td>
          <td>{count(source.requested)} {source.unit}<small>Current account identity universe</small></td>
          <td>{count(source.matched)} {source.unit}</td><td>{count(source.attached)} / {number.format(source.totalSystems)}</td>
          <td>{source.coverage === null ? 'Not reported' : `${source.coverage.toFixed(1)}%`}</td>
          <td><span>Last retrieved: {date(source.retrievedAt)}</span><small>Publisher updated: {date(source.source?.source_last_updated_at)}</small><small>{source.source?.source_query_scope}</small><small>{source.note}</small><small>Raw retrieved count, pagination and schema diagnostics: not reported in account metadata.</small></td>
        </tr>)}
      </tbody></table></div>
      <div className="disclaimer"><strong>Evidence gaps remain explicit.</strong> HPD registration/contact coverage is a different source from HPD violations. SWO complaint dispositions do not establish whether an order is currently active. Generic Labor Law court filings are not supplied by FISP. A missing match is not proof of no violation, no filing or no enforcement.</div>
    </div>

    <div className="reference-table-card" data-testid="source-refresh-coverage">
      <div className="reference-table-heading"><div><strong>Production refresh coverage</strong><span>One canonical daily NYC release, with durable high-cost caches refreshed ahead of it and OATH refreshed more frequently.</span></div></div>
      <div className="disclaimer"><strong>Refresh time is not source observation time.</strong> A daily rebuild means TowerSignal checks the publisher or verified cache again; it does not make a historical source snapshot current. The 10:17 UTC production release is the deployment gate: source collection, validation, application build, hosted desktop/iPhone verification and history persistence must all succeed.</div>
      <div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Source family</th><th>Refresh cadence</th><th>Production path</th><th>Coverage</th><th>Operational boundary</th></tr></thead><tbody>
        {refreshContracts.map(contract => <tr key={contract.source}>
          <td><strong>{contract.source}</strong></td>
          <td><span className="health-badge">{contract.cadence}</span></td>
          <td>{contract.path}</td>
          <td>{contract.scope}</td>
          <td>{contract.note}</td>
        </tr>)}
      </tbody></table></div>
    </div>

    <div className="reference-table-card" data-testid="legionella-source-health">
      <div className="reference-table-heading"><div><strong>Legionnaires monitoring coverage</strong><span>Official NYC and NYS channels, retrieval evidence and retained history. Separate from account-identity coverage.</span></div></div>
      {error ? <div className="reference-empty-state"><strong>Legionnaires source health unavailable.</strong><span>{error}</span><span>No healthy status, zero-alert count or property attribution is inferred.</span></div> : !alerts ? <div className="reference-empty-state"><strong>Loading Legionnaires source health…</strong></div> : <>
        <div className="reference-metric-grid">
          <article><span className="reference-metric-icon">SRC</span><div><small>Channel snapshots retrieved</small><strong>{channels.filter(row => row.retrieved).length}/{channels.length}</strong><span>Snapshot evidence, not archive completeness</span></div></article>
          <article><span className="reference-metric-icon">DOC</span><div><small>Retained relevant items</small><strong>{number.format(alerts.items.length)}</strong><span>Not a count of active outbreaks</span></div></article>
          <article><span className="reference-metric-icon warning">ERR</span><div><small>Item retrieval errors</small><strong>{number.format(alerts.errors.length)}</strong><span>Failed child documents remain visible</span></div></article>
          <article><span className="reference-metric-icon">H</span><div><small>Prior items retained</small><strong>{count(countOrNull(alerts.history_merge?.retained_prior_item_count))}</strong><span>Old observations are not newly verified</span></div></article>
        </div>
        <div className="disclaimer">Cache assembled {date(alerts.generated_at)}. Source freshness is each snapshot's retrieval date below, not the rebuild date. {count(countOrNull(alerts.history_merge?.current_collection_item_count))} items were collected in that run. A successful channel snapshot does not prove that every historical alert or linked document was retrieved.</div>
        <div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Channel</th><th>Agency</th><th>Retrieval evidence</th><th>Last successful retrieval</th><th>Channel scope</th><th>Source</th></tr></thead><tbody>
          {channels.map(channel => <tr key={channel.key}>
            <td><strong>{channel.name}</strong></td><td>{channel.snapshot?.agency || 'Not reported'}</td>
            <td><span className={`health-badge${channel.retrieved ? '' : ' health-warning'}`}>{channel.retrieved ? 'SNAPSHOT RETRIEVED' : 'UNVERIFIED'}</span></td>
            <td>{date(channel.retrievedAt)}</td><td>{channel.snapshot?.channel_kind?.replaceAll('_', ' ') || 'Not reported'}</td><td><SourceLink url={channel.snapshot?.url} /></td>
          </tr>)}
        </tbody></table></div>
        {alerts.errors.length > 0 && <div className="reference-empty-state"><strong>Incomplete item retrieval</strong>{alerts.errors.map((item, index) => <div key={`${item.url ?? 'error'}-${index}`}><SourceLink url={item.url} label="Failed item" /><span>{typeof item.error === 'string' ? item.error : 'Retrieval error; details not reported'}</span></div>)}</div>}
        <div className="disclaimer"><strong>Public-health context, not automatic property attribution.</strong> Notify NYC exposes recent notifications, not a complete historical archive. Retention uses stable item identity. An affected ZIP code does not identify a positive building or tower; property attribution requires explicit official building evidence and a separately verified identity match. These source-coverage figures do not change Priority Score.</div>
      </>}
    </div>
  </>
}