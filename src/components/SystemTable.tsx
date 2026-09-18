import { useEffect, useMemo, useState } from 'react'
import type { SystemSummary } from '../types/data'
import { loadDomesticWaterMarket } from '../data/api'
import { formatDate, signalLabel } from '../domain/labels'
import { exactDomesticWaterProperty, indexDomesticWaterProperties, normalizeProspectPreset, prospectPresets, type DomesticWaterMarketWithProperties, type ProspectPreset, type ProspectSystemSummary } from '../domain/prospectPreset'
import { StatusBadge } from './StatusBadge'

const PAGE_SIZE = 50

type SortKey = 'priority_score' | 'address' | 'active_equipment' | 'days_since_latest_sample' | 'latest_inspection_date' | 'oath_case_count'

function priorityBand(score: number): string {
  if (score >= 70) return 'high'
  if (score >= 40) return 'medium'
  return 'low'
}

function count(value: number | null | undefined): string {
  return value == null ? '—' : value.toLocaleString()
}

function area(value: number | null | undefined): string {
  return value == null ? 'Not published' : `${Math.round(value).toLocaleString()} sq ft`
}

function AccountCell({ row }: { row: SystemSummary }) {
  return <td className="account-cell"><strong>{row.address ?? 'Address unavailable'}</strong><span>{row.borough ?? '—'} · {row.zip ?? '—'}</span><small className="mono">{row.system_id} · {row.active_equipment} active unit{row.active_equipment === 1 ? '' : 's'}</small></td>
}

function PriorityCell({ row }: { row: SystemSummary }) {
  return <td><div className={`priority-indicator priority-${priorityBand(row.priority_score)}`}><strong>{row.priority_score}</strong><span><i style={{ width:`${Math.max(4, row.priority_score)}%` }} /></span></div></td>
}

function TimingRow({ row, onSelect }: { row: ProspectSystemSummary; onSelect: (row: SystemSummary) => void }) {
  const acrisCount = row.acris_recent_document_count ?? 0
  const hpdOpen = row.hpd_open_violation_count ?? 0
  const swoCount = row.stop_work_order_event_count ?? 0
  const fispStatus = row.facade_latest_status
  const hasActivity = (row.oath_case_count ?? 0) > 0 || (row.dob_recent_activity_count ?? 0) > 0 || acrisCount > 0 || hpdOpen > 0 || swoCount > 0 || Boolean(fispStatus)
  return <tr key={row.system_id} onClick={() => onSelect(row)} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') onSelect(row) }}>
    <AccountCell row={row} />
    <PriorityCell row={row} />
    <td><span className={`signal signal-${row.primary_signal.toLowerCase()}`}>{signalLabel(row.primary_signal)}</span>{row.confirmed_violation && <small className="urgent-copy">Confirmed record</small>}</td>
    <td>{(row.hpd_contact_count ?? 0) > 0 ? <span className="contact-ready">✓ {row.hpd_contact_count} HPD contact{row.hpd_contact_count === 1 ? '' : 's'}</span> : <span className="muted-copy">No matched contact</span>}</td>
    <td>{formatDate(row.latest_sample_date)}<small>{row.days_since_latest_sample == null ? 'No usable date' : `${row.days_since_latest_sample} days ago`}</small></td>
    <td><div className="activity-stack">{(row.oath_case_count ?? 0) > 0 && <span>OATH · {row.oath_case_count}</span>}{(row.dob_recent_activity_count ?? 0) > 0 && <span>DOB · {row.dob_recent_activity_count}</span>}{acrisCount > 0 && <span title={row.latest_acris_recorded_date ? `Latest recorded ${formatDate(row.latest_acris_recorded_date)}` : undefined}>ACRIS · {acrisCount}</span>}{hpdOpen > 0 && <span title={row.latest_hpd_violation_inspection_date ? `Latest inspection ${formatDate(row.latest_hpd_violation_inspection_date)}` : undefined}>HPD open · {hpdOpen}</span>}{swoCount > 0 && <span title="DOB complaint-disposition Stop Work Order evidence; not a claim that an order remains active">SWO evidence · {swoCount}</span>}{fispStatus && <span>FISP · {fispStatus}</span>}{!hasActivity && <span className="muted-copy">No recent match</span>}</div></td>
    <td><StatusBadge value={row.evidence_confidence} /></td><td className="row-arrow">›</td>
  </tr>
}

function SalesRow({ row, onSelect, market, marketError, propertyIndex }: {
  row: ProspectSystemSummary
  onSelect: (row: SystemSummary) => void
  market: DomesticWaterMarketWithProperties | null | undefined
  marketError: string | null
  propertyIndex: Map<string, ReturnType<typeof exactDomesticWaterProperty>>
}) {
  const observation = exactDomesticWaterProperty(row, propertyIndex)
  const providerState = market === undefined
    ? <span className="muted-copy">Loading DWT observations…</span>
    : !market || marketError
      ? <span className="muted-copy">DWT provider/lab source unavailable</span>
      : !row.bin && !row.bbl
        ? <span className="muted-copy">No usable BIN/BBL for exact DWT join</span>
        : !observation
          ? <span className="muted-copy">No exact-key DWT inspection observation</span>
          : <div className="commercial-stack">
              {observation.current_observed_provider_raw ? <span><strong>{observation.current_observed_provider_raw}</strong><small>Observed DWT inspection firm</small></span> : <span className="muted-copy">Latest exact-key DWT observation did not name an inspection firm</span>}
              {observation.current_observed_lab_raw ? <span><strong>{observation.current_observed_lab_raw}</strong><small>Observed DWT laboratory</small></span> : <span className="muted-copy">Latest exact-key DWT observation did not name a laboratory</span>}
              <small>{observation.latest_inspection_date ? `Observed ${formatDate(observation.latest_inspection_date)}` : observation.latest_reporting_year ? `Reporting year ${observation.latest_reporting_year}` : 'Observation date not published'} · exact {row.bin ? 'BIN' : 'BBL'}</small>
            </div>

  const dobAvailable = row.dob_activity_count != null || row.dob_recent_activity_count != null || row.dob_explicit_cooling_tower_count != null || row.dob_mechanical_or_boiler_count != null
  return <tr key={row.system_id} onClick={() => onSelect(row)} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') onSelect(row) }}>
    <AccountCell row={row} />
    <PriorityCell row={row} />
    <td><div className="commercial-stack">{row.hpd_contact_count == null ? <span className="muted-copy">HPD contact coverage unavailable</span> : row.hpd_contact_count > 0 ? <span className="contact-ready">✓ {row.hpd_contact_count} HPD contact{row.hpd_contact_count === 1 ? '' : 's'}</span> : <span className="muted-copy">No matched HPD contact</span>}{row.pluto_owner_name ? <span><strong>{row.pluto_owner_name}</strong><small>PLUTO owner · exact BBL</small></span> : <small>PLUTO owner not matched or published</small>}</div></td>
    <td><div className="commercial-stack"><span><strong>{area(row.pluto_building_area_sqft)}</strong><small>PLUTO building area</small></span><span>{row.active_equipment} active cooling-tower unit{row.active_equipment === 1 ? '' : 's'}</span></div></td>
    <td>{providerState}</td>
    <td>{dobAvailable ? <div className="commercial-stack"><span>DOB recent · {count(row.dob_recent_activity_count)}</span><span>Explicit cooling tower · {count(row.dob_explicit_cooling_tower_count)}</span><span>Mechanical / boiler · {count(row.dob_mechanical_or_boiler_count)}</span><small>{row.latest_dob_activity_date ? `Latest ${formatDate(row.latest_dob_activity_date)}` : 'No recent DOB activity date published'}</small></div> : <span className="muted-copy">DOB activity summary unavailable</span>}</td>
    <td>{row.cms_institutional_facility_count == null ? <span className="muted-copy">Institutional context unavailable</span> : row.cms_institutional_facility_count > 0 ? <div className="commercial-stack"><span><strong>{row.cms_institutional_facility_count}</strong> exact property-linked CMS facilit{row.cms_institutional_facility_count === 1 ? 'y' : 'ies'}</span><small>{row.cms_institutional_facility_types?.join(' · ') || 'Facility type not published'}</small></div> : <span className="muted-copy">No exact property-linked CMS facility</span>}</td>
    <td><StatusBadge value={row.evidence_confidence} /></td><td className="row-arrow">›</td>
  </tr>
}

function FieldRow({ row, onSelect }: { row: ProspectSystemSummary; onSelect: (row: SystemSummary) => void }) {
  const complaintSwo = row.stop_work_order_event_count
  const snapshotStatus = row.official_swo_snapshot_observation_status
  const dwtAvailable = row.dwt_planimetric_tank_count != null || row.dwt_compliance_record_count != null || row.dwt_self_report_record_count != null
  return <tr key={row.system_id} onClick={() => onSelect(row)} tabIndex={0} onKeyDown={event => { if (event.key === 'Enter') onSelect(row) }}>
    <AccountCell row={row} />
    <PriorityCell row={row} />
    <td><div className="commercial-stack"><span><strong>{row.active_equipment}</strong> registered active unit{row.active_equipment === 1 ? '' : 's'}</span>{row.planimetric_bin_match === true ? <span>2022 planimetric features · {count(row.planimetric_building_tower_count)}</span> : row.planimetric_bin_match === false ? <span className="muted-copy">No exact-BIN 2022 planimetric match</span> : <span className="muted-copy">Planimetric coverage unavailable</span>}{row.building_footprint_bin_match === true && <small>Current building footprint matched by exact BIN</small>}</div></td>
    <td><strong>{formatDate(row.latest_sample_date)}</strong><small>{row.days_since_latest_sample == null ? 'No usable public sample date' : `${row.days_since_latest_sample} days ago`}</small></td>
    <td><div className="commercial-stack"><span><strong>{formatDate(row.latest_inspection_date)}</strong><small>{row.latest_inspection_type ?? 'Inspection type not published'}</small></span>{row.inspection_count == null ? <small>Inspection count unavailable</small> : <small>{row.inspection_count} published inspection record{row.inspection_count === 1 ? '' : 's'}</small>}</div></td>
    <td>{dwtAvailable ? <div className="commercial-stack"><span>Roof tanks · {count(row.dwt_planimetric_tank_count)}</span><span>DWT self reports · {count(row.dwt_self_report_record_count)}</span><span>DWT compliance · {count(row.dwt_compliance_record_count)}</span>{row.dwt_latest_self_report_inspection_date && <small>Latest DWT inspection {formatDate(row.dwt_latest_self_report_inspection_date)}</small>}</div> : <span className="muted-copy">Domestic-water account context unavailable</span>}</td>
    <td>{row.nyc_lead_service_line_record_count == null && row.cms_institutional_facility_count == null ? <span className="muted-copy">Infrastructure context unavailable</span> : <div className="commercial-stack">{row.nyc_lead_service_line_record_count != null && <span>Lead-service-line records · {row.nyc_lead_service_line_record_count}{row.nyc_lead_service_line_materials?.length ? <small>{row.nyc_lead_service_line_materials.join(' · ')}</small> : null}</span>}{row.cms_institutional_facility_count != null && <span>CMS facilities · {row.cms_institutional_facility_count}</span>}</div>}</td>
    <td><div className="commercial-stack">{complaintSwo == null ? <span className="muted-copy">Complaint/disposition SWO evidence unavailable</span> : <span>SWO complaint dispositions · {complaintSwo}<small>Complaint/disposition evidence; not current-order status</small></span>}{snapshotStatus === 'MATCHED_DATED_OBSERVATION' ? <span>DOB dated SWO snapshot · {count(row.official_swo_snapshot_record_count)}<small>Active at snapshot {count(row.official_swo_active_at_snapshot_count)} · rescinded at snapshot {count(row.official_swo_rescinded_at_snapshot_count)} · 2022–2024 observation, not current 2026 status</small></span> : snapshotStatus === 'NO_MATCH_IN_DATED_SNAPSHOT' ? <span className="muted-copy">No match in dated DOB SWO snapshot<small>Not proof that no current order exists</small></span> : snapshotStatus === 'NO_USABLE_BIN' ? <span className="muted-copy">Dated DOB SWO snapshot unavailable: no usable BIN</span> : <span className="muted-copy">Official dated SWO snapshot coverage unavailable</span>}{row.hpd_open_violation_count != null && <span>HPD open · {row.hpd_open_violation_count}</span>}{row.facade_latest_status && <span>FISP · {row.facade_latest_status}</span>}</div></td>
    <td><StatusBadge value={row.evidence_confidence} /></td><td className="row-arrow">›</td>
  </tr>
}

export function SystemTable({ rows, onSelect, preset: presetValue = 'timing', onPresetChange }: { rows: SystemSummary[]; onSelect: (row: SystemSummary) => void; preset?: ProspectPreset | string; onPresetChange?: (preset: ProspectPreset) => void }) {
  const preset = normalizeProspectPreset(presetValue)
  const [page, setPage] = useState(0)
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({ key: 'priority_score', dir: 'desc' })
  const [market, setMarket] = useState<DomesticWaterMarketWithProperties | null | undefined>(undefined)
  const [marketError, setMarketError] = useState<string | null>(null)

  useEffect(() => {
    if (preset === 'timing' || market !== undefined) return
    let active = true
    loadDomesticWaterMarket()
      .then(payload => {
        if (!active) return
        if (!payload) {
          setMarket(null)
          setMarketError('Domestic-water market artifact is unavailable')
          return
        }
        const enriched = payload as DomesticWaterMarketWithProperties
        if (!Array.isArray(enriched.properties)) {
          setMarket(null)
          setMarketError('Domestic-water market artifact does not publish property observations')
          return
        }
        setMarket(enriched)
        setMarketError(null)
      })
      .catch(error => {
        if (!active) return
        setMarket(null)
        setMarketError(error instanceof Error ? error.message : 'Domestic-water market artifact is unavailable')
      })
    return () => { active = false }
  }, [preset, market])

  const propertyIndex = useMemo(() => indexDomesticWaterProperties(market?.properties ?? []), [market])
  const sorted = useMemo(() => [...rows].sort((a,b) => {
    const av = a[sort.key] ?? ''; const bv = b[sort.key] ?? ''
    const result = typeof av === 'number' && typeof bv === 'number' ? av - bv : String(av).localeCompare(String(bv))
    return sort.dir === 'asc' ? result : -result
  }), [rows, sort])
  const maxPage = Math.max(0, Math.ceil(sorted.length / PAGE_SIZE) - 1)
  const activePage = Math.min(page, maxPage)
  const visible = sorted.slice(activePage * PAGE_SIZE, activePage * PAGE_SIZE + PAGE_SIZE) as ProspectSystemSummary[]
  const changeSort = (key: SortKey) => setSort(current => current.key === key ? { key, dir: current.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: key === 'priority_score' ? 'desc' : 'asc' })
  const changePreset = (next: ProspectPreset) => {
    setPage(0)
    onPresetChange?.(next)
  }

  return <>
    <div className="prospect-preset-bar" aria-label="Prospect column presets">
      <div><span className="eyebrow">Column preset</span><strong>{prospectPresets.find(item => item.value === preset)?.detail}</strong></div>
      <div className="prospect-preset-buttons" role="group" aria-label="Prospect table columns">{prospectPresets.map(item => <button type="button" key={item.value} className={preset === item.value ? 'active' : ''} aria-pressed={preset === item.value} onClick={() => changePreset(item.value)}>{item.label}</button>)}</div>
    </div>
    <div className={`table-card account-table-card prospect-table-preset-${preset}`} data-prospect-preset={preset}>
      <div className="table-heading"><div><strong>{rows.length.toLocaleString()}</strong> matching systems</div><div>Showing {visible.length ? activePage * PAGE_SIZE + 1 : 0}–{Math.min((activePage + 1) * PAGE_SIZE, rows.length)}</div></div>
      {rows.length === 0 ? <div className="empty-state"><strong>No accounts match these filters.</strong><span>Try widening the territory, timing signal or priority criteria.</span></div> : <div className="table-scroll"><table className="account-table"><thead><tr>
        {preset === 'timing' && <><th><button onClick={() => changeSort('address')}>Account</button></th><th><button onClick={() => changeSort('priority_score')}>Priority</button></th><th>Timing signal</th><th>Contact</th><th><button onClick={() => changeSort('days_since_latest_sample')}>Sampling</button></th><th><button onClick={() => changeSort('oath_case_count')}>Activity</button></th><th>Evidence</th><th aria-label="Open account" /></>}
        {preset === 'sales' && <><th><button onClick={() => changeSort('address')}>Account</button></th><th><button onClick={() => changeSort('priority_score')}>Priority</button></th><th>Contact / owner</th><th>Property scale</th><th>Observed firms</th><th>Project activity</th><th>Institutional</th><th>Evidence</th><th aria-label="Open account" /></>}
        {preset === 'field' && <><th><button onClick={() => changeSort('address')}>Account</button></th><th><button onClick={() => changeSort('priority_score')}>Priority</button></th><th><button onClick={() => changeSort('active_equipment')}>Equipment / roof</button></th><th><button onClick={() => changeSort('days_since_latest_sample')}>Sampling</button></th><th><button onClick={() => changeSort('latest_inspection_date')}>Inspection</button></th><th>Domestic water</th><th>Infrastructure</th><th>Enforcement</th><th>Evidence</th><th aria-label="Open account" /></>}
      </tr></thead><tbody>{visible.map(row => preset === 'timing'
        ? <TimingRow key={row.system_id} row={row} onSelect={onSelect} />
        : preset === 'sales'
          ? <SalesRow key={row.system_id} row={row} onSelect={onSelect} market={market} marketError={marketError} propertyIndex={propertyIndex} />
          : <FieldRow key={row.system_id} row={row} onSelect={onSelect} />)}</tbody></table></div>}
      <div className="pagination"><button disabled={activePage === 0} onClick={() => setPage(p => Math.max(0,p-1))}>Previous</button><span>Page {activePage + 1} of {maxPage + 1}</span><button disabled={activePage === maxPage} onClick={() => setPage(p => Math.min(maxPage,p+1))}>Next</button></div>
    </div>
  </>
}
