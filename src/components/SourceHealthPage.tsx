import { useEffect, useMemo, useState } from 'react'
import type { SystemsPayload } from '../types/data'
import type { ProcurementBundle, ProcurementSourceHealth } from '../types/procurement'
import type { CoverageAuditPayload } from '../types/coverage'
import { loadCoverageAudit, loadProcurement } from '../data/api'
import { formatTimestamp } from '../domain/labels'
import { safeSourceUrl } from '../domain/sourceHealthExpansion'
import { ShareButton } from './ShareButton'
import { SourceHealthExpansion } from './SourceHealthExpansion'

const number = new Intl.NumberFormat('en-US')

type ProcurementHealthRow = ProcurementSourceHealth & { source_url: string | null }

const fallbackDiagnosticSourceUrls: Record<string, string> = {
  nys_registry: 'https://health.data.ny.gov/Health/New-York-State-Cooling-Tower-Registry-Weekly-Extr/24a4-muw7',
  labor_law_published_decisions: 'https://www.nycourts.gov/reporter/RSS.shtml',
  acris_recent: 'https://data.cityofnewyork.us/City-Government/ACRIS-Real-Property-Master/bnx9-e6tj',
}

function SourceNameLink({ name, url }: { name: string; url: string | null }) {
  return <strong>{url ? <a href={url} target="_blank" rel="noreferrer">{name}</a> : name}</strong>
}

function diagnosticSourceUrl(payload: SystemsPayload, source: { source_key: string; dataset_id: string }): string | null {
  const metadataUrl = (payload.metadata.sources ?? []).find(item => item.dataset_id === source.dataset_id)?.url
  return safeSourceUrl(metadataUrl) ?? safeSourceUrl(fallbackDiagnosticSourceUrls[source.source_key])
}

function recordSourceUrl(source: Record<string, unknown>, keys: string[]): string | null {
  for (const key of keys) {
    const url = safeSourceUrl(source[key])
    if (url) return url
  }
  return null
}

function procurementHealthRows(procurement: ProcurementBundle | null): ProcurementHealthRow[] {
  if (!procurement) return []
  const checkbookSourceUrl = safeSourceUrl(procurement.checkbook.source.documentation_url) ?? safeSourceUrl(procurement.checkbook.source.api_url)
  const rows: ProcurementHealthRow[] = [
    { ...procurement.cityRecord.source_health, source_url: safeSourceUrl(procurement.cityRecord.source.dataset_page) },
    ...Object.values(procurement.checkbook.source_health).map(source => ({ ...source, source_url: checkbookSourceUrl })),
  ]
  if (procurement.openBookWater) {
    const source = procurement.openBookWater.source
    const transportComplete = source.transport_complete === true
    const schemaValid = source.schema_valid === true
    rows.push({
      source: 'NYS_OPEN_BOOK', status: transportComplete && schemaValid ? 'HEALTHY' : 'WARNING',
      record_count: procurement.openBookWater.summary.source_transaction_count,
      relevant_record_count: procurement.openBookWater.summary.relevant_transaction_count,
      normalized_contract_count: procurement.openBookWater.summary.relevant_contract_count,
      normalized_notice_count: 0, resolved_company_count: 0,
      unresolved_vendor_count: procurement.openBookWater.summary.relevant_vendor_count,
      facility_link_count: 0, exact_tower_link_count: 0, pagination_complete: transportComplete, schema_valid: schemaValid,
      freshness: `generated ${procurement.openBookWater.generated_at.slice(0, 10)}`,
      status_reasons: ['CSV transport hash verified', 'facility links intentionally unlinked'],
      source_url: recordSourceUrl(source, ['search_page', 'source_url', 'export_url']),
    })
  }
  if (procurement.nychaWater) {
    const sourceMetadata = procurement.nychaWater.source
    const sourceRows = procurement.nychaWater.source_health
    const partitionsHealthy = sourceRows.every(row => row.status === 'HEALTHY')
    const paginationComplete = sourceRows.every(row => row.pagination_complete === true)
    const schemaValid = sourceRows.every(row => row.schema_valid === true)
    rows.push({
      source: 'NYC_CHECKBOOK_NYCHA', status: partitionsHealthy && paginationComplete && schemaValid ? 'HEALTHY' : 'WARNING',
      record_count: procurement.nychaWater.summary.source_record_count,
      relevant_record_count: procurement.nychaWater.summary.relevant_release_line_count,
      normalized_contract_count: procurement.nychaWater.summary.relevant_contract_count,
      normalized_notice_count: 0, resolved_company_count: 0,
      unresolved_vendor_count: procurement.nychaWater.summary.relevant_vendor_count,
      facility_link_count: 0, exact_tower_link_count: 0, pagination_complete: paginationComplete, schema_valid: schemaValid,
      freshness: `${procurement.nychaWater.summary.fiscal_year_count} fiscal-year partitions`,
      status_reasons: ['NYCHA location text retained as source context', 'line/release amounts are not summed as company revenue'],
      source_url: recordSourceUrl(sourceMetadata, ['contract_api_url', 'api_url', 'source_url']),
    })
  }
  return rows
}

function percent(numerator: number, denominator: number): string {
  return denominator > 0 ? `${(numerator / denominator * 100).toFixed(1)}%` : '—'
}

function bytes(value: number | null | undefined): string {
  const size = Number(value ?? 0)
  if (size >= 1024 * 1024 * 1024) return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${number.format(size)} B`
}

function observedText(observed: Record<string, unknown>): string {
  return Object.entries(observed)
    .filter(([, value]) => value !== null && value !== undefined)
    .slice(0, 5)
    .map(([key, value]) => `${key.replaceAll('_', ' ')}: ${typeof value === 'number' ? number.format(value) : String(value)}`)
    .join(' · ')
}

export function SourceHealthPage({ payload }: { payload: SystemsPayload }) {
  const [procurement, setProcurement] = useState<ProcurementBundle | null>(null)
  const [procurementError, setProcurementError] = useState<string | null>(null)
  const [coverageAudit, setCoverageAudit] = useState<CoverageAuditPayload | null>(null)
  const [coverageAuditError, setCoverageAuditError] = useState<string | null>(null)

  useEffect(() => {
    loadProcurement().then(setProcurement).catch(error => setProcurementError(error instanceof Error ? error.message : 'Unable to load procurement source health'))
    loadCoverageAudit().then(setCoverageAudit).catch(error => setCoverageAuditError(error instanceof Error ? error.message : 'Unable to load production coverage audit'))
  }, [])

  const health = payload.metadata.source_health ?? []
  const procurementHealth = procurementHealthRows(procurement)
  const healthy = health.filter(source => source.status === 'HEALTHY').length
  const warning = health.filter(source => source.status === 'WARNING').length
  const failed = health.filter(source => source.status === 'FAILED').length
  const coverages = health.map(source => source.coverage_percentage).filter((value): value is number => value != null)
  const averageCoverage = coverages.length > 0 ? coverages.reduce((sum, value) => sum + value, 0) / coverages.length : null
  const procurementRecords = procurementHealth.reduce((sum, source) => sum + source.record_count, 0)
  const integratedArtifacts = coverageAudit?.source_artifacts.filter(artifact => artifact.exists && artifact.integration_status === 'INTEGRATED').length ?? 0
  const historyEvents = useMemo(() => Object.values(coverageAudit?.history_depth ?? {}).reduce((total, item) => total + Number(item.event_count ?? 0), 0), [coverageAudit])

  return <section className="product-page source-health-page">
    <div className="product-page-heading">
      <div><span className="page-kicker">New York · data trust</span><h1>Source Health &amp; Coverage</h1><p>Freshness, exact-identity coverage, generated-dataset integration and known evidence gaps across TowerSignal.</p></div>
      <div className="page-actions"><ShareButton label="Share this view" /></div>
    </div>

    <div className="reference-metric-grid source-health-metrics">
      <article><span className="reference-metric-icon success">✓</span><div><small>Healthy diagnostic sources</small><strong>{healthy}/{health.length || '—'}</strong><span>{failed > 0 ? `${failed} failed` : 'No failed sources'}</span></div></article>
      <article><span className="reference-metric-icon warning">◷</span><div><small>Warnings</small><strong>{warning}</strong><span>Require review, not silent fallback</span></div></article>
      <article><span className="reference-metric-icon">◎</span><div><small>Average account coverage</small><strong>{averageCoverage == null ? '—' : `${averageCoverage.toFixed(1)}%`}</strong><span>Across sources publishing health diagnostics</span></div></article>
      <article><span className="reference-metric-icon success">⌂</span><div><small>NYC accounts</small><strong>{number.format(payload.summary.registered_systems)}</strong><span>Current normalized systems</span></div></article>
      <article><span className="reference-metric-icon">▤</span><div><small>Procurement source rows</small><strong>{procurement ? number.format(procurementRecords) : '—'}</strong><span>City Record, Checkbook and water caches</span></div></article>
    </div>

    {health.length === 0 ? <div className="reference-empty-state"><strong>Source-health metrics are not available in this payload.</strong><span>TowerSignal will not infer a healthy state when source diagnostics are missing.</span></div> : <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>{health.length} sources publishing account-health diagnostics</strong><span>Generated {formatTimestamp(payload.metadata.generated_at)}</span></div></div>
      <div className="reference-table-scroll"><table className="reference-table source-health-table"><thead><tr><th>Source</th><th>Status</th><th>Coverage</th><th>Retrieved</th><th>Normalized</th><th>Matched</th><th>Attached</th><th>Represented</th><th>Health note</th></tr></thead><tbody>{health.map(source => <tr key={source.source_key}>
        <td><SourceNameLink name={source.name} url={diagnosticSourceUrl(payload, source)} /><small>{source.dataset_id} · {source.entity_unit}</small></td>
        <td><span className={`health-badge health-${source.status.toLowerCase()}`}>{source.status}</span></td>
        <td><strong>{source.coverage_percentage == null ? 'n/a' : `${source.coverage_percentage.toFixed(1)}%`}</strong>{source.coverage_change_percentage_points != null && <small>{source.coverage_change_percentage_points >= 0 ? '+' : ''}{source.coverage_change_percentage_points.toFixed(1)} pp vs prior</small>}</td>
        <td>{number.format(source.retrieved_record_count)}</td><td>{number.format(source.normalized_entity_count)}</td><td>{number.format(source.matched_entity_count)}</td><td>{number.format(source.attached_entity_count)}</td><td>{number.format(source.displayed_entity_count)}</td>
        <td><span>{source.coverage_note}</span>{source.status_reasons.length > 0 && <small>{source.status_reasons.join(' · ')}</small>}</td>
      </tr>)}</tbody></table></div>
    </div>}

    <SourceHealthExpansion payload={payload} />

    <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>Completeness &amp; identity audit</strong><span>{coverageAudit ? `Generated ${formatTimestamp(coverageAudit.generated_at)}` : 'Build 015 production completeness audit'}</span></div></div>
      {coverageAuditError ? <div className="reference-empty-state"><strong>Coverage audit unavailable.</strong><span>{coverageAuditError}</span><span>No completeness claim is inferred from a missing audit artifact.</span></div> : !coverageAudit ? <div className="reference-empty-state"><strong>Loading completeness audit…</strong></div> : <>
        <div className="reference-metric-grid">
          <article><span className="reference-metric-icon success">BIN</span><div><small>NYC systems with BIN</small><strong>{percent(coverageAudit.nyc.identifier_coverage.with_bin, coverageAudit.nyc.identifier_coverage.systems)}</strong><span>{number.format(coverageAudit.nyc.identifier_coverage.with_bin)} / {number.format(coverageAudit.nyc.identifier_coverage.systems)}</span></div></article>
          <article><span className="reference-metric-icon warning">BBL</span><div><small>NYC systems with source BBL</small><strong>{percent(coverageAudit.nyc.identifier_coverage.with_bbl, coverageAudit.nyc.identifier_coverage.systems)}</strong><span>{number.format(coverageAudit.nyc.identifier_coverage.missing_bbl)} source BBL gaps</span></div></article>
          <article><span className="reference-metric-icon">ART</span><div><small>Integrated generated datasets</small><strong>{integratedArtifacts}/{coverageAudit.source_artifacts.length}</strong><span>Validated production artifacts</span></div></article>
          <article><span className="reference-metric-icon warning">GAP</span><div><small>Explicit gap classes</small><strong>{number.format(coverageAudit.gap_analysis.length)}</strong><span>Known scope/identity constraints</span></div></article>
          <article><span className="reference-metric-icon">H</span><div><small>Durable history events</small><strong>{number.format(historyEvents)}</strong><span>{bytes(coverageAudit.storage_footprint.history_artifact_bytes)} deployed history</span></div></article>
          <article><span className="reference-metric-icon">DATA</span><div><small>Published data footprint</small><strong>{bytes(coverageAudit.storage_footprint.public_data_total_bytes)}</strong><span>{number.format(coverageAudit.storage_footprint.file_count ?? 0)} generated files</span></div></article>
        </div>
        <div className="disclaimer"><strong>Identity coverage is not sales coverage.</strong> A missing source BBL, HPD registration or recent ACRIS event does not mean the building, owner or service relationship is absent. It means that specific source cannot support that claim under the current exact-identity contract.</div>
        <div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Borough</th><th>Systems</th><th>With BIN</th><th>BIN coverage</th><th>With source BBL</th><th>BBL coverage</th></tr></thead><tbody>{Object.entries(coverageAudit.nyc.identifier_coverage.by_borough).map(([borough, values]) => <tr key={borough}><td><strong>{borough}</strong></td><td>{number.format(values.systems)}</td><td>{number.format(values.with_bin)}</td><td>{percent(values.with_bin, values.systems)}</td><td>{number.format(values.with_bbl)}</td><td>{percent(values.with_bbl, values.systems)}</td></tr>)}</tbody></table></div>
      </>}
    </div>

    {coverageAudit && <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>Known evidence gaps &amp; next actions</strong><span>Classified so expected source scope is not mistaken for data loss</span></div></div>
      <div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Gap</th><th>Classification</th><th>Observed</th><th>Interpretation</th><th>Next action</th></tr></thead><tbody>{coverageAudit.gap_analysis.map(gap => <tr key={gap.gap_key}><td><strong>{gap.gap_key}</strong></td><td><span className="health-badge health-warning">{gap.classification}</span></td><td>{observedText(gap.observed) || '—'}</td><td>{gap.interpretation}</td><td>{gap.next_action}</td></tr>)}</tbody></table></div>
    </div>}

    {coverageAudit && <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>Generated dataset inventory</strong><span>Validated caches already available to product surfaces</span></div></div>
      <div className="reference-table-scroll"><table className="reference-table"><thead><tr><th>Dataset</th><th>Status</th><th>Artifact</th><th>Identity / evidence contract</th><th>Supports</th><th>Size</th></tr></thead><tbody>{coverageAudit.source_artifacts.map(artifact => <tr key={artifact.source_key}><td><strong>{artifact.source_key.replaceAll('_', ' ')}</strong></td><td><span className={`health-badge ${artifact.exists ? 'health-healthy' : 'health-warning'}`}>{artifact.integration_status}</span></td><td><a href={`${import.meta.env.BASE_URL}data/${artifact.artifact}`} target="_blank" rel="noreferrer">{artifact.artifact}</a></td><td>{artifact.authoritative_contract}</td><td>{artifact.decisions_supported.join(' · ') || 'Context'}</td><td>{bytes(artifact.artifact_bytes)}</td></tr>)}</tbody></table></div>
    </div>}

    <div className="reference-table-card">
      <div className="reference-table-heading"><div><strong>Procurement sources</strong><span>Retrieval, normalization and linkage remain separate from account-source coverage.</span></div></div>
      {procurementError ? <div className="reference-empty-state"><strong>Procurement source health unavailable.</strong><span>{procurementError}</span><span>No healthy status is inferred when the production procurement payload cannot be loaded.</span></div> : !procurement ? <div className="reference-empty-state"><strong>Loading procurement source health…</strong></div> : <><div className="source-health-warning-stack">
        {procurement.sourceErrors.nysAuthorities && <div className="reference-empty-state compact"><strong>NYS authority procurement unavailable.</strong><span>{procurement.sourceErrors.nysAuthorities}</span></div>}
        {procurement.sourceErrors.openBookWater && <div className="reference-empty-state compact"><strong>Open Book water procurement unavailable.</strong><span>{procurement.sourceErrors.openBookWater}</span></div>}
        {procurement.sourceErrors.nychaWater && <div className="reference-empty-state compact"><strong>NYCHA water procurement unavailable.</strong><span>{procurement.sourceErrors.nychaWater}</span></div>}
      </div><div className="reference-table-scroll"><table className="reference-table procurement-health-table"><thead><tr><th>Source</th><th>Status</th><th>Source rows</th><th>Relevant</th><th>Contracts</th><th>Notices</th><th>Companies resolved</th><th>Vendors unresolved</th><th>Facility links</th><th>Exact tower links</th><th>Guards</th></tr></thead><tbody>{procurementHealth.map(source => <tr key={source.source}>
        <td><SourceNameLink name={source.source} url={source.source_url} /><small>{source.freshness ?? 'freshness not published'}</small></td><td><span className={`health-badge health-${source.status.toLowerCase()}`}>{source.status}</span></td><td>{number.format(source.record_count)}</td><td>{number.format(source.relevant_record_count)}</td><td>{number.format(source.normalized_contract_count)}</td><td>{number.format(source.normalized_notice_count)}</td><td>{number.format(source.resolved_company_count)}</td><td>{number.format(source.unresolved_vendor_count)}</td><td>{number.format(source.facility_link_count)}</td><td>{number.format(source.exact_tower_link_count)}</td><td><span>{source.pagination_complete ? 'Pagination complete' : 'Pagination incomplete'}</span><small>{source.schema_valid ? 'Schema valid' : 'Schema invalid'}</small></td>
      </tr>)}</tbody></table></div></>}
    </div>

    {payload.metadata.priority_model_version === '1.1' && <div className="disclaimer"><strong>Research-priority model 1.1.</strong> Source-dated findings and named-building evidence are scored with explicit limits and exclusions. This is not a calibrated health-risk or purchase-probability model. <a href="data/priority-model-review.json" target="_blank" rel="noreferrer">Full before / after model review</a>. The coverage-audit governance below describes its original baseline.</div>}
    {coverageAudit && <div className="disclaimer"><strong>Earlier coverage-audit governance.</strong> Priority Score 1.0 changed: {coverageAudit.governance.priority_score_1_0_changed ? 'yes' : 'no'} · fuzzy matching used: {coverageAudit.governance.fuzzy_matching_used ? 'yes' : 'no'} · Opportunity Score authorized: {coverageAudit.governance.opportunity_score_authorized ? 'yes' : 'no'}. {coverageAudit.governance.follow_on_rule}</div>}
    <div className="source-health-footnote">Source health distinguishes expected scope limits from unexpected data loss. Procurement, public-water and other context remain unlinked to cooling-tower accounts until an exact or explicitly reviewed relationship is available.</div>
  </section>
}
