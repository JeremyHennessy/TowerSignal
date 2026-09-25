import { useEffect, useMemo, useState } from 'react'
import type { SystemsPayload } from '../types/data'
import { formatTimestamp } from '../domain/labels'
import { SourceHealthLinks, SourceHealthSource, type SourceHealthLink } from './SourceHealthLinks'
import { countOrNull, enforcementCoverage, legionellaChannelRows, parseLegionellaHealth, timestampOrNull, type LegionellaHealthPayload } from '../domain/sourceHealthExpansion'

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
    scope: 'HPD violations, DOB SWO complaint/disposition evidence, the official DOB issued/rescinded SWO dated snapshot, FISP / Local Law 11 filings and official published Labor Law decisions.',
    note: 'Exact BBL/BIN or explicit-worksite attachment only. Complaint dispositions and the dated DOB snapshot do not establish current SWO status. Official Reports covers all appellate decisions but only selected trial-court decisions, so published Labor Law decisions are not a comprehensive filing feed.',
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

// Publisher references mirror the existing collectors; they never imply retrieval success.
function refreshLinks(payload: SystemsPayload, index: number): SourceHealthLink[] {
  const groups = [
    /y4fw-iqfr|f9wb-g8mb|64uk-42ks|w9ak-ipjd|tesw-yqqr|feu5-w2e2|x748-37q7|5zhs-2jue/i,
    /wvxf-dwi5|eabe-havv|xubg-57si|NYCDOB_SWOS|LABOR_LAW/,
    /legionella|legionnaires/i,
    /water|CMS|medicare|service.?line|City Record|NYS.*registry/i,
    /ACRIS/i,
    /checkbook/i,
    /OATH/i,
    /311.*histor|histor.*311|76ig-c548/i,
  ]
  const labels: Record<string, string> = {
    'y4fw-iqfr': 'Tower registry', 'f9wb-g8mb': 'Inspections', '64uk-42ks': 'PLUTO',
    'w9ak-ipjd': 'DOB NOW', 'tesw-yqqr': 'HPD registrations', 'feu5-w2e2': 'HPD contacts',
    'x748-37q7': 'Tower geometry', '5zhs-2jue': 'Building footprints',
    'wvxf-dwi5': 'HPD violations', 'eabe-havv': 'DOB complaints', 'xubg-57si': 'FISP filings',
    'NYCDOB_SWOS_ISSUED_RESCINDED_SNAPSHOT_20240205': 'Dated SWO snapshot',
    'NYS_OFFICIAL_REPORTS_LABOR_LAW_PUBLISHED_DECISIONS': 'Published decisions',
    'bnx9-e6tj': 'ACRIS master', '8h5j-fqxa': 'ACRIS legals', '636b-3b5g': 'ACRIS parties',
    'jz4z-kudi': 'OATH cases', 'rytv-g5ui': 'Tank compliance', 'gjm4-k24g': 'Tank inspections',
    'Water_Tank_2022/FeatureServer/27': 'Tank geometry',
  }
  const links: SourceHealthLink[] = payload.metadata.sources
    .filter(source => groups[index].test(`${source.name} ${source.dataset_id}`))
    .map(source => ({ url: source.url, label: labels[source.dataset_id] || source.name }))
  const fixed: Record<number, SourceHealthLink[]> = {
    2: [
      { label: 'NYC Health', url: 'https://www.nyc.gov/site/doh/health/health-topics/legionnaires-disease.page' },
      { label: 'NYS Health', url: 'https://www.health.ny.gov/diseases/communicable/legionellosis/' },
    ],
    3: [{ label: 'NYS public water', url: 'https://www.health.ny.gov/environmental/water/drinking/pws_contacts/map_pws_contacts.htm' }],
    4: [
      { label: 'ACRIS master', url: 'https://data.cityofnewyork.us/City-Government/ACRIS-Real-Property-Master/bnx9-e6tj' },
      { label: 'ACRIS legals', url: 'https://data.cityofnewyork.us/City-Government/ACRIS-Real-Property-Legals/8h5j-fqxa' },
      { label: 'ACRIS parties', url: 'https://data.cityofnewyork.us/City-Government/ACRIS-Real-Property-Parties/636b-3b5g' },
    ],
    5: [{ label: 'Checkbook NYC', url: 'https://www.checkbooknyc.com/' }],
    7: [
      { label: '311 · 2010–2019', url: 'https://data.cityofnewyork.us/d/76ig-c548' },
      { label: '311 · 2020 onward', url: 'https://data.cityofnewyork.us/d/erm2-nwe9' },
    ],
  }
  return [...links, ...(fixed[index] ?? [])]
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
    <div className="reference-table-card" data-testid="property-enforcement-source-health" id="source-health-enforcement" tabIndex={-1}>
      <div className="reference-table-heading"><div><strong>Property enforcement coverage</strong><span>HPD violations, DOB SWO complaint/disposition evidence, the official DOB dated SWO snapshot and Local Law 11 / FISP. Counts follow the currently loaded NYC accounts.</span></div></div>
      <details className="source-health-explainer"><summary>How to read enforcement coverage</summary><div className="disclaimer">Dataset rows are the publisher's full dataset count. Retained records are the normalized, exact-key cohort records, not a claimed raw retrieval count. Matched properties are distinct BBLs or BINs; represented systems can share a property. Coverage is observed prevalence across {number.format(payload.systems.length)} systems, not completeness of citywide enforcement. Available means published provenance and account measurements are present; WARNING preserves an explicit source limitation such as a historical observation window. Neither state substitutes for pagination or schema diagnostics.</div></details>
      <div className="reference-table-scroll" tabIndex={0} role="region" aria-label="Property enforcement source health"><table className="reference-table source-health-table source-linked-table"><thead><tr><th>Source &amp; links</th><th>Availability</th><th>Dataset rows</th><th>Retained records</th><th>Requested properties</th><th>Matched properties</th><th>Represented systems</th><th>System coverage</th><th>Freshness &amp; evidence scope</th></tr></thead><tbody>
        {properties.map(source => {
          const status = !source.available ? 'UNVERIFIED' : source.source?.source_health_status === 'FAILED' ? 'FAILED' : source.source?.source_health_status === 'WARNING' ? 'WARNING' : 'AVAILABLE'
          return <tr key={source.id}>
            <td><SourceHealthSource name={source.name} detail={`${source.id} · exact ${source.unit}`} links={[{ url: source.source?.url }]} /></td>
            <td><span className={`health-badge${status === 'AVAILABLE' ? '' : ' health-warning'}`}>{status}</span></td>
            <td>{count(source.sourceRecords)}</td><td>{count(source.records)}</td>
            <td>{count(source.requested)} {source.unit}<small>Current account identity universe</small></td>
            <td>{count(source.matched)} {source.unit}</td><td>{count(source.attached)} / {number.format(source.totalSystems)}</td>
            <td>{source.coverage === null ? 'Not reported' : `${source.coverage.toFixed(1)}%`}</td>
            <td><span>Last retrieved: {date(source.retrievedAt)}</span><small>Publisher updated: {date(source.source?.source_last_updated_at)}</small>{(source.source?.source_observation_start_at || source.source?.source_observation_end_at) && <small>Observation window: {date(source.source?.source_observation_start_at)} – {date(source.source?.source_observation_end_at)}</small>}{source.source?.current_status_available === false && <small>Current status: not available from this source.</small>}<small>{source.source?.source_query_scope}</small><small>{source.note}</small>{(source.source?.source_health_reasons ?? []).map(reason => <small key={reason}>{reason}</small>)}<small>Raw retrieved count, pagination and schema diagnostics: not reported in account metadata.</small></td>
          </tr>
        })}
      </tbody></table></div>
      <details className="source-health-explainer"><summary>Evidence limits and what a missing match means</summary><div className="disclaimer"><strong>Evidence gaps remain explicit.</strong> HPD registration/contact coverage is a different source from HPD violations. DOB complaint dispositions are event evidence, not an active-order ledger. The official DOB issued/rescinded snapshot is a dated 2022–2024 observation and does not establish current 2026 SWO status. FISP is Local Law 11, not generic Labor Law. Official Reports published decisions are complete for appellate decisions but only selected trial-court decisions, so they are not a comprehensive Supreme Court/NYSCEF filing feed. A missing match is not proof of no violation, no filing or no enforcement.</div></details>
    </div>

    <div className="reference-table-card" data-testid="source-refresh-coverage" id="source-health-refresh" tabIndex={-1}>
      <div className="reference-table-heading"><div><strong>Production refresh coverage</strong><span>One canonical daily NYC release, with durable high-cost caches refreshed ahead of it and OATH refreshed more frequently.</span></div></div>
      <div className="disclaimer"><strong>Refresh time is not source observation time.</strong> A daily rebuild means TowerSignal checks the publisher or verified cache again; it does not make a historical source snapshot current. The 10:17 UTC production release is the deployment gate: source collection, validation, application build, hosted desktop/iPhone verification and history persistence must all succeed.</div>
      <div className="reference-table-scroll" tabIndex={0} role="region" aria-label="Production refresh coverage"><table className="reference-table source-linked-table"><thead><tr><th>Source family &amp; links</th><th>Refresh cadence</th><th>Production path</th><th>Coverage</th><th>Operational boundary</th></tr></thead><tbody>
        {refreshContracts.map((contract, index) => <tr key={contract.source}>
          <td><SourceHealthSource name={contract.source} links={refreshLinks(payload, index)} /></td>
          <td><span className="health-badge">{contract.cadence}</span></td>
          <td>{contract.path}</td>
          <td>{contract.scope}</td>
          <td>{contract.note}</td>
        </tr>)}
      </tbody></table></div>
    </div>

    <div className="reference-table-card" data-testid="legionella-source-health" id="source-health-monitoring" tabIndex={-1}>
      <div className="reference-table-heading"><div><strong>Legionnaires monitoring coverage</strong><span>Official NYC and NYS channels, retrieval evidence and retained history. Separate from account-identity coverage.</span></div></div>
      {error ? <div className="reference-empty-state"><strong>Legionnaires source health unavailable.</strong><span>{error}</span><span>No healthy status, zero-alert count or property attribution is inferred.</span></div> : !alerts ? <div className="reference-empty-state"><strong>Loading Legionnaires source health…</strong></div> : <>
        <div className="reference-metric-grid">
          <article><span className="reference-metric-icon">SRC</span><div><small>Channel snapshots retrieved</small><strong>{channels.filter(row => row.retrieved).length}/{channels.length}</strong><span>Snapshot evidence, not archive completeness</span></div></article>
          <article><span className="reference-metric-icon">DOC</span><div><small>Retained relevant items</small><strong>{number.format(alerts.items.length)}</strong><span>Not a count of active outbreaks</span></div></article>
          <article><span className="reference-metric-icon warning">ERR</span><div><small>Item retrieval errors</small><strong>{number.format(alerts.errors.length)}</strong><span>Failed child documents remain visible</span></div></article>
          <article><span className="reference-metric-icon">H</span><div><small>Prior items retained</small><strong>{count(countOrNull(alerts.history_merge?.retained_prior_item_count))}</strong><span>Old observations are not newly verified</span></div></article>
        </div>
        <div className="disclaimer">Cache assembled {date(alerts.generated_at)}. Source freshness is each snapshot's retrieval date below, not the rebuild date. {count(countOrNull(alerts.history_merge?.current_collection_item_count))} items were collected in that run. A successful channel snapshot does not prove that every historical alert or linked document was retrieved.</div>
        <div className="reference-table-scroll" tabIndex={0} role="region" aria-label="Legionnaires monitoring channels"><table className="reference-table source-linked-table"><thead><tr><th>Source &amp; links</th><th>Agency</th><th>Retrieval evidence</th><th>Last successful retrieval</th><th>Channel scope</th></tr></thead><tbody>
          {channels.map(channel => <tr key={channel.key}>
            <td><SourceHealthSource name={channel.name} links={[{ url: channel.snapshot?.url }]} /></td><td>{channel.snapshot?.agency || 'Not reported'}</td>
            <td><span className={`health-badge${channel.retrieved ? '' : ' health-warning'}`}>{channel.retrieved ? 'SNAPSHOT RETRIEVED' : 'UNVERIFIED'}</span></td>
            <td>{date(channel.retrievedAt)}</td><td>{channel.snapshot?.channel_kind?.replaceAll('_', ' ') || 'Not reported'}</td>
          </tr>)}
        </tbody></table></div>
        {alerts.errors.length > 0 && <div className="reference-empty-state"><strong>Incomplete item retrieval</strong>{alerts.errors.map((item, index) => <div key={`${item.url ?? 'error'}-${index}`}><SourceHealthLinks links={[{ url: item.url, label: 'Failed item' }]} /><span>{typeof item.error === 'string' ? item.error : 'Retrieval error; details not reported'}</span></div>)}</div>}
        <div className="disclaimer"><strong>Public-health context, not automatic property attribution.</strong> Notify NYC exposes recent notifications, not a complete historical archive. Retention uses stable item identity. An affected ZIP code does not identify a positive building or tower; property attribution requires explicit official building evidence and a separately verified identity match. These source-coverage figures do not change Priority Score.</div>
      </>}
    </div>
  </>
}
