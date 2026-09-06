import { useEffect, useMemo, useState } from 'react'
import { loadNycDistributionWater } from '../data/api'
import type { NycDistributionWaterPayload } from '../types/water'
import { formatDate, formatTimestamp } from '../domain/labels'
import { ShareButton } from './ShareButton'

const number = new Intl.NumberFormat('en-US')

type Measurement = { raw: string | null; numeric: number | null; qualifier: string }

function measurementText(measurements: Record<string, Measurement> | null | undefined, key: string): string {
  const measurement = measurements?.[key]
  if (!measurement || measurement.raw == null) return '—'
  return measurement.qualifier && measurement.qualifier !== 'EQ' ? `${measurement.qualifier} ${measurement.raw}` : measurement.raw
}

function sampleText(row: Record<string, unknown>, key: string): string | null {
  const value = row[key]
  return typeof value === 'string' && value.trim() ? value : null
}

function sampleMeasurements(row: Record<string, unknown>): Record<string, Measurement> | null {
  const value = row.measurements
  return value && typeof value === 'object' ? value as Record<string, Measurement> : null
}

export function WaterQualityPage() {
  const [payload, setPayload] = useState<NycDistributionWaterPayload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [sampleClass, setSampleClass] = useState('ALL')
  const [view, setView] = useState<'sites' | 'samples'>('sites')

  useEffect(() => {
    let cancelled = false
    loadNycDistributionWater()
      .then(value => { if (!cancelled) setPayload(value) })
      .catch(err => { if (!cancelled) setError(err instanceof Error ? err.message : 'NYC distribution water-quality cache is unavailable') })
    return () => { cancelled = true }
  }, [])

  const classes = useMemo(() => Object.keys(payload?.summary.sample_class_counts ?? {}).sort(), [payload])
  const sites = useMemo(() => {
    const query = search.trim().toLowerCase()
    return [...(payload?.sites ?? [])]
      .filter(row => (!query || String(row.sample_site ?? '').toLowerCase().includes(query)) && (sampleClass === 'ALL' || Boolean(row.sample_class_counts[sampleClass])))
      .sort((a, b) => b.sample_count - a.sample_count || String(a.sample_site ?? '').localeCompare(String(b.sample_site ?? '')))
      .slice(0, 150)
  }, [payload, sampleClass, search])
  const samples = useMemo(() => {
    const query = search.trim().toLowerCase()
    return [...(payload?.samples ?? [])]
      .filter(row => {
        const site = sampleText(row, 'sample_site') ?? ''
        const klass = sampleText(row, 'sample_class') ?? ''
        return (!query || site.toLowerCase().includes(query) || (sampleText(row, 'sample_number') ?? '').toLowerCase().includes(query)) && (sampleClass === 'ALL' || klass === sampleClass)
      })
      .sort((a, b) => String(sampleText(b, 'sample_date') ?? '').localeCompare(String(sampleText(a, 'sample_date') ?? '')))
      .slice(0, 150)
  }, [payload, sampleClass, search])

  return <section className="product-page water-quality-page">
    <div className="product-page-heading">
      <div><span className="page-kicker">New York City · distribution water quality</span><h1>Water Quality</h1><p>Explore NYC DEP distribution drinking-water samples by sample site and class. Sample-site evidence remains unlinked to TowerSignal buildings, PWS records and cooling-tower accounts unless a future source supplies a defensible property relationship.</p></div>
      <div className="page-actions"><ShareButton label="Share this view" /></div>
    </div>

    {error && <div className="reference-empty-state"><strong>Distribution water-quality cache unavailable.</strong><span>{error}</span><span>No account or property water-quality evidence is inferred from a missing optional cache.</span></div>}
    {!payload && !error && <div className="reference-empty-state"><strong>Loading NYC distribution water-quality evidence…</strong></div>}
    {payload && <>
      <div className="reference-metric-grid">
        <article><span className="reference-metric-icon success">◎</span><div><small>Samples</small><strong>{number.format(payload.summary.sample_count)}</strong><span>DEP distribution records</span></div></article>
        <article><span className="reference-metric-icon">⌖</span><div><small>Sample sites</small><strong>{number.format(payload.summary.sample_site_count)}</strong><span>Source site identifiers</span></div></article>
        <article><span className="reference-metric-icon warning">CL</span><div><small>Coliform values</small><strong>{number.format(Number(payload.summary.samples_with_coliform_value ?? 0))}</strong><span>Raw qualifiers retained</span></div></article>
        <article><span className="reference-metric-icon">EC</span><div><small>E. coli values</small><strong>{number.format(Number(payload.summary.samples_with_e_coli_value ?? 0))}</strong><span>Raw qualifiers retained</span></div></article>
        <article><span className="reference-metric-icon">SRC</span><div><small>Generated</small><strong>{formatDate(payload.generated_at)}</strong><span>{formatTimestamp(payload.generated_at)}</span></div></article>
      </div>

      <div className="disclaimer"><strong>Unlinked evidence.</strong> Distribution sample sites are source-published sampling identifiers. This view does not attach samples to properties, cooling towers, domestic-water tanks or PWS profiles.</div>

      <div className="reference-table-card">
        <div className="reference-table-heading">
          <div><strong>{view === 'sites' ? 'Distribution sample sites' : 'Recent distribution samples'}</strong><span>{number.format(view === 'sites' ? sites.length : samples.length)} shown · raw measurement text and qualifiers preserved</span></div>
          <div className="page-actions">
            <button className={view === 'sites' ? 'active-control' : ''} onClick={() => setView('sites')}>Sites</button>
            <button className={view === 'samples' ? 'active-control' : ''} onClick={() => setView('samples')}>Samples</button>
            <select aria-label="Sample class" value={sampleClass} onChange={event => setSampleClass(event.target.value)}><option value="ALL">All classes</option>{classes.map(value => <option key={value} value={value}>{value}</option>)}</select>
            <input aria-label="Search distribution water-quality records" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search sample site or sample number…" />
          </div>
        </div>
        {view === 'sites' ? <div className="reference-table-scroll"><table className="reference-table distribution-site-table"><thead><tr><th>Sample site</th><th>Samples</th><th>First sample</th><th>Latest sample</th><th>Class counts</th><th>Residual chlorine</th><th>Coliform</th><th>Linkage</th></tr></thead><tbody>{sites.map(row => <tr key={row.sample_site ?? 'MISSING'}>
          <td><strong>{row.sample_site ?? 'Missing site'}</strong></td>
          <td>{number.format(row.sample_count)}</td>
          <td>{row.first_sample_date ? formatDate(row.first_sample_date) : '—'}</td>
          <td>{row.latest_sample_date ? formatDate(row.latest_sample_date) : '—'}</td>
          <td>{Object.entries(row.sample_class_counts).map(([key, value]) => `${key}: ${number.format(value)}`).join(' · ') || '—'}</td>
          <td>{measurementText(row.latest_measurements, 'residual_free_chlorine')}</td>
          <td>{measurementText(row.latest_measurements, 'coliform')}</td>
          <td><span className="muted-label">{row.property_link_confidence}</span></td>
        </tr>)}</tbody></table></div> : <div className="reference-table-scroll"><table className="reference-table distribution-sample-table"><thead><tr><th>Sample</th><th>Site</th><th>Class</th><th>Date</th><th>Residual chlorine</th><th>Turbidity</th><th>Fluoride</th><th>Coliform</th><th>E. coli</th></tr></thead><tbody>{samples.map(row => {
          const measurements = sampleMeasurements(row)
          const sampleId = sampleText(row, 'sample_id') ?? sampleText(row, 'sample_number') ?? 'sample'
          return <tr key={sampleId}>
            <td><strong>{sampleText(row, 'sample_number') ?? '—'}</strong><small>{sampleId}</small></td>
            <td>{sampleText(row, 'sample_site') ?? '—'}</td>
            <td>{sampleText(row, 'sample_class') ?? '—'}</td>
            <td>{sampleText(row, 'sample_date') ? formatDate(sampleText(row, 'sample_date') ?? '') : '—'}<small>{sampleText(row, 'sample_time') ?? ''}</small></td>
            <td>{measurementText(measurements, 'residual_free_chlorine')}</td>
            <td>{measurementText(measurements, 'turbidity')}</td>
            <td>{measurementText(measurements, 'fluoride')}</td>
            <td>{measurementText(measurements, 'coliform')}</td>
            <td>{measurementText(measurements, 'e_coli')}</td>
          </tr>
        })}</tbody></table></div>}
      </div>
      <div className="source-health-footnote">Distribution samples are intentionally represented as an unlinked water-quality workspace. Future property linkage must be exact or explicitly reviewed before appearing in account detail.</div>
    </>}
  </section>
}
