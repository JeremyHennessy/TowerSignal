import type { SystemDetail } from '../types/data'

const COMPLIANCE_URL = 'https://data.cityofnewyork.us/Health/NYC-Drinking-Water-Tank-Inspections-and-Audits-Com/rytv-g5ui'
const SELF_REPORT_URL = 'https://data.cityofnewyork.us/Health/Self-Reported-Drinking-Water-Tank-Inspection-Resul/gjm4-k24g'
const WATER_TANK_URL = 'https://services6.arcgis.com/yG5s3afENB5iO9fj/ArcGIS/rest/services/Water_Tank_2022/FeatureServer/27'

type PlanimetricWaterTankFeature = {
  global_id: string
  source_id: string | null
  bin: string
  feature_code: string | null
  status: string | null
  base_elevation_ft: number | null
  top_elevation_ft: number | null
  height_ft: number | null
  geometry: unknown
  imagery_year: 2022
  location_level: 'ROOF_LEVEL'
  location_basis: 'SOURCE_FEATURE_CLASS_CAPTURE_RULE'
  match_basis: 'BIN_EXACT'
}

type DwtComplianceRecord = {
  bin: string
  house: string | null
  street_name: string | null
  zip_code: string | null
  borough: string | null
  status: string | null
  number_of_dwt: number | null
  activity_type: string | null
  activity_year: string | null
  violation_code: string | null
  law_section: string | null
  violation_text: string | null
  compliance_year: string | null
  date_of_occurrence: string | null
  summons_number: string | null
  match_basis: 'BIN_EXACT'
}

type DwtSelfReportRecord = {
  bin: string
  reporting_year: string | null
  tank_num: string | null
  inspection_by_firm: string | null
  inspection_performed: string | null
  inspection_date: string | null
  sediment_result: string | null
  biological_growth_result: string | null
  debris_insects_result: string | null
  rodent_bird_result: string | null
  sample_collected: string | null
  coliform: string | null
  ecoli: string | null
  meet_standards: string | null
  match_basis: 'BIN_EXACT'
}

type DomesticWaterContext = {
  summary: {
    planimetric_tank_count: number
    compliance_record_count: number
    self_report_record_count: number
    latest_status: string | null
    latest_reported_dwt_count: number | null
    latest_activity_type: string | null
    latest_activity_year: string | null
    latest_compliance_year: string | null
    violation_record_count: number
    latest_self_report_inspection_date: string | null
    latest_self_report_reporting_year: string | null
    latest_self_report_meet_standards: string | null
  }
  planimetric_tank_features: PlanimetricWaterTankFeature[]
  compliance_history: DwtComplianceRecord[]
  self_report_history: DwtSelfReportRecord[]
}

export type SystemDetailWithDomesticWater = SystemDetail & { domestic_water?: DomesticWaterContext }

const display = (value: string | number | null | undefined) => value == null || value === '' ? '—' : String(value)
const feet = (value: number | null) => value == null ? '—' : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} ft`

function groupSelfReports(records: DwtSelfReportRecord[]) {
  const groups = new Map<string, DwtSelfReportRecord[]>()
  records.forEach(record => {
    const key = record.tank_num?.trim() || 'Not published'
    const group = groups.get(key) ?? []
    group.push(record)
    groups.set(key, group)
  })
  return [...groups.entries()].map(([tank, history]) => ({ tank, history }))
}

function compactSelfReport(report: DwtSelfReportRecord, index: number) {
  return <article className="dwt-history-row" key={`${report.reporting_year ?? 'year'}-${report.inspection_date ?? index}-${index}`}>
    <div><strong>{report.inspection_date ?? report.reporting_year ?? 'Date not published'}</strong><span>{report.inspection_by_firm ?? 'Inspector / firm not published'}</span></div>
    <dl className="identity-grid">
      <div><dt>Sample collected</dt><dd>{display(report.sample_collected)}</dd></div>
      <div><dt>Meets standards</dt><dd>{display(report.meet_standards)}</dd></div>
      <div><dt>Coliform</dt><dd>{display(report.coliform)}</dd></div>
      <div><dt>E. coli</dt><dd>{display(report.ecoli)}</dd></div>
    </dl>
  </article>
}

function complianceCard(record: DwtComplianceRecord, index: number) {
  return <article className="signal-card" key={`${record.activity_year ?? 'year'}-${record.summons_number ?? record.violation_code ?? index}-${index}`}>
    <div className="signal-card-head"><strong>{record.activity_type ?? 'DWT oversight record'}</strong><span>{record.activity_year ?? record.compliance_year ?? 'Year not published'}</span></div>
    <dl className="identity-grid">
      <div><dt>Status</dt><dd>{record.status ?? '—'}</dd></div>
      <div><dt>Reported tank count</dt><dd>{record.number_of_dwt ?? '—'}</dd></div>
      <div><dt>Compliance year</dt><dd>{record.compliance_year ?? '—'}</dd></div>
      <div><dt>Date of occurrence</dt><dd>{record.date_of_occurrence ?? '—'}</dd></div>
      <div><dt>Violation code</dt><dd>{record.violation_code ?? '—'}</dd></div>
      <div><dt>Law section</dt><dd>{record.law_section ?? '—'}</dd></div>
      <div><dt>Summons</dt><dd>{record.summons_number ?? '—'}</dd></div>
    </dl>
    {record.violation_text && <p>{record.violation_text}</p>}
  </article>
}

export function DomesticWaterSection({ detail }: { detail: SystemDetailWithDomesticWater }) {
  const context = detail.domestic_water
  if (!context) return null

  const { summary, planimetric_tank_features: physical, compliance_history: compliance, self_report_history: reports } = context
  const reportGroups = groupSelfReports(reports)
  const latestReports = reportGroups.map(group => ({ ...group, latest: group.history[0], older: group.history.slice(1) })).filter(group => Boolean(group.latest))
  const primaryCompliance = compliance.slice(0, 3)
  const olderCompliance = compliance.slice(3)
  const hasAny = physical.length > 0 || compliance.length > 0 || reports.length > 0

  return <section className="domestic-water-section">
    <h3>Domestic water context</h3>
    {!hasAny ? <>
      <div className="empty-inline">No exact-BIN drinking-water tank polygon, DOHMH oversight record, or self-reported tank inspection was found for this cooling-tower building.</div>
      <p className="microcopy">Absence across these public sources is not evidence that the building has no current domestic-water tank or that no private inspection records exist.</p>
    </> : <>
      <dl className="identity-grid domestic-water-metrics">
        <div><dt>2022 mapped rooftop tanks</dt><dd>{summary.planimetric_tank_count.toLocaleString()}</dd></div>
        <div><dt>Latest DOHMH reported tank count</dt><dd>{summary.latest_reported_dwt_count ?? '—'}</dd></div>
        <div><dt>Latest DOHMH status</dt><dd>{summary.latest_status ?? '—'}</dd></div>
        <div><dt>Latest oversight activity</dt><dd>{summary.latest_activity_type ? `${summary.latest_activity_type}${summary.latest_activity_year ? ` · ${summary.latest_activity_year}` : ''}` : '—'}</dd></div>
        <div><dt>Latest self-report inspection</dt><dd>{summary.latest_self_report_inspection_date ?? '—'}</dd></div>
        <div><dt>Compliance/violation records</dt><dd>{summary.violation_record_count.toLocaleString()}</dd></div>
      </dl>

      {latestReports.length > 0 && <div className="domestic-water-latest">
        <strong>Latest self-reported inspection evidence</strong>
        <p>{latestReports.length.toLocaleString()} tank{latestReports.length === 1 ? '' : 's'} with self-reported history. Latest record per tank is shown first.</p>
        <div className="signal-list dwt-latest-grid">
          {latestReports.map(({ tank, latest, older }, index) => <article className="signal-card dwt-latest-card" key={`${tank}-${latest.reporting_year ?? index}`}>
            <div className="signal-card-head"><strong>Tank {tank}</strong><span>{latest.inspection_date ?? 'Inspection date not published'}</span></div>
            <dl className="identity-grid">
              <div><dt>Reporting year</dt><dd>{latest.reporting_year ?? '—'}</dd></div>
              <div><dt>Inspector / firm</dt><dd>{latest.inspection_by_firm ?? '—'}</dd></div>
              <div><dt>Inspection performed</dt><dd>{display(latest.inspection_performed)}</dd></div>
              <div><dt>Sample collected</dt><dd>{display(latest.sample_collected)}</dd></div>
              <div><dt>Meets standards</dt><dd>{display(latest.meet_standards)}</dd></div>
              <div><dt>Total coliform result</dt><dd>{display(latest.coliform)}</dd></div>
              <div><dt>E. coli result</dt><dd>{display(latest.ecoli)}</dd></div>
              <div><dt>Sediment condition</dt><dd>{display(latest.sediment_result)}</dd></div>
              <div><dt>Biological growth condition</dt><dd>{display(latest.biological_growth_result)}</dd></div>
              <div><dt>Debris / insects condition</dt><dd>{display(latest.debris_insects_result)}</dd></div>
              <div><dt>Rodent / bird condition</dt><dd>{display(latest.rodent_bird_result)}</dd></div>
            </dl>
            {older.length > 0 && <details className="dwt-older-history">
              <summary>View {older.length.toLocaleString()} older inspection{older.length === 1 ? '' : 's'}</summary>
              <div className="dwt-history-list">{older.map(compactSelfReport)}</div>
            </details>}
          </article>)}
        </div>
        <p className="microcopy">Condition and lab values are displayed exactly as published by DOHMH. TowerSignal does not decode abbreviated A/P/N or similar source values unless the source data dictionary explicitly defines them.</p>
      </div>}

      {physical.length > 0 && <details className="roof-building-details">
        <summary>2022 rooftop drinking-water tank polygons · {physical.length.toLocaleString()}</summary>
        <div className="planimetric-feature-list">
          {physical.map((tank, index) => <article className="planimetric-feature" key={tank.global_id}>
            <div className="planimetric-feature-head"><strong>Drinking-water tank footprint {index + 1}</strong><span>BIN {tank.bin}</span></div>
            <dl className="identity-grid">
              <div><dt>Location</dt><dd>Roof level</dd></div>
              <div><dt>Mapped height</dt><dd>{feet(tank.height_ft)}</dd></div>
              <div><dt>Base elevation</dt><dd>{feet(tank.base_elevation_ft)}</dd></div>
              <div><dt>Top elevation</dt><dd>{feet(tank.top_elevation_ft)}</dd></div>
              <div><dt>Source status</dt><dd>{tank.status ?? '—'}</dd></div>
              <div><dt>Observation imagery</dt><dd>{tank.imagery_year}</dd></div>
              <div><dt>Global ID</dt><dd className="mono planimetric-id">{tank.global_id}</dd></div>
              <div><dt>Source ID</dt><dd>{tank.source_id ?? '—'}</dd></div>
            </dl>
          </article>)}
        </div>
      </details>}

      {compliance.length > 0 && <details className="domestic-water-history" open>
        <summary>DOHMH oversight / compliance history · {compliance.length.toLocaleString()} record{compliance.length === 1 ? '' : 's'}</summary>
        <div className="signal-list">{primaryCompliance.map(complianceCard)}</div>
        {olderCompliance.length > 0 && <details className="dwt-older-history dwt-older-oversight">
          <summary>View {olderCompliance.length.toLocaleString()} older oversight record{olderCompliance.length === 1 ? '' : 's'}</summary>
          <div className="signal-list">{olderCompliance.map(complianceCard)}</div>
        </details>}
      </details>}

      <p className="microcopy">Evidence is intentionally separated by source and vintage. The mapped polygons are 2022 rooftop physical observations. DOHMH oversight/compliance records and certified-inspector self-reports are separate regulatory evidence joined by exact BIN. Differences between physical polygon count and later reported tank count are verification cues, not proof of a violation, removal, or unreported installation.</p>
    </>}
    <div className="roof-source-links">
      <a className="planimetric-source-link" href={WATER_TANK_URL} target="_blank" rel="noreferrer">Water-tank polygons ↗</a>
      <a className="planimetric-source-link" href={COMPLIANCE_URL} target="_blank" rel="noreferrer">DOHMH oversight ↗</a>
      <a className="planimetric-source-link" href={SELF_REPORT_URL} target="_blank" rel="noreferrer">Self-reported inspections ↗</a>
    </div>
  </section>
}
