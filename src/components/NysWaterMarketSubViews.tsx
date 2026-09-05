import { useEffect, useMemo, useState } from 'react'
import { loadNysLsliDetails, loadNysPublicWater, loadNysServiceLineSummary } from '../data/api'
import type { LsliDetailRecord, NysLsliDetailPayload, NysPublicWaterPayload, NysServiceLineInventorySummaryPayload } from '../types/water'
import { formatTimestamp } from '../domain/labels'

export type NysWaterSubview = 'pws' | 'lsli' | 'service-lines'

const number = new Intl.NumberFormat('en-US')

function count(value: unknown): string {
  return typeof value === 'number' ? number.format(value) : '—'
}

function countyFor(row: { lead_service_line_inventory_principal_county?: string | null }): string {
  return row.lead_service_line_inventory_principal_county ?? '—'
}

function contactName(row: LsliDetailRecord): string {
  return row.owner_or_operator_form_contact?.name ?? 'No source contact name'
}

function methodSummary(row: LsliDetailRecord): string {
  const methods = (row.identification_methods ?? [])
    .filter(method => Number(method.pws_side_count ?? 0) > 0 || Number(method.customer_side_count ?? 0) > 0)
    .map(method => String(method.method ?? 'method'))
  return methods.slice(0, 3).join(' · ') || 'No counted method rows'
}

function sortedCounts(counts: Record<string, number> | undefined): Array<[string, number]> {
  return Object.entries(counts ?? {}).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
}

function OptionalError({ message }: { message: string | null }) {
  return message ? <div className="reference-empty-state compact"><strong>Optional source warning.</strong><span>{message}</span></div> : null
}

function PwsSubview({ payload, error, loading }: { payload: NysPublicWaterPayload | null; error: string | null; loading: boolean }) {
  const [search, setSearch] = useState('')
  const rows = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (payload?.pws_systems ?? []).filter(row => {
      const haystack = [row.pws_id, row.pws_name, row.system_type, row.lead_service_line_inventory_principal_county]
        .filter(Boolean).join(' ').toLowerCase()
      return !query || haystack.includes(query)
    }).slice(0, 120)
  }, [payload, search])

  if (loading) return <div className="reference-empty-state"><strong>Loading NYS public-water systems…</strong></div>
  if (!payload) return <><OptionalError message={error} /><div className="reference-empty-state"><strong>NYS public-water cache is not available.</strong><span>The statewide cooling-tower registry remains available; no PWS relationships are inferred from missing cache data.</span></div></>

  return <>
    <OptionalError message={error} />
    <section className="nys-water-kpis">
      <article><span>PWS profiles</span><strong>{count(payload.summary.pws_system_count)}</strong><small>Built from NYSDOH contact pages</small></article>
      <article><span>Certified operators</span><strong>{count(payload.summary.certified_operator_count)}</strong><small>Qualified only, unlinked to PWS</small></article>
      <article><span>LSLI required</span><strong>{count(payload.summary.lsli_required_system_count)}</strong><small>Index-linked by PWSID</small></article>
      <article><span>2025 violations</span><strong>{count(payload.summary.violation_count_2025)}</strong><small>Authority PWSID observations</small></article>
      <article><span>Systems with violations</span><strong>{count(payload.summary.systems_with_violations_2025)}</strong><small>Matched by PWSID only</small></article>
    </section>
    <div className="disclaimer"><strong>PWS identity boundary.</strong> Public-water contacts are CONTACT_FOR_PWS evidence only. Certified operators are qualified-person evidence only and are not assigned to a PWS unless the source says so.</div>
    <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>NYS public-water system subview</strong><span>{number.format(rows.length)} shown · generated {formatTimestamp(payload.generated_at)}</span></div><div className="page-actions"><input aria-label="Search PWS systems" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search PWS, name, county…" /></div></div>
      <div className="reference-table-scroll"><table className="reference-table pws-table"><thead><tr><th>PWS</th><th>Type</th><th>Population</th><th>Contacts</th><th>LSLI</th><th>2025 violations</th><th>Evidence</th></tr></thead><tbody>{rows.map(row => <tr key={row.pws_id}>
        <td><strong>{row.pws_name ?? 'Unnamed public-water system'}</strong><small>{row.pws_id}</small></td>
        <td>{row.system_type ?? '—'}</td>
        <td>{row.total_population == null ? '—' : number.format(row.total_population)}</td>
        <td>{number.format(row.contact_count)}<small>directory contacts</small></td>
        <td>{row.lead_service_line_inventory_required ? <span className="ready-label">Required</span> : <span className="muted-label">Not indexed</span>}<small>{countyFor(row)}</small></td>
        <td>{number.format(row.violation_count_2025 ?? 0)}<small>{Object.keys(row.violation_status_counts_2025 ?? {}).join(' · ') || 'none in cache'}</small></td>
        <td>{row.lead_service_line_inventory_detail_url ? <a className="table-link" href={row.lead_service_line_inventory_detail_url} target="_blank" rel="noreferrer">Open LSLI detail ↗</a> : '—'}</td>
      </tr>)}</tbody></table></div>
    </div>
  </>
}

function LsliSubview({ payload, error, loading }: { payload: NysLsliDetailPayload | null; error: string | null; loading: boolean }) {
  const [search, setSearch] = useState('')
  const rows = useMemo(() => {
    const query = search.trim().toLowerCase()
    return [...(payload?.details ?? [])]
      .filter(row => !query || `${row.pws_id} ${row.pws_name ?? ''}`.toLowerCase().includes(query))
      .sort((a, b) => (b.inventory?.lead_service_lines ?? 0) - (a.inventory?.lead_service_lines ?? 0) || (b.inventory?.unknown_service_lines ?? 0) - (a.inventory?.unknown_service_lines ?? 0))
      .slice(0, 120)
  }, [payload, search])

  if (loading) return <div className="reference-empty-state"><strong>Loading NYS LSLI detail cache…</strong></div>
  if (!payload) return <><OptionalError message={error} /><div className="reference-empty-state"><strong>NYS LSLI detail cache is not available.</strong><span>The app does not infer line inventories from the PWS index when detail pages are unavailable.</span></div></>

  return <>
    <OptionalError message={error} />
    <section className="nys-water-kpis">
      <article><span>Index coverage</span><strong>{count(payload.summary.index_count)}</strong><small>Current PWS IDs accounted for</small></article>
      <article><span>Parsed details</span><strong>{count(payload.summary.parsed_detail_count)}</strong><small>Full detail pages parsed</small></article>
      <article><span>Unavailable details</span><strong>{count(payload.summary.unavailable_detail_count)}</strong><small>Explicit current-index 404s only</small></article>
      <article><span>Systems with lead</span><strong>{count(payload.summary.systems_with_lead_lines)}</strong><small>Source-reported detail totals</small></article>
      <article><span>Total service lines</span><strong>{count(payload.summary.source_reported_total_service_lines_sum)}</strong><small>Parsed details only</small></article>
    </section>
    <div className="disclaimer"><strong>LSLI detail boundary.</strong> Section II contacts keep NYSDOH's combined owner/licensed-operator form role. TowerSignal does not split owner versus operator or infer values for current-index 404 details.</div>
    <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>NYS LSLI detail explorer</strong><span>{number.format(rows.length)} shown · generated {formatTimestamp(payload.generated_at)}</span></div><div className="page-actions"><input aria-label="Search LSLI details" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search PWS or name…" /></div></div>
      <div className="reference-table-scroll"><table className="reference-table lsli-detail-table"><thead><tr><th>PWS</th><th>Total lines</th><th>Lead</th><th>GSLRR</th><th>Unknown</th><th>Form contact</th><th>Methods</th><th>Source</th></tr></thead><tbody>{rows.map(row => <tr key={row.pws_id}>
        <td><strong>{row.pws_name ?? 'Unnamed public-water system'}</strong><small>{row.pws_id}</small></td>
        <td>{row.inventory?.total_service_lines == null ? '—' : number.format(row.inventory.total_service_lines)}</td>
        <td>{row.inventory?.lead_service_lines == null ? '—' : number.format(row.inventory.lead_service_lines)}</td>
        <td>{row.inventory?.gslrr_service_lines == null ? '—' : number.format(row.inventory.gslrr_service_lines)}</td>
        <td>{row.inventory?.unknown_service_lines == null ? '—' : number.format(row.inventory.unknown_service_lines)}</td>
        <td>{contactName(row)}<small>{row.owner_or_operator_form_contact?.relationship_role ?? 'role not present'}</small></td>
        <td>{methodSummary(row)}</td>
        <td><a className="table-link" href={row.source_url} target="_blank" rel="noreferrer">Open source ↗</a><small>{row.detail_status ?? 'PARSED'}</small></td>
      </tr>)}</tbody></table></div>
    </div>
  </>
}

function ServiceLineSubview({ payload, error, loading }: { payload: NysServiceLineInventorySummaryPayload | null; error: string | null; loading: boolean }) {
  const [partition, setPartition] = useState('category')
  const [search, setSearch] = useState('')
  const partitions = useMemo(() => payload ? [
    { key: 'category', label: 'Line category', counts: payload.summary.normalized_category_counts },
    { key: 'public-material', label: 'Public material', counts: payload.summary.normalized_public_material_counts },
    { key: 'customer-material', label: 'Customer material', counts: payload.summary.normalized_customer_material_counts },
    { key: 'public-method', label: 'Public method', counts: payload.summary.normalized_public_method_counts },
    { key: 'customer-method', label: 'Customer method', counts: payload.summary.normalized_customer_method_counts },
    { key: 'nyc-borough', label: 'NYC locality code', counts: payload.summary.nyc_borough_row_counts },
    { key: 'building-type', label: 'Building type', counts: payload.summary.building_type_counts },
    { key: 'raw-locality', label: 'Raw locality', counts: payload.summary.raw_locality_counts },
  ] : [], [payload])
  const rows = useMemo(() => {
    const query = search.trim().toLowerCase()
    const active = partitions.find(row => row.key === partition) ?? partitions[0]
    return sortedCounts(active?.counts)
      .filter(([label]) => !query || label.toLowerCase().includes(query))
      .slice(0, 150)
      .map(([label, value]) => ({ partition: active?.label ?? 'Partition', label, value }))
  }, [partition, partitions, search])

  if (loading) return <div className="reference-empty-state"><strong>Loading statewide address-level service-line summary…</strong></div>
  if (!payload) return <><OptionalError message={error} /><div className="reference-empty-state"><strong>NYS address-level service-line cache is not available.</strong><span>The browser loads only the summary/explorer metadata, not the multi-million-row compressed cache.</span></div></>

  return <>
    <OptionalError message={error} />
    <section className="nys-water-kpis">
      <article><span>Address-level rows</span><strong>{number.format(payload.summary.row_count)}</strong><small>Full compressed cache retained</small></article>
      <article><span>NYC-coded rows</span><strong>{number.format(Object.values(payload.summary.nyc_borough_row_counts).reduce((sum, value) => sum + value, 0))}</strong><small>MN/BX/BK/QN/SI locality codes</small></article>
      <article><span>Geocoded rows</span><strong>{number.format(payload.summary.rows_with_valid_nys_location)}</strong><small>Normalized NY coordinate bounds</small></article>
      <article><span>Missing address key</span><strong>{count(payload.summary.missing_service_address_id_count)}</strong><small>No locality + street + ZIP key</small></article>
      <article><span>Rows with notes</span><strong>{number.format(payload.summary.rows_with_note)}</strong><small>Raw source notes preserved</small></article>
    </section>
    <div className="disclaimer"><strong>Address-level boundary.</strong> The statewide line dataset does not publish PWSID. This explorer partitions the coherent cache; it does not assign rows to PWS, cooling towers, properties or NYC accounts.</div>
    <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>Partitioned service-line explorer</strong><span>Compressed data file {payload.data_file} · generated {formatTimestamp(payload.generated_at)}</span></div><div className="page-actions"><select aria-label="Service-line partition" value={partition} onChange={event => setPartition(event.target.value)}>{partitions.map(row => <option key={row.key} value={row.key}>{row.label}</option>)}</select><input aria-label="Search service-line partition" value={search} onChange={event => setSearch(event.target.value)} placeholder="Filter partition values…" /></div></div>
      <div className="reference-table-scroll"><table className="reference-table service-line-partition-table"><thead><tr><th>Partition</th><th>Value</th><th>Rows</th><th>Share</th></tr></thead><tbody>{rows.map(row => <tr key={`${row.partition}-${row.label}`}>
        <td>{row.partition}</td>
        <td><strong>{row.label}</strong></td>
        <td>{number.format(row.value)}</td>
        <td>{payload.summary.row_count > 0 ? `${((row.value / payload.summary.row_count) * 100).toFixed(2)}%` : '—'}</td>
      </tr>)}</tbody></table></div>
    </div>
  </>
}

export function NysWaterMarketSubViews({ view }: { view: NysWaterSubview }) {
  const [pws, setPws] = useState<NysPublicWaterPayload | null>(null)
  const [lsli, setLsli] = useState<NysLsliDetailPayload | null>(null)
  const [serviceLines, setServiceLines] = useState<NysServiceLineInventorySummaryPayload | null>(null)
  const [pwsError, setPwsError] = useState<string | null>(null)
  const [lsliError, setLsliError] = useState<string | null>(null)
  const [serviceLineError, setServiceLineError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    Promise.allSettled([loadNysPublicWater(), loadNysLsliDetails(), loadNysServiceLineSummary()])
      .then(([pwsResult, lsliResult, serviceLineResult]) => {
        if (cancelled) return
        if (pwsResult.status === 'fulfilled') setPws(pwsResult.value)
        else setPwsError(pwsResult.reason instanceof Error ? pwsResult.reason.message : 'NYS public-water cache is unavailable')
        if (lsliResult.status === 'fulfilled') setLsli(lsliResult.value)
        else setLsliError(lsliResult.reason instanceof Error ? lsliResult.reason.message : 'NYS LSLI detail cache is unavailable')
        if (serviceLineResult.status === 'fulfilled') setServiceLines(serviceLineResult.value)
        else setServiceLineError(serviceLineResult.reason instanceof Error ? serviceLineResult.reason.message : 'NYS service-line cache is unavailable')
        setLoading(false)
      })
    return () => { cancelled = true }
  }, [])

  if (view === 'pws') return <PwsSubview payload={pws} error={pwsError} loading={loading} />
  if (view === 'lsli') return <LsliSubview payload={lsli} error={lsliError} loading={loading} />
  return <ServiceLineSubview payload={serviceLines} error={serviceLineError} loading={loading} />
}
