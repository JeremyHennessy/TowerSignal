import { useEffect, useMemo, useState } from 'react'

type EwrbCount = { property_type?: string; fsa?: string; rows: number }
type EwrbAnnual = {
  year: number
  reporting_rows: number
  unique_ewrb_ids: number
  data_quality_check_yes_rows: number
  data_quality_check_yes_percent: number | null
  energy_star_numeric_score_rows: number
  published_energy_star_certification_value_rows: number
  top_property_types: EwrbCount[]
  top_postal_fsa: EwrbCount[]
}
type EwrbMarketPayload = {
  schema_version: string
  scope: 'TORONTO_AGGREGATE_ONLY'
  title: string
  catalogue_url: string | null
  license: string | null
  retrieved_at: string | null
  reporting_years: number[]
  latest_reporting_year: number | null
  toronto_reporting_rows: number
  annual: EwrbAnnual[]
  overall_top_property_types: EwrbCount[]
  overall_top_postal_fsa: EwrbCount[]
  identity_contract: {
    property_level_links: number
    reason: string
    allowed_use: string
    tower_evidence_effect: 'NONE'
    relationship_effect: 'NONE'
  }
  absence: string
}

async function loadEwrbMarket(): Promise<EwrbMarketPayload> {
  const response = await fetch(`${import.meta.env.BASE_URL}data/toronto-ewrb-market.json`, { cache: 'no-store' })
  if (!response.ok) throw new Error(`Toronto EWRB market request failed: HTTP ${response.status}`)
  const payload = await response.json() as EwrbMarketPayload
  if (payload.scope !== 'TORONTO_AGGREGATE_ONLY' || payload.identity_contract?.property_level_links !== 0 || !Array.isArray(payload.annual)) {
    throw new Error('Toronto EWRB market dataset is malformed')
  }
  return payload
}

function pct(value: number, total: number): string {
  return total > 0 ? `${(value / total * 100).toFixed(1)}%` : '—'
}

export function TorontoBenchmarkingPage() {
  const [payload, setPayload] = useState<EwrbMarketPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [selectedYear, setSelectedYear] = useState<number | 'all'>('all')

  useEffect(() => {
    loadEwrbMarket().then(setPayload).catch(reason => setError(reason instanceof Error ? reason.message : 'Unable to load Toronto EWRB market context'))
  }, [])

  const latest = useMemo(() => payload?.annual.find(item => item.year === payload.latest_reporting_year) ?? null, [payload])
  const selected = useMemo(() => selectedYear === 'all' ? null : payload?.annual.find(item => item.year === selectedYear) ?? null, [payload, selectedYear])
  const typeRows = selected?.top_property_types ?? payload?.overall_top_property_types ?? []
  const fsaRows = selected?.top_postal_fsa ?? payload?.overall_top_postal_fsa ?? []
  const contextTotal = selected?.reporting_rows ?? payload?.toronto_reporting_rows ?? 0

  if (error) return <section className="product-page toronto-page toronto-parity-page"><div className="reference-empty-state"><strong>Toronto benchmarking unavailable.</strong><span>{error}</span></div></section>
  if (!payload || !latest) return <section className="product-page toronto-page toronto-parity-page"><div className="portal-loading">Loading Toronto aggregate benchmarking…</div></section>

  return <section className="product-page toronto-page toronto-parity-page toronto-benchmarking-page">
    <div className="product-page-heading"><div><span className="page-kicker">Toronto · aggregate market context</span><h1>Energy & water benchmarking</h1><p>Ontario EWRB reporting provides Toronto-wide building-performance context from published 2018–2024 data. The public Ontario disclosure does not contain civic street addresses, so TowerSignal does not link these rows to individual properties.</p></div></div>

    <div className="reference-metric-grid toronto-parity-metrics">
      <article><span className="reference-metric-icon success">▦</span><div><small>Published Toronto rows</small><strong>{payload.toronto_reporting_rows.toLocaleString()}</strong><span>2018–2024 aggregate context</span></div></article>
      <article><span className="reference-metric-icon">◷</span><div><small>Latest reporting year</small><strong>{latest.year}</strong><span>{latest.reporting_rows.toLocaleString()} Toronto rows</span></div></article>
      <article><span className="reference-metric-icon success">✓</span><div><small>Latest data-quality check</small><strong>{latest.data_quality_check_yes_percent?.toFixed(1) ?? '—'}%</strong><span>{latest.data_quality_check_yes_rows.toLocaleString()} published yes rows</span></div></article>
      <article><span className="reference-metric-icon">★</span><div><small>Latest numeric Energy Star scores</small><strong>{latest.energy_star_numeric_score_rows.toLocaleString()}</strong><span>{pct(latest.energy_star_numeric_score_rows, latest.reporting_rows)} of latest rows</span></div></article>
      <article><span className="reference-metric-icon warning">⌁</span><div><small>Property-level EWRB links</small><strong>0</strong><span>Intentionally aggregate-only</span></div></article>
    </div>

    <div className="toronto-benchmarking-boundary"><strong>Identity boundary</strong><span>{payload.identity_contract.reason}</span><small>{payload.identity_contract.allowed_use}</small></div>

    <div className="toronto-benchmarking-grid">
      <section className="toronto-benchmarking-card toronto-benchmarking-trend"><div className="toronto-benchmarking-card-heading"><div><small>Reporting history</small><h2>Toronto EWRB rows by year</h2></div><a href={payload.catalogue_url ?? '#'} target="_blank" rel="noreferrer">Open Ontario dataset ↗</a></div>
        <div className="toronto-benchmark-bars">{payload.annual.map(item => {
          const max = Math.max(...payload.annual.map(row => row.reporting_rows))
          return <button key={item.year} className={selectedYear === item.year ? 'selected' : ''} onClick={() => setSelectedYear(current => current === item.year ? 'all' : item.year)} title={`${item.year}: ${item.reporting_rows.toLocaleString()} published Toronto rows`}><span className="toronto-benchmark-bar-track"><span style={{ height: `${Math.max(8, item.reporting_rows / max * 100)}%` }} /></span><strong>{item.reporting_rows.toLocaleString()}</strong><small>{item.year}</small></button>
        })}</div>
        <div className="toronto-table-wrap"><table className="toronto-table"><thead><tr><th>Year</th><th>Rows</th><th>Unique EWRB IDs</th><th>Quality check = Yes</th><th>Numeric Energy Star score</th><th>Published certification value</th></tr></thead><tbody>{payload.annual.map(item => <tr key={item.year}><td><button className="toronto-address-button" onClick={() => setSelectedYear(current => current === item.year ? 'all' : item.year)}>{item.year}</button></td><td>{item.reporting_rows.toLocaleString()}</td><td>{item.unique_ewrb_ids.toLocaleString()}</td><td>{item.data_quality_check_yes_percent?.toFixed(1) ?? '—'}%</td><td>{item.energy_star_numeric_score_rows.toLocaleString()}</td><td>{item.published_energy_star_certification_value_rows.toLocaleString()}</td></tr>)}</tbody></table></div>
      </section>

      <section className="toronto-benchmarking-card"><div className="toronto-benchmarking-card-heading"><div><small>{selected ? `${selected.year} selected` : 'All published years'}</small><h2>Property-type mix</h2></div>{selected && <button onClick={() => setSelectedYear('all')}>Clear year</button>}</div><div className="toronto-benchmark-list">{typeRows.slice(0, 12).map(item => <div key={item.property_type}><span>{item.property_type}</span><strong>{item.rows.toLocaleString()}</strong><small>{pct(item.rows, contextTotal)}</small></div>)}</div></section>

      <section className="toronto-benchmarking-card"><div className="toronto-benchmarking-card-heading"><div><small>{selected ? `${selected.year} selected` : 'All published years'}</small><h2>Postal-FSA mix</h2></div></div><div className="toronto-benchmark-list">{fsaRows.slice(0, 12).map(item => <div key={item.fsa}><span>{item.fsa}</span><strong>{item.rows.toLocaleString()}</strong><small>{pct(item.rows, contextTotal)}</small></div>)}</div></section>
    </div>

    <section className="toronto-parity-limitations"><h2>How to use this source</h2><ul><li>Use the EWRB view for Toronto-wide benchmarking and market context, not for property identification.</li><li>Ontario’s public file exposes EWRB ID, city/postal FSA, building type and performance fields but no civic street address.</li><li>Absence from the public EWRB rows is not evidence that a property lacks cooling equipment, energy use, or reporting obligations.</li><li>{payload.license ?? 'Source licence information unavailable.'}</li></ul></section>
  </section>
}
