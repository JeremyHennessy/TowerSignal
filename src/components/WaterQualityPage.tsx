import { useEffect, useMemo, useState } from 'react'
import { loadNycDistributionWater, loadNysLsliDetails, loadNysPublicWater, loadNysServiceLineSummary } from '../data/api'
import type { LsliDetailRecord, NysLsliDetailPayload, NysPublicWaterPayload, NysServiceLineInventorySummaryPayload, NycDistributionWaterPayload } from '../types/water'
import { formatDate, formatTimestamp } from '../domain/labels'
import { ShareButton } from './ShareButton'

const number = new Intl.NumberFormat('en-US')
const PAGE_SIZE = 40

type Measurement = { raw: string | null; numeric: number | null; qualifier: string }
type WaterWorkspace = 'nyc' | 'pws' | 'lsli'
type SortDirection = 'asc' | 'desc'
type WaterSort = { key: string; direction: SortDirection }

function measurementText(measurements: Record<string, Measurement> | null | undefined, key: string): string {
  const measurement = measurements?.[key]
  if (!measurement || measurement.raw == null) return '—'
  return measurement.qualifier && measurement.qualifier !== 'EQ' ? `${measurement.qualifier} ${measurement.raw}` : measurement.raw
}

function measurementNumeric(measurements: Record<string, Measurement> | null | undefined, key: string): number | string {
  const measurement = measurements?.[key]
  return measurement?.numeric ?? measurement?.raw ?? ''
}

function sampleText(row: Record<string, unknown>, key: string): string | null {
  const value = row[key]
  return typeof value === 'string' && value.trim() ? value : null
}

function sampleMeasurements(row: Record<string, unknown>): Record<string, Measurement> | null {
  const value = row.measurements
  return value && typeof value === 'object' ? value as Record<string, Measurement> : null
}

function sum(values: Array<number | null | undefined>): number {
  return values.reduce<number>((total, value) => total + (typeof value === 'number' ? value : 0), 0)
}

function compareValues(left: unknown, right: unknown): number {
  if (typeof left === 'number' && typeof right === 'number') return left - right
  if (typeof left === 'boolean' && typeof right === 'boolean') return Number(left) - Number(right)
  return String(left ?? '').localeCompare(String(right ?? ''), undefined, { numeric: true, sensitivity: 'base' })
}

function PageControls({ page, total, onPage }: { page: number; total: number; onPage: (page: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  if (pages <= 1) return null
  const safePage = Math.min(page, pages)
  return <div className="reference-pagination"><span>Page {safePage} of {pages}</span><div>
    <button disabled={safePage <= 1} onClick={() => onPage(safePage - 1)}>Previous</button>
    <button disabled={safePage >= pages} onClick={() => onPage(safePage + 1)}>Next</button>
  </div></div>
}

function inventoryValue(row: LsliDetailRecord, key: keyof NonNullable<LsliDetailRecord['inventory']>): number {
  return Number(row.inventory?.[key] ?? 0)
}

function defaultSort(workspace: WaterWorkspace, nycView: 'sites' | 'samples'): WaterSort {
  if (workspace === 'pws') return { key: 'violations', direction: 'desc' }
  if (workspace === 'lsli') return { key: 'lead', direction: 'desc' }
  return nycView === 'sites' ? { key: 'sample_count', direction: 'desc' } : { key: 'date', direction: 'desc' }
}

export function WaterQualityPage() {
  const [nyc, setNyc] = useState<NycDistributionWaterPayload | null>(null)
  const [pws, setPws] = useState<NysPublicWaterPayload | null>(null)
  const [lsli, setLsli] = useState<NysLsliDetailPayload | null>(null)
  const [serviceLines, setServiceLines] = useState<NysServiceLineInventorySummaryPayload | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const [workspace, setWorkspace] = useState<WaterWorkspace>('nyc')
  const [search, setSearch] = useState('')
  const [sampleClass, setSampleClass] = useState('ALL')
  const [nycView, setNycView] = useState<'sites' | 'samples'>('sites')
  const [pwsCounty, setPwsCounty] = useState('ALL')
  const [pwsLsli, setPwsLsli] = useState('ALL')
  const [lsliFocus, setLsliFocus] = useState('ALL')
  const [sort, setSort] = useState<WaterSort>({ key: 'sample_count', direction: 'desc' })
  const [page, setPage] = useState(1)

  useEffect(() => {
    let cancelled = false
    Promise.allSettled([
      loadNycDistributionWater(),
      loadNysPublicWater(),
      loadNysLsliDetails(),
      loadNysServiceLineSummary(),
    ]).then(results => {
      if (cancelled) return
      const nextErrors: string[] = []
      const [nycResult, pwsResult, lsliResult, serviceLineResult] = results
      if (nycResult.status === 'fulfilled') setNyc(nycResult.value)
      else nextErrors.push(`NYC distribution: ${nycResult.reason instanceof Error ? nycResult.reason.message : 'unavailable'}`)
      if (pwsResult.status === 'fulfilled') setPws(pwsResult.value)
      else nextErrors.push(`NYS public water: ${pwsResult.reason instanceof Error ? pwsResult.reason.message : 'unavailable'}`)
      if (lsliResult.status === 'fulfilled') setLsli(lsliResult.value)
      else nextErrors.push(`NYS LSLI: ${lsliResult.reason instanceof Error ? lsliResult.reason.message : 'unavailable'}`)
      if (serviceLineResult.status === 'fulfilled') setServiceLines(serviceLineResult.value)
      else nextErrors.push(`NYS service lines: ${serviceLineResult.reason instanceof Error ? serviceLineResult.reason.message : 'unavailable'}`)
      setErrors(nextErrors)
    })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    setPage(1)
    setSearch('')
    setSort(defaultSort(workspace, nycView))
  }, [workspace, nycView])
  useEffect(() => { setPage(1) }, [search, sampleClass, pwsCounty, pwsLsli, lsliFocus, sort])

  const classes = useMemo(() => Object.keys(nyc?.summary.sample_class_counts ?? {}).sort(), [nyc])
  const pwsCounties = useMemo(() => [...new Set((pws?.pws_systems ?? []).map(row => row.lead_service_line_inventory_principal_county).filter(Boolean))].sort() as string[], [pws])

  const sites = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (nyc?.sites ?? []).filter(row => (!query || String(row.sample_site ?? '').toLowerCase().includes(query)) && (sampleClass === 'ALL' || Boolean(row.sample_class_counts[sampleClass])))
  }, [nyc, sampleClass, search])
  const sortedSites = useMemo(() => [...sites].sort((a, b) => {
    const value = (row: (typeof sites)[number]): unknown => {
      if (sort.key === 'site') return row.sample_site
      if (sort.key === 'first_sample') return row.first_sample_date
      if (sort.key === 'latest_sample') return row.latest_sample_date
      if (sort.key === 'classes') return Object.values(row.sample_class_counts).reduce((sum, count) => sum + count, 0)
      if (sort.key === 'residual') return measurementNumeric(row.latest_measurements, 'residual_free_chlorine')
      if (sort.key === 'coliform') return measurementNumeric(row.latest_measurements, 'coliform')
      if (sort.key === 'linkage') return row.property_link_confidence
      return row.sample_count
    }
    const result = compareValues(value(a), value(b)) || compareValues(a.sample_site, b.sample_site)
    return sort.direction === 'asc' ? result : -result
  }), [sites, sort])

  const samples = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (nyc?.samples ?? []).filter(row => {
      const site = sampleText(row, 'sample_site') ?? ''
      const klass = sampleText(row, 'sample_class') ?? ''
      return (!query || site.toLowerCase().includes(query) || (sampleText(row, 'sample_number') ?? '').toLowerCase().includes(query)) && (sampleClass === 'ALL' || klass === sampleClass)
    })
  }, [nyc, sampleClass, search])
  const sortedSamples = useMemo(() => [...samples].sort((a, b) => {
    const value = (row: Record<string, unknown>): unknown => {
      const measurements = sampleMeasurements(row)
      if (sort.key === 'sample') return sampleText(row, 'sample_number') ?? sampleText(row, 'sample_id')
      if (sort.key === 'site') return sampleText(row, 'sample_site')
      if (sort.key === 'class') return sampleText(row, 'sample_class')
      if (sort.key === 'residual') return measurementNumeric(measurements, 'residual_free_chlorine')
      if (sort.key === 'turbidity') return measurementNumeric(measurements, 'turbidity')
      if (sort.key === 'fluoride') return measurementNumeric(measurements, 'fluoride')
      if (sort.key === 'coliform') return measurementNumeric(measurements, 'coliform')
      if (sort.key === 'ecoli') return measurementNumeric(measurements, 'e_coli')
      return sampleText(row, 'sample_date') ?? ''
    }
    const result = compareValues(value(a), value(b)) || compareValues(sampleText(a, 'sample_number'), sampleText(b, 'sample_number'))
    return sort.direction === 'asc' ? result : -result
  }), [samples, sort])

  const publicWaterRows = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (pws?.pws_systems ?? []).filter(row => {
      if (query && ![row.pws_id, row.pws_name, row.system_type, row.lead_service_line_inventory_principal_county].some(value => String(value ?? '').toLowerCase().includes(query))) return false
      if (pwsCounty !== 'ALL' && row.lead_service_line_inventory_principal_county !== pwsCounty) return false
      if (pwsLsli === 'REQUIRED' && !row.lead_service_line_inventory_required) return false
      if (pwsLsli === 'NOT_REQUIRED' && row.lead_service_line_inventory_required) return false
      return true
    })
  }, [pws, search, pwsCounty, pwsLsli])
  const sortedPublicWaterRows = useMemo(() => [...publicWaterRows].sort((a, b) => {
    const value = (row: (typeof publicWaterRows)[number]): unknown => {
      if (sort.key === 'pws') return row.pws_id
      if (sort.key === 'system') return row.pws_name
      if (sort.key === 'county') return row.lead_service_line_inventory_principal_county
      if (sort.key === 'type') return row.system_type ?? row.system_types?.join(' ')
      if (sort.key === 'population') return row.total_population ?? 0
      if (sort.key === 'contacts') return row.contact_count
      if (sort.key === 'lsli') return Boolean(row.lead_service_line_inventory_required)
      return row.violation_count_2025 ?? 0
    }
    const result = compareValues(value(a), value(b)) || compareValues(a.pws_id, b.pws_id)
    return sort.direction === 'asc' ? result : -result
  }), [publicWaterRows, sort])

  const lsliRows = useMemo(() => {
    const query = search.trim().toLowerCase()
    return (lsli?.details ?? []).filter(row => {
      if (query && ![row.pws_id, row.pws_name, row.owner_or_operator_form_contact?.name].some(value => String(value ?? '').toLowerCase().includes(query))) return false
      if (lsliFocus === 'LEAD' && inventoryValue(row, 'lead_service_lines') <= 0) return false
      if (lsliFocus === 'UNKNOWN' && inventoryValue(row, 'unknown_service_lines') <= 0) return false
      return true
    })
  }, [lsli, search, lsliFocus])
  const sortedLsliRows = useMemo(() => [...lsliRows].sort((a, b) => {
    const value = (row: LsliDetailRecord): unknown => {
      if (sort.key === 'pws') return row.pws_id
      if (sort.key === 'system') return row.pws_name
      if (sort.key === 'total') return inventoryValue(row, 'total_service_lines')
      if (sort.key === 'identified') return inventoryValue(row, 'identified_service_lines')
      if (sort.key === 'lead') return inventoryValue(row, 'lead_service_lines')
      if (sort.key === 'gslrr') return inventoryValue(row, 'gslrr_service_lines')
      if (sort.key === 'non_lead') return inventoryValue(row, 'non_lead_service_lines')
      if (sort.key === 'unknown') return inventoryValue(row, 'unknown_service_lines')
      if (sort.key === 'contact') return row.owner_or_operator_form_contact?.name
      if (sort.key === 'status') return row.detail_status
      return inventoryValue(row, 'lead_service_lines')
    }
    const result = compareValues(value(a), value(b)) || compareValues(a.pws_id, b.pws_id)
    return sort.direction === 'asc' ? result : -result
  }), [lsliRows, sort])

  const pwsPopulation = useMemo(() => sum((pws?.pws_systems ?? []).map(row => row.total_population)), [pws])
  const pwsContacts = useMemo(() => sum((pws?.pws_systems ?? []).map(row => row.contact_count)), [pws])
  const pwsLeadRequired = useMemo(() => (pws?.pws_systems ?? []).filter(row => row.lead_service_line_inventory_required).length, [pws])
  const pwsViolations = useMemo(() => sum((pws?.pws_systems ?? []).map(row => row.violation_count_2025)), [pws])
  const inventoryTotals = useMemo(() => ({
    total: sum((lsli?.details ?? []).map(row => row.inventory?.total_service_lines)),
    lead: sum((lsli?.details ?? []).map(row => row.inventory?.lead_service_lines)),
    gslrr: sum((lsli?.details ?? []).map(row => row.inventory?.gslrr_service_lines)),
    unknown: sum((lsli?.details ?? []).map(row => row.inventory?.unknown_service_lines)),
  }), [lsli])

  const nycRows = nycView === 'sites' ? sortedSites : sortedSamples
  const activeRows = workspace === 'nyc' ? nycRows : workspace === 'pws' ? sortedPublicWaterRows : sortedLsliRows
  const pageCount = Math.max(1, Math.ceil(activeRows.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount)
  const paged = activeRows.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)
  const changeSort = (key: string, defaultDirection: SortDirection = 'asc') => setSort(current => current.key === key
    ? { key, direction: current.direction === 'asc' ? 'desc' : 'asc' }
    : { key, direction: defaultDirection })
  const sortIndicator = (key: string) => sort.key === key ? (sort.direction === 'asc' ? ' ↑' : ' ↓') : ''

  return <section className="product-page water-quality-page">
    <div className="product-page-heading">
      <div><span className="page-kicker">New York · water intelligence</span><h1>Water Quality</h1><p>Distribution sampling, public-water-system profiles and lead-service-line inventory evidence in one source-bounded workspace. Records remain separate unless their public identifiers establish an exact relationship.</p></div>
      <div className="page-actions"><ShareButton label="Share this view" /></div>
    </div>

    <div className="page-actions" role="tablist" aria-label="Water intelligence datasets">
      <button className={workspace === 'nyc' ? 'active-control' : ''} onClick={() => setWorkspace('nyc')}>NYC Distribution</button>
      <button className={workspace === 'pws' ? 'active-control' : ''} onClick={() => setWorkspace('pws')}>NYS Public Water</button>
      <button className={workspace === 'lsli' ? 'active-control' : ''} onClick={() => setWorkspace('lsli')}>Lead Service Lines</button>
    </div>

    {errors.length > 0 && <div className="reference-empty-state compact"><strong>Some optional water datasets are unavailable.</strong><span>{errors.join(' · ')}</span><span>Missing optional caches do not create inferred property or account evidence.</span></div>}

    {workspace === 'nyc' && <>
      {!nyc && <div className="reference-empty-state"><strong>Loading NYC distribution water-quality evidence…</strong></div>}
      {nyc && <>
        <div className="reference-metric-grid">
          <article><span className="reference-metric-icon success">◎</span><div><small>Samples</small><strong>{number.format(nyc.summary.sample_count)}</strong><span>DEP distribution records</span></div></article>
          <article><span className="reference-metric-icon">⌖</span><div><small>Sample sites</small><strong>{number.format(nyc.summary.sample_site_count)}</strong><span>Source site identifiers</span></div></article>
          <article><span className="reference-metric-icon warning">CL</span><div><small>Coliform values</small><strong>{number.format(Number(nyc.summary.samples_with_coliform_value ?? 0))}</strong><span>Raw qualifiers retained</span></div></article>
          <article><span className="reference-metric-icon">EC</span><div><small>E. coli values</small><strong>{number.format(Number(nyc.summary.samples_with_e_coli_value ?? 0))}</strong><span>Raw qualifiers retained</span></div></article>
          <article><span className="reference-metric-icon">SRC</span><div><small>Generated</small><strong>{formatDate(nyc.generated_at)}</strong><span>{formatTimestamp(nyc.generated_at)}</span></div></article>
        </div>
        <div className="disclaimer"><strong>Unlinked distribution evidence.</strong> Sample sites are source-published identifiers. They are not attached to cooling towers, domestic-water tanks, properties or PWS profiles without a separate exact relationship.</div>
        <div className="reference-table-card">
          <div className="reference-table-heading">
            <div><strong>{nycView === 'sites' ? 'Distribution sample sites' : 'Distribution samples'}</strong><span>{number.format(nycRows.length)} matching · {number.format(paged.length)} shown on this page</span></div>
            <div className="page-actions">
              <button className={nycView === 'sites' ? 'active-control' : ''} onClick={() => setNycView('sites')}>Sites</button>
              <button className={nycView === 'samples' ? 'active-control' : ''} onClick={() => setNycView('samples')}>Samples</button>
              <select aria-label="Sample class" value={sampleClass} onChange={event => setSampleClass(event.target.value)}><option value="ALL">All classes</option>{classes.map(value => <option key={value} value={value}>{value}</option>)}</select>
              <input aria-label="Search distribution water-quality records" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search site or sample…" />
            </div>
          </div>
          {nycView === 'sites' ? <div className="reference-table-scroll"><table className="reference-table distribution-site-table"><thead><tr>
            <th><button onClick={() => changeSort('site')}>Sample site{sortIndicator('site')}</button></th>
            <th><button onClick={() => changeSort('sample_count', 'desc')}>Samples{sortIndicator('sample_count')}</button></th>
            <th><button onClick={() => changeSort('first_sample')}>First sample{sortIndicator('first_sample')}</button></th>
            <th><button onClick={() => changeSort('latest_sample', 'desc')}>Latest sample{sortIndicator('latest_sample')}</button></th>
            <th><button onClick={() => changeSort('classes', 'desc')}>Class counts{sortIndicator('classes')}</button></th>
            <th><button onClick={() => changeSort('residual', 'desc')}>Residual chlorine{sortIndicator('residual')}</button></th>
            <th><button onClick={() => changeSort('coliform', 'desc')}>Coliform{sortIndicator('coliform')}</button></th>
            <th><button onClick={() => changeSort('linkage')}>Linkage{sortIndicator('linkage')}</button></th>
          </tr></thead><tbody>{(paged as typeof sortedSites).map(row => <tr key={row.sample_site ?? 'MISSING'}>
            <td><strong>{row.sample_site ?? 'Missing site'}</strong></td><td>{number.format(row.sample_count)}</td><td>{row.first_sample_date ? formatDate(row.first_sample_date) : '—'}</td><td>{row.latest_sample_date ? formatDate(row.latest_sample_date) : '—'}</td><td>{Object.entries(row.sample_class_counts).map(([key, value]) => `${key}: ${number.format(value)}`).join(' · ') || '—'}</td><td>{measurementText(row.latest_measurements, 'residual_free_chlorine')}</td><td>{measurementText(row.latest_measurements, 'coliform')}</td><td><span className="muted-label">{row.property_link_confidence}</span></td>
          </tr>)}</tbody></table></div> : <div className="reference-table-scroll"><table className="reference-table distribution-sample-table"><thead><tr>
            <th><button onClick={() => changeSort('sample')}>Sample{sortIndicator('sample')}</button></th><th><button onClick={() => changeSort('site')}>Site{sortIndicator('site')}</button></th><th><button onClick={() => changeSort('class')}>Class{sortIndicator('class')}</button></th><th><button onClick={() => changeSort('date', 'desc')}>Date{sortIndicator('date')}</button></th><th><button onClick={() => changeSort('residual', 'desc')}>Residual chlorine{sortIndicator('residual')}</button></th><th><button onClick={() => changeSort('turbidity', 'desc')}>Turbidity{sortIndicator('turbidity')}</button></th><th><button onClick={() => changeSort('fluoride', 'desc')}>Fluoride{sortIndicator('fluoride')}</button></th><th><button onClick={() => changeSort('coliform', 'desc')}>Coliform{sortIndicator('coliform')}</button></th><th><button onClick={() => changeSort('ecoli', 'desc')}>E. coli{sortIndicator('ecoli')}</button></th>
          </tr></thead><tbody>{(paged as Array<Record<string, unknown>>).map(row => {
            const measurements = sampleMeasurements(row); const sampleId = sampleText(row, 'sample_id') ?? sampleText(row, 'sample_number') ?? 'sample'
            return <tr key={sampleId}><td><strong>{sampleText(row, 'sample_number') ?? '—'}</strong><small>{sampleId}</small></td><td>{sampleText(row, 'sample_site') ?? '—'}</td><td>{sampleText(row, 'sample_class') ?? '—'}</td><td>{sampleText(row, 'sample_date') ? formatDate(sampleText(row, 'sample_date') ?? '') : '—'}<small>{sampleText(row, 'sample_time') ?? ''}</small></td><td>{measurementText(measurements, 'residual_free_chlorine')}</td><td>{measurementText(measurements, 'turbidity')}</td><td>{measurementText(measurements, 'fluoride')}</td><td>{measurementText(measurements, 'coliform')}</td><td>{measurementText(measurements, 'e_coli')}</td></tr>
          })}</tbody></table></div>}
          <PageControls page={safePage} total={nycRows.length} onPage={setPage} />
        </div>
      </>}
    </>}

    {workspace === 'pws' && <>
      {!pws && <div className="reference-empty-state"><strong>NYS public-water-system cache is not available in this build.</strong><span>No cooling-tower or property relationship is inferred from its absence.</span></div>}
      {pws && <>
        <div className="reference-metric-grid">
          <article><span className="reference-metric-icon success">PWS</span><div><small>Public water systems</small><strong>{number.format(pws.pws_systems.length)}</strong><span>Source PWSID spine</span></div></article>
          <article><span className="reference-metric-icon">POP</span><div><small>Population represented</small><strong>{number.format(pwsPopulation)}</strong><span>Source-reported totals</span></div></article>
          <article><span className="reference-metric-icon warning">LSL</span><div><small>LSLI required</small><strong>{number.format(pwsLeadRequired)}</strong><span>Systems flagged by source</span></div></article>
          <article><span className="reference-metric-icon">CT</span><div><small>Published contacts</small><strong>{number.format(pwsContacts)}</strong><span>Source-specific contact roles</span></div></article>
          <article><span className="reference-metric-icon warning">V</span><div><small>2025 violations</small><strong>{number.format(pwsViolations)}</strong><span>Observed source records</span></div></article>
        </div>
        <div className="disclaimer"><strong>PWSID evidence boundary.</strong> Public-water contacts and operators describe the public water system. They are not cooling-tower contractors, building owners or account contacts unless another exact source establishes that relationship.</div>
        <div className="reference-table-card">
          <div className="reference-table-heading"><div><strong>NYS public-water systems</strong><span>{number.format(sortedPublicWaterRows.length)} matching source profiles · {number.format(paged.length)} shown</span></div><div className="page-actions"><input aria-label="Search public water systems" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search PWSID, name or county…" /><select aria-label="Public water county" value={pwsCounty} onChange={event => setPwsCounty(event.target.value)}><option value="ALL">All counties</option>{pwsCounties.map(value => <option key={value} value={value}>{value}</option>)}</select><select aria-label="Public water LSLI requirement" value={pwsLsli} onChange={event => setPwsLsli(event.target.value)}><option value="ALL">Any LSLI status</option><option value="REQUIRED">LSLI required</option><option value="NOT_REQUIRED">Not flagged</option></select></div></div>
          <div className="reference-table-scroll"><table className="reference-table"><thead><tr><th><button onClick={() => changeSort('pws')}>PWSID{sortIndicator('pws')}</button></th><th><button onClick={() => changeSort('system')}>System{sortIndicator('system')}</button></th><th><button onClick={() => changeSort('county')}>County{sortIndicator('county')}</button></th><th><button onClick={() => changeSort('type')}>Type{sortIndicator('type')}</button></th><th><button onClick={() => changeSort('population', 'desc')}>Population{sortIndicator('population')}</button></th><th><button onClick={() => changeSort('contacts', 'desc')}>Contacts{sortIndicator('contacts')}</button></th><th><button onClick={() => changeSort('lsli', 'desc')}>LSLI{sortIndicator('lsli')}</button></th><th><button onClick={() => changeSort('violations', 'desc')}>2025 violations{sortIndicator('violations')}</button></th></tr></thead><tbody>{(paged as typeof sortedPublicWaterRows).map(row => <tr key={row.pws_id}><td><strong>{row.pws_id}</strong></td><td>{row.pws_name ?? '—'}</td><td>{row.lead_service_line_inventory_principal_county ?? '—'}</td><td>{row.system_type ?? row.system_types?.join(' · ') ?? '—'}</td><td>{row.total_population == null ? '—' : number.format(row.total_population)}</td><td>{number.format(row.contact_count)}</td><td>{row.lead_service_line_inventory_required ? <span className="health-badge health-warning">Required</span> : <span className="muted-label">Not flagged</span>}</td><td>{number.format(row.violation_count_2025 ?? 0)}</td></tr>)}</tbody></table></div>
          <PageControls page={safePage} total={sortedPublicWaterRows.length} onPage={setPage} />
        </div>
      </>}
    </>}

    {workspace === 'lsli' && <>
      {!lsli && !serviceLines && <div className="reference-empty-state"><strong>NYS lead-service-line caches are not available in this build.</strong><span>No property assignment is inferred.</span></div>}
      {(lsli || serviceLines) && <>
        <div className="reference-metric-grid">
          <article><span className="reference-metric-icon success">PWS</span><div><small>Detailed inventories</small><strong>{number.format(lsli?.details.length ?? 0)}</strong><span>Exact source PWSID detail pages</span></div></article>
          <article><span className="reference-metric-icon">Σ</span><div><small>Service lines</small><strong>{number.format(inventoryTotals.total)}</strong><span>Source-reported inventory total</span></div></article>
          <article><span className="reference-metric-icon warning">Pb</span><div><small>Lead lines</small><strong>{number.format(inventoryTotals.lead)}</strong><span>Reported lead classification</span></div></article>
          <article><span className="reference-metric-icon warning">?</span><div><small>Unknown lines</small><strong>{number.format(inventoryTotals.unknown)}</strong><span>Reported unknown classification</span></div></article>
          <article><span className="reference-metric-icon">ADR</span><div><small>Address-level rows</small><strong>{number.format(serviceLines?.summary.row_count ?? 0)}</strong><span>{number.format(serviceLines?.summary.rows_with_valid_nys_location ?? 0)} with valid NYS location</span></div></article>
        </div>
        <div className="disclaimer"><strong>Inventory identity boundary.</strong> LSLI detail is joined by published PWSID. Address-level inventory remains source-native locality/address evidence; TowerSignal does not infer a cooling-tower account, building BBL or service responsibility when those identifiers are absent.</div>
        {serviceLines && <div className="reference-table-card"><div className="reference-table-heading"><div><strong>Address-level service-line coverage</strong><span>Source-normalized summary; raw address rows remain in the generated data file</span></div></div><div className="reference-metric-grid">
          <article><div><small>NYC rows</small><strong>{number.format(Object.values(serviceLines.summary.nyc_borough_row_counts).reduce((a, b) => a + b, 0))}</strong><span>{Object.entries(serviceLines.summary.nyc_borough_row_counts).map(([key, value]) => `${key}: ${number.format(value)}`).join(' · ') || 'No NYC borough rows'}</span></div></article>
          <article><div><small>Public-side material</small><strong>{number.format(Object.values(serviceLines.summary.normalized_public_material_counts).reduce((a, b) => a + b, 0))}</strong><span>{Object.entries(serviceLines.summary.normalized_public_material_counts).slice(0, 4).map(([key, value]) => `${key}: ${number.format(value)}`).join(' · ')}</span></div></article>
          <article><div><small>Customer-side material</small><strong>{number.format(Object.values(serviceLines.summary.normalized_customer_material_counts).reduce((a, b) => a + b, 0))}</strong><span>{Object.entries(serviceLines.summary.normalized_customer_material_counts).slice(0, 4).map(([key, value]) => `${key}: ${number.format(value)}`).join(' · ')}</span></div></article>
        </div></div>}
        {lsli && <div className="reference-table-card">
          <div className="reference-table-heading"><div><strong>Lead Service Line Inventory detail</strong><span>{number.format(sortedLsliRows.length)} matching PWS inventories · {number.format(paged.length)} shown</span></div><div className="page-actions"><input aria-label="Search lead service line inventories" value={search} onChange={event => setSearch(event.target.value)} placeholder="Search PWSID, system or contact…" /><select aria-label="Lead service line focus" value={lsliFocus} onChange={event => setLsliFocus(event.target.value)}><option value="ALL">All inventories</option><option value="LEAD">Has lead lines</option><option value="UNKNOWN">Has unknown lines</option></select></div></div>
          <div className="reference-table-scroll"><table className="reference-table"><thead><tr><th><button onClick={() => changeSort('pws')}>PWSID{sortIndicator('pws')}</button></th><th><button onClick={() => changeSort('system')}>System{sortIndicator('system')}</button></th><th><button onClick={() => changeSort('total', 'desc')}>Total{sortIndicator('total')}</button></th><th><button onClick={() => changeSort('identified', 'desc')}>Identified{sortIndicator('identified')}</button></th><th><button onClick={() => changeSort('lead', 'desc')}>Lead{sortIndicator('lead')}</button></th><th><button onClick={() => changeSort('gslrr', 'desc')}>GSLRR{sortIndicator('gslrr')}</button></th><th><button onClick={() => changeSort('non_lead', 'desc')}>Non-lead{sortIndicator('non_lead')}</button></th><th><button onClick={() => changeSort('unknown', 'desc')}>Unknown{sortIndicator('unknown')}</button></th><th><button onClick={() => changeSort('contact')}>Owner/operator form contact{sortIndicator('contact')}</button></th><th><button onClick={() => changeSort('status')}>Status{sortIndicator('status')}</button></th></tr></thead><tbody>{(paged as typeof sortedLsliRows).map(row => <tr key={row.pws_id}><td><strong>{row.pws_id}</strong></td><td>{row.pws_name ?? '—'}</td><td>{number.format(inventoryValue(row, 'total_service_lines'))}</td><td>{number.format(inventoryValue(row, 'identified_service_lines'))}</td><td>{number.format(inventoryValue(row, 'lead_service_lines'))}</td><td>{number.format(inventoryValue(row, 'gslrr_service_lines'))}</td><td>{number.format(inventoryValue(row, 'non_lead_service_lines'))}</td><td>{number.format(inventoryValue(row, 'unknown_service_lines'))}</td><td>{row.owner_or_operator_form_contact?.name ?? '—'}<small>{row.owner_or_operator_form_contact?.relationship_role ?? ''}</small></td><td>{row.detail_status ?? '—'}</td></tr>)}</tbody></table></div>
          <PageControls page={safePage} total={sortedLsliRows.length} onPage={setPage} />
        </div>}
      </>}
    </>}

    <div className="source-health-footnote">Water datasets remain separate evidence domains. TowerSignal exposes what each source says and does not convert public-system, distribution-sample or service-line records into account evidence without an exact public identifier.</div>
  </section>
}
