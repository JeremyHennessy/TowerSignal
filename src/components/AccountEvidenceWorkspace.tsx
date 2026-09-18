import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { loadProcurement, loadSystemDetail } from '../data/api'
import { formatDate, formatTimestamp } from '../domain/labels'
import { collectAccountFirmRoleEvidence, explicitAccountProcurementRecords } from '../domain/accountEvidence'
import { collectProcurementFirmRoleEvidence } from '../domain/procurementFirmRoles'
import type { SystemDetail } from '../types/data'
import type { ProcurementBundle, ProcurementRecord } from '../types/procurement'
import type { PropertyEnforcementContext } from '../types/enforcement'
import { BuildingWaterSignalsSection } from './BuildingWaterSignalsSection'
import { DomesticWaterSection, type SystemDetailWithDomesticWater } from './DomesticWaterSection'
import { InstitutionalFacilitySection } from './InstitutionalFacilitySection'
import { LeadServiceLineSection } from './LeadServiceLineSection'
import { LegacyDobProjectSection } from './LegacyDobProjectSection'
import { OfficialSwoSnapshotSection } from './OfficialSwoSnapshotSection'

const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 1 })
const money = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
let procurementPromise: Promise<ProcurementBundle> | null = null

function loadProcurementCached(): Promise<ProcurementBundle> {
  if (!procurementPromise) {
    procurementPromise = loadProcurement().catch(error => {
      procurementPromise = null
      throw error
    })
  }
  return procurementPromise
}

function systemIdFromHash(): string | null {
  const raw = window.location.hash.replace(/^#\/?/, '')
  const parts = raw.split('?')[0].split('/').filter(Boolean)
  if (parts[0] !== 'account' || !parts[1]) return null
  try { return decodeURIComponent(parts[1]) } catch { return parts[1] }
}

function Group({ title, summary, children }: { title: string; summary: string; children: ReactNode }) {
  return <details className="account-evidence-group">
    <summary><span><strong>{title}</strong><small>{summary}</small></span><span className="evidence-group-toggle">View</span></summary>
    <div className="account-evidence-group-body">{children}</div>
  </details>
}

function ComplianceEvidence({ detail }: { detail: EvidenceDetail }) {
  const enforcement = detail.property_enforcement_context
  const hpd = enforcement?.hpd_violations?.summary
  const facade = enforcement?.facade_compliance?.summary
  return <>
    <div className="account-evidence-metrics">
      <article><small>NYC Health inspections</small><strong>{detail.inspection_history.length.toLocaleString()}</strong><span>{detail.inspection_history.filter(item => item.violation_count > 0).length.toLocaleString()} with published violations</span></article>
      <article><small>Exact OATH cases</small><strong>{detail.oath_case_history?.length?.toLocaleString() ?? '0'}</strong><span>Summons → ticket exact identity only</span></article>
      <article><small>HPD open violations</small><strong>{hpd ? hpd.open_count.toLocaleString() : 'Unverified'}</strong><span>{hpd ? `${hpd.open_class_c_count.toLocaleString()} Class C` : 'No attached enforcement summary'}</span></article>
      <article><small>FISP / Local Law 11</small><strong>{facade?.latest_status ?? 'Not published'}</strong><span>{facade?.latest_cycle ? `Cycle ${facade.latest_cycle}` : 'No published cycle'}</span></article>
    </div>
    <OfficialSwoSnapshotSection detail={detail as SystemDetail} />
    <p className="microcopy">Complaint/disposition SWO evidence, the dated official issued/rescinded SWO snapshot, FISP filings, published Labor Law decisions, NYC Health violations and OATH case outcomes remain distinct evidence classes. A missing match is not converted into a clean/current status.</p>
  </>
}

function PropertyOwnershipEvidence({ detail }: { detail: EvidenceDetail }) {
  return <>
    <section className="evidence-subsection"><h4>Identity</h4><dl className="identity-grid"><div><dt>System</dt><dd>{detail.identity.system_id}</dd></div><div><dt>BIN</dt><dd>{detail.identity.bin ?? '—'}</dd></div><div><dt>BBL</dt><dd>{detail.identity.bbl ?? '—'}</dd></div><div><dt>Active equipment</dt><dd>{detail.identity.active_equipment}</dd></div><div><dt>Coordinates</dt><dd>{detail.identity.coordinate_status === 'VALID' && detail.identity.latitude != null && detail.identity.longitude != null ? `${detail.identity.latitude.toFixed(4)}, ${detail.identity.longitude.toFixed(4)}` : detail.identity.coordinate_status === 'INVALID_SOURCE' ? `Unusable source coordinates (${detail.identity.source_latitude_raw ?? 'blank'}, ${detail.identity.source_longitude_raw ?? 'blank'})` : 'Not published'}</dd></div></dl></section>
    {!detail.identity.bbl ? <div className="evidence-boundary"><strong>Property-level BBL evidence unavailable.</strong><p>This cooling-tower record has no usable BBL. TowerSignal does not infer a parcel identity to attach PLUTO ownership, HPD contacts, DOB project roles or ACRIS parties.</p></div> : <>
      <section className="evidence-subsection"><h4>PLUTO property context</h4>{!detail.building_context ? <div className="empty-inline">No exact BBL match was returned from NYC DCP PLUTO.</div> : <dl className="identity-grid"><div><dt>Owner</dt><dd>{detail.building_context.owner_name ?? '—'}</dd></div><div><dt>Land use</dt><dd>{detail.building_context.land_use ?? '—'}</dd></div><div><dt>Building class</dt><dd>{detail.building_context.building_class ?? '—'}</dd></div><div><dt>Year built</dt><dd>{detail.building_context.year_built || '—'}</dd></div><div><dt>Building area</dt><dd>{detail.building_context.building_area_sqft == null ? '—' : `${number.format(detail.building_context.building_area_sqft)} sq ft`}</dd></div><div><dt>Floors</dt><dd>{detail.building_context.floors == null ? '—' : number.format(detail.building_context.floors)}</dd></div><div><dt>Total units</dt><dd>{detail.building_context.total_units ?? '—'}</dd></div></dl>}</section>
      <section className="evidence-subsection"><h4>HPD registered contacts</h4>{!detail.hpd_registration ? <div className="empty-inline">No exact BBL match was found in HPD Multiple Dwelling Registrations. HPD scope does not cover every property type.</div> : detail.hpd_registration.contacts.length === 0 ? <div className="empty-inline">An HPD registration matched this BBL, but no public contact rows were returned.</div> : <div className="evidence-card-list">{detail.hpd_registration.contacts.map((contact, index) => <article className="evidence-card" key={`${contact.registration_contact_id ?? 'contact'}-${index}`}><strong>{contact.corporation_name ?? contact.person_name ?? contact.description ?? 'Name not published'}</strong><span>{contact.type ?? 'HPD contact'}{contact.title ? ` · ${contact.title}` : ''}</span><small>{contact.business_address ?? 'Business address not published'} · HPD registration {detail.hpd_registration?.registration_id ?? 'id not published'}</small></article>)}</div>}</section>
    </>}
    <p className="microcopy">PLUTO owner and HPD contact roles are public property/filing context. They are not relabeled as cooling-tower service providers or procurement decision-makers.</p>
  </>
}

function ProjectEvidence({ detail }: { detail: EvidenceDetail }) {
  const jobs = detail.dob_activity_history ?? []
  return <>
    <section className="evidence-subsection"><h4>DOB NOW project activity</h4>{jobs.length === 0 ? <div className="empty-inline">No exact-BBL DOB NOW job filing was attached.</div> : <div className="evidence-card-list">{jobs.slice(0, 12).map((job, index) => <article className="evidence-card" key={`${job.job_filing_number ?? 'job'}-${index}`}><div><strong>{job.job_filing_number ?? 'DOB filing'}</strong><span>{job.activity_date ? formatDate(job.activity_date) : 'Date not published'}</span></div><p>{job.job_description ?? 'No job description published.'}</p><small>{job.explicit_cooling_tower_mention ? 'Explicit cooling-tower wording' : job.mechanical_systems || job.boiler_equipment ? 'Mechanical / boiler source flag' : 'Property project context'} · Applicant {job.applicant_business_name ?? 'not published'} · Owner {job.owner_business_name ?? 'not published'}</small></article>)}</div>}</section>
    <LegacyDobProjectSection detail={detail} />
    <p className="microcopy">DOB applicants and owner businesses are recorded project roles only. A filing does not establish current service responsibility, an incumbent vendor, compliance state or contract award.</p>
  </>
}

function FirmRoleEvidence({ detail, procurementRecords, procurementError }: { detail: EvidenceDetail; procurementRecords: ProcurementRecord[] | null; procurementError: string | null }) {
  const sourceRows = collectAccountFirmRoleEvidence(detail).map(row => ({ ...row, sourceUrls: [] as string[], companyIdentity: null as string | null }))
  const procurementRows = procurementRecords == null ? [] : collectProcurementFirmRoleEvidence(procurementRecords)
  const rows = [...sourceRows, ...procurementRows]
  if (rows.length === 0 && procurementRecords == null && !procurementError) return <div className="loading-state">Loading source-observed and procurement-linked firm roles…</div>
  return <>
    {rows.length === 0 ? <div className="empty-inline">No source-named service/recorded role or explicitly account-linked procurement vendor is represented in the current evidence. This is not evidence that no firm relationship exists.</div> : <div className="observed-firm-role-list">{rows.map(row => <article className="observed-firm-role" key={row.key}>
      <div className="observed-firm-role-head"><div><strong>{row.name}</strong><span>{row.role}</span></div><span className={`relationship-chip relationship-${row.relationship.toLowerCase()}`}>{row.relationship.replaceAll('_', ' ')}</span></div>
      <dl className="identity-grid"><div><dt>Source / dataset</dt><dd>{row.sourceName}<small>{row.datasetId}</small></dd></div><div><dt>Observation</dt><dd>{row.observedDate ? formatDate(row.observedDate) : row.observedYear ? `Reporting year ${row.observedYear}` : 'Date not published'}</dd></div><div><dt>Identity basis</dt><dd>{row.matchBasis.replaceAll('_', ' ')}</dd></div><div><dt>Fact / confidence</dt><dd>{row.factClass.replaceAll('_', ' ')} · {row.confidence}</dd></div>{row.companyIdentity && <div><dt>Resolved company</dt><dd>{row.companyIdentity}</dd></div>}<div className="wide"><dt>Source reference</dt><dd>{row.sourceReference}</dd></div></dl>
      {row.sourceUrls.length > 0 && <div className="evidence-source-links">{row.sourceUrls.map((url, index) => <a href={url} target="_blank" rel="noreferrer" key={`${url}-${index}`}>Source {row.sourceUrls.length > 1 ? index + 1 : ''} ↗</a>)}</div>}
      <p className="microcopy">{row.serviceAssignmentBoundary}</p>
    </article>)}</div>}
    {procurementRecords == null && !procurementError && <div className="loading-state">Loading explicitly linked procurement firm roles…</div>}
    {procurementError && <div className="evidence-boundary"><strong>Procurement-linked firm roles unavailable.</strong><p>{procurementError}</p><p>No zero-vendor or no-relationship conclusion is inferred.</p></div>}
  </>
}

function ProcurementEvidence({ records, error }: { records: ProcurementRecord[] | null; error: string | null }) {
  if (error) return <div className="evidence-boundary"><strong>Procurement evidence unavailable.</strong><p>{error}</p><p>No zero-contract or no-vendor conclusion is inferred.</p></div>
  if (records == null) return <div className="loading-state">Loading explicitly linked procurement evidence…</div>
  if (records.length === 0) return <div className="empty-inline">No generated procurement record explicitly links this system through `tower_account_system_ids`. This is not evidence that no public or private contract exists.</div>
  return <div className="evidence-card-list">{records.slice(0, 20).map(record => {
    const links = record.source_urls?.length ? record.source_urls : record.source_url ? [record.source_url] : []
    const date = record.due_date ?? record.award_date ?? record.start_date ?? record.notice_start_date
    const amount = record.current_amount ?? record.original_amount ?? record.amount
    return <article className="evidence-card procurement-evidence-card" key={record.procurement_id}>
      <div><strong>{record.title ?? record.description ?? record.procurement_id}</strong><span>{date ? formatDate(date) : 'Date not published'}</span></div>
      <p>{record.buyer_name ?? record.agency ?? 'Buyer/agency not published'}{record.vendor_raw ? ` · ${record.vendor_raw}` : ''}</p>
      <small>{record.source} · {record.source_dataset_id ?? 'dataset id not published'} · tower link {record.tower_link_confidence ?? 'UNVERIFIED'} · {record.service_category}{amount != null ? ` · ${money.format(amount)}` : ''}</small>
      {links.length > 0 && <div className="evidence-source-links">{links.map((url, index) => <a href={url} target="_blank" rel="noreferrer" key={`${url}-${index}`}>Source {links.length > 1 ? index + 1 : ''} ↗</a>)}</div>}
    </article>
  })}</div>
}

function HistoricalEvidence({ detail }: { detail: EvidenceDetail }) {
  const profile = detail.historical_profile
  return <>
    {profile ? <div className="account-evidence-metrics"><article><small>Registered</small><strong>{profile.registration_date ? formatDate(profile.registration_date) : '—'}</strong><span>Source registration date</span></article><article><small>Reported samples</small><strong>{profile.sample.reported_sample_count.toLocaleString()}</strong><span>Full chronology remains in History</span></article><article><small>NYC Health inspections</small><strong>{profile.inspection.inspection_count.toLocaleString()}</strong><span>{profile.inspection.violation_citation_count.toLocaleString()} cited violation rows</span></article><article><small>OATH balance due</small><strong>{money.format(profile.oath.balance_due_total)}</strong><span>Exact-matched cases only</span></article></div> : <div className="empty-inline">Historical profile is not available in this generated record.</div>}
    <details className="evidence-provenance-details"><summary><strong>Source &amp; provenance</strong><span>{detail.metadata.sources.length} datasets</span></summary><div className="evidence-card-list">{detail.metadata.sources.map(source => <article className="evidence-card" key={source.dataset_id}><strong>{source.name}</strong><span>{source.dataset_id} · {source.source_record_count.toLocaleString()} source rows{source.matched_record_count != null ? ` · ${source.matched_record_count.toLocaleString()} exact-matched` : ''}</span><small>Retrieved {formatTimestamp(source.retrieved_at)}{source.source_last_updated_at ? ` · publisher updated ${formatTimestamp(source.source_last_updated_at)}` : ''}</small><small>{source.source_query_scope ?? 'Query scope not published'}</small>{source.url && <a href={source.url} target="_blank" rel="noreferrer">Official source ↗</a>}</article>)}</div></details>
    <p className="microcopy">Detailed sample, inspection, OATH, ACRIS, historical-water and TowerSignal change chronology remains in the History mode. This group is a compact evidence/provenance index, not a second history timeline.</p>
  </>
}

type EvidenceDetail = SystemDetailWithDomesticWater & { property_enforcement_context?: PropertyEnforcementContext | null }

export function AccountEvidenceWorkspace({ systemId = systemIdFromHash() }: { systemId?: string | null }) {
  const [detail, setDetail] = useState<EvidenceDetail | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [procurement, setProcurement] = useState<ProcurementBundle | null>(null)
  const [procurementLoaded, setProcurementLoaded] = useState(false)
  const [procurementError, setProcurementError] = useState<string | null>(null)

  useEffect(() => {
    if (!systemId) { setDetailError('Account system ID is missing from the route.'); return }
    let active = true
    setDetail(null); setDetailError(null)
    loadSystemDetail(systemId)
      .then(value => { if (active) setDetail(value as EvidenceDetail) })
      .catch(error => { if (active) setDetailError(error instanceof Error ? error.message : 'Unable to load account evidence') })
    return () => { active = false }
  }, [systemId])

  useEffect(() => {
    let active = true
    setProcurementLoaded(false); setProcurementError(null)
    loadProcurementCached()
      .then(value => { if (active) { setProcurement(value); setProcurementLoaded(true) } })
      .catch(error => { if (active) { setProcurementError(error instanceof Error ? error.message : 'Unable to load procurement evidence'); setProcurementLoaded(true) } })
    return () => { active = false }
  }, [])

  const linkedProcurement = useMemo(() => systemId && procurement ? explicitAccountProcurementRecords(procurement, systemId) : [], [procurement, systemId])
  const sourceFirmCount = detail ? collectAccountFirmRoleEvidence(detail).length : 0
  const procurementFirmCount = procurementLoaded && !procurementError ? collectProcurementFirmRoleEvidence(linkedProcurement).length : null
  const institutionalCount = detail?.cms_institutional_context?.facilities.length ?? 0
  const serviceLineCount = detail?.nyc_lead_service_lines?.records.length ?? 0

  return <section className="account-evidence-workspace" aria-labelledby="account-evidence-workspace-title">
    <div className="account-evidence-heading"><div><span className="eyebrow">Evidence architecture</span><h3 id="account-evidence-workspace-title">Account evidence</h3><p>Source records are grouped by decision use. Relationship classes remain explicit; missing evidence stays unknown rather than becoming zero or “none.”</p></div><span className="evidence-group-count">7 groups</span></div>
    {detailError ? <div className="error-state">{detailError}</div> : !detail ? <div className="loading-state">Loading source-backed account evidence…</div> : <>
      <Group title="Compliance" summary={`${detail.inspection_history.length} NYC Health inspections · ${detail.oath_case_history?.length ?? 0} exact OATH cases`}><ComplianceEvidence detail={detail} /></Group>
      <Group title="Property / Ownership" summary={`${detail.building_context?.owner_name ?? 'PLUTO owner not published'} · ${detail.hpd_registration?.contacts.length ?? 0} HPD contacts`}><PropertyOwnershipEvidence detail={detail} /></Group>
      <Group title="Project Activity" summary={`${detail.dob_activity_history?.length ?? 0} DOB NOW filings · legacy context kept separate`}><ProjectEvidence detail={detail} /></Group>
      <Group title="Domestic Water" summary={detail.domestic_water ? `${detail.domestic_water.summary.self_report_record_count} self reports · ${detail.domestic_water.summary.compliance_record_count} compliance records` : 'No exact-BIN DWT payload attached'}><DomesticWaterSection detail={detail} /><BuildingWaterSignalsSection detail={detail} /></Group>
      <Group title="Institutional / Infrastructure" summary={`${institutionalCount} CMS facilities · ${serviceLineCount} service-line records`}><InstitutionalFacilitySection detail={detail as SystemDetail} /><LeadServiceLineSection detail={detail as SystemDetail} /></Group>
      <Group title="Procurement / Commercial" summary={`${sourceFirmCount + (procurementFirmCount ?? 0)} source-observed/recorded/contract-linked firm roles${procurementFirmCount == null ? ' · procurement pending' : ''} · ${procurementLoaded && !procurementError ? linkedProcurement.length : '—'} explicit procurement links`}><section className="evidence-subsection"><h4>Observed firms &amp; roles</h4><FirmRoleEvidence detail={detail} procurementRecords={procurementLoaded && !procurementError ? linkedProcurement : null} procurementError={procurementError} /></section><section className="evidence-subsection"><h4>Explicitly linked procurement</h4><ProcurementEvidence records={procurementLoaded && !procurementError ? linkedProcurement : null} error={procurementError} /></section></Group>
      <Group title="Historical Evidence" summary={`${detail.metadata.sources.length} source datasets · detailed chronology remains in History`}><HistoricalEvidence detail={detail} /></Group>
    </>}
  </section>
}