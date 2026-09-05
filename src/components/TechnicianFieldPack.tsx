import { formatDate } from '../domain/labels'
import type { SystemSummary } from '../types/data'
import type { SystemDetailWithDomesticWater } from './DomesticWaterSection'

type PackTone = 'ready' | 'attention' | 'verify' | 'missing'

type PackItem = {
  label: string
  value: string
  detail: string
  tone: PackTone
}

const display = (value: string | number | null | undefined) => value == null || value === '' ? 'Not published' : String(value)

function plural(value: number, singular: string, pluralLabel = `${singular}s`) {
  return `${value.toLocaleString()} ${value === 1 ? singular : pluralLabel}`
}

function latestDobLabel(detail: SystemDetailWithDomesticWater) {
  const jobs = detail.dob_activity_history ?? []
  if (jobs.length === 0) return 'No exact-BBL DOB job filing match'
  const latest = jobs.find(job => job.activity_date)?.activity_date
  const explicit = jobs.filter(job => job.explicit_cooling_tower_mention).length
  const mechanical = jobs.filter(job => job.mechanical_systems || job.boiler_equipment).length
  return `${plural(jobs.length, 'filing')}${latest ? `, latest ${formatDate(latest)}` : ''}; ${explicit.toLocaleString()} explicit cooling-tower; ${mechanical.toLocaleString()} mechanical/boiler`
}

function sampleLabel(row: SystemSummary) {
  if (!row.latest_sample_date) return 'No public sample date'
  const days = row.days_since_latest_sample == null ? 'age not calculated' : `${row.days_since_latest_sample.toLocaleString()} days old`
  return `${formatDate(row.latest_sample_date)} (${days})`
}

function mainStatus(row: SystemSummary) {
  if (row.recent_confirmed_violation) return { label: 'Priority field review', tone: 'attention' as PackTone }
  if (row.signal_types.includes('POTENTIAL_SAMPLING_GAP') || row.signal_types.includes('NO_PUBLIC_SAMPLE_DATE')) return { label: 'Verify operation status', tone: 'verify' as PackTone }
  return { label: 'Routine field context', tone: 'ready' as PackTone }
}

function sourceItems(row: SystemSummary, detail: SystemDetailWithDomesticWater): PackItem[] {
  const towers = detail.planimetric_building_tower_features ?? []
  const footprints = detail.building_footprints ?? []
  const domestic = detail.domestic_water
  const buildingWater = detail.nyc_building_water_signals
  const contacts = detail.hpd_registration?.contacts ?? []
  const dobJobs = detail.dob_activity_history ?? []
  return [
    {
      label: 'Cooling tower registration',
      value: `${plural(row.active_equipment, 'active equipment unit')}`,
      detail: `System ${row.system_id}; BIN ${display(row.bin)}; BBL ${display(row.bbl)}.`,
      tone: 'ready',
    },
    {
      label: 'Rooftop cooling-tower footprints',
      value: towers.length ? `${plural(towers.length, 'mapped 2022 footprint')}` : 'No exact-BIN footprint match',
      detail: towers.length ? 'NYC OTI planimetric cooling-tower polygons are available below.' : 'Missing planimetric evidence is a field-verification cue, not proof the registered tower is absent.',
      tone: towers.length ? 'ready' : 'verify',
    },
    {
      label: 'Building outline / roof height',
      value: footprints.length ? `${plural(footprints.length, 'building footprint')}` : 'No exact-BIN building footprint',
      detail: footprints.length ? 'Use building outline and roof-height context with the aerial map below.' : 'Confirm access and roof context through field prep or owner-provided material.',
      tone: footprints.length ? 'ready' : 'verify',
    },
    {
      label: 'Domestic water tank context',
      value: domestic ? `${plural(domestic.summary.planimetric_tank_count, 'mapped rooftop tank')}; ${plural(domestic.summary.compliance_record_count + domestic.summary.self_report_record_count, 'DOHMH record')}` : 'No domestic-water payload',
      detail: domestic ? 'Domestic-water tank evidence is kept separate from cooling-tower compliance evidence.' : 'No exact-BIN drinking-water tank evidence is represented for this detail record.',
      tone: domestic ? 'ready' : 'missing',
    },
    {
      label: 'Building-water signals',
      value: buildingWater ? `${plural(buildingWater.summary.record_count, 'exact property signal')}` : 'No exact-BBL/BIN water-signal match',
      detail: buildingWater ? '311, HPD, DOB and LL84 building-water evidence stays separate from compliance scoring and service-provider claims.' : 'No exact source BBL/BIN 311, HPD, DOB or LL84 building-water signal is represented for this detail record.',
      tone: buildingWater ? 'verify' : 'missing',
    },
    {
      label: 'HPD contact / access cues',
      value: contacts.length ? `${plural(contacts.length, 'public contact')}` : 'No public HPD contact match',
      detail: contacts.length ? 'Use as an access/research cue only; it does not prove service responsibility.' : 'Plan to confirm owner, manager, roof access and site contact before dispatch.',
      tone: contacts.length ? 'ready' : 'verify',
    },
    {
      label: 'DOB mechanical project context',
      value: latestDobLabel(detail),
      detail: dobJobs.length ? 'DOB records are exact-BBL project context; only explicit wording is a cooling-tower claim.' : 'No current DOB project context is represented for this building.',
      tone: dobJobs.length ? 'ready' : 'missing',
    },
    {
      label: 'Schematics / mechanical drawings',
      value: 'Not in current public payload',
      detail: 'Do not infer schematics from permits. Add DOB document retrieval or owner-provided drawings as a later source-backed phase.',
      tone: 'missing',
    },
  ]
}

export function TechnicianFieldPack({ row, detail }: { row: SystemSummary; detail: SystemDetailWithDomesticWater }) {
  const towers = detail.planimetric_building_tower_features ?? []
  const footprints = detail.building_footprints ?? []
  const domesticTanks = detail.domestic_water?.summary.planimetric_tank_count ?? 0
  const buildingWaterSignals = detail.nyc_building_water_signals?.summary.record_count ?? 0
  const contacts = detail.hpd_registration?.contacts ?? []
  const roofLevel = towers.filter(feature => feature.sub_feature_code === '212000').length
  const groundLevel = towers.filter(feature => feature.sub_feature_code === '212010').length
  const mappedMismatch = towers.length > 0 && row.active_equipment !== towers.length
  const status = mainStatus(row)
  const items = sourceItems(row, detail)

  return <div className="technician-field-pack" aria-labelledby="technician-field-pack-title">
    <div className="field-pack-header">
      <div>
        <span className="eyebrow">Technician field pack</span>
        <h3 id="technician-field-pack-title">Pre-visit field pack</h3>
        <p>Source-backed dispatch context for access planning, roof verification and service conversation prep.</p>
      </div>
      <span className={`field-pack-status field-pack-status-${status.tone}`}>{status.label}</span>
    </div>

    <div className="field-pack-metrics" aria-label="Field pack metrics">
      <article><small>Latest public sample</small><strong>{sampleLabel(row)}</strong></article>
      <article><small>NYC Health inspection</small><strong>{row.latest_inspection_date ? `${formatDate(row.latest_inspection_date)}${row.confirmed_violation ? ' with violation evidence' : ''}` : 'No joined inspection'}</strong></article>
      <article><small>Physical roof evidence</small><strong>{plural(towers.length, 'tower footprint')}; {plural(footprints.length, 'building outline')}</strong></article>
      <article><small>Building-water signals</small><strong>{buildingWaterSignals ? plural(buildingWaterSignals, 'exact property record') : 'No exact match'}</strong></article>
      <article><small>Contacts and access cues</small><strong>{contacts.length ? plural(contacts.length, 'HPD contact') : 'No public HPD contact'}</strong></article>
    </div>

    <div className="field-pack-checklists">
      <div>
        <h4>Before dispatch</h4>
        <ul>
          <li><strong>Confirm identity:</strong> {display(row.address)}; System {row.system_id}; BIN {display(row.bin)}; BBL {display(row.bbl)}.</li>
          <li><strong>Confirm access:</strong> {contacts.length ? `${contacts[0]?.corporation_name ?? contacts[0]?.person_name ?? 'HPD contact'} is published as a contact cue.` : 'No public access contact is matched; verify owner or manager route before sending a technician.'}</li>
          <li><strong>Review compliance context:</strong> sample {sampleLabel(row)}; {row.oath_case_count ? `${plural(row.oath_case_count, 'exact-matched OATH case')}.` : 'no exact-matched OATH case.'}</li>
          <li><strong>Review building-water context:</strong> {buildingWaterSignals ? `${plural(buildingWaterSignals, 'exact 311/HPD/DOB/LL84 signal')} attached.` : 'no exact-BBL/BIN building-water signal attached.'}</li>
          <li><strong>Check project timing:</strong> {latestDobLabel(detail)}.</li>
        </ul>
      </div>
      <div>
        <h4>On roof / site</h4>
        <ul>
          <li><strong>Verify equipment count:</strong> {row.active_equipment.toLocaleString()} active unit{row.active_equipment === 1 ? '' : 's'} in registration; {plural(towers.length, 'mapped tower footprint')} in the 2022 planimetric layer.</li>
          <li><strong>Confirm tower location:</strong> {roofLevel.toLocaleString()} roof-level footprint{roofLevel === 1 ? '' : 's'}; {groundLevel.toLocaleString()} ground-level footprint{groundLevel === 1 ? '' : 's'}; map evidence is below when available.</li>
          <li><strong>Check adjacent water assets:</strong> {domesticTanks ? `${plural(domesticTanks, 'mapped rooftop drinking-water tank')} on this BIN.` : 'no mapped rooftop drinking-water tank represented for this BIN.'}</li>
          <li><strong>Capture private field notes:</strong> current operator label, controller/service tags, make/model, basin condition, access blockers and photos should stay in workflow notes until source-backed.</li>
        </ul>
      </div>
    </div>

    {mappedMismatch && <div className="field-pack-alert"><strong>Field verification cue:</strong> Registered active equipment count and mapped footprint count differ. This may reflect multi-system buildings, 2022 imagery vintage, source coding or current configuration changes.</div>}

    <details className="field-pack-source-details">
      <summary>Public inputs available for this field pack</summary>
      <div className="field-pack-source-grid">
        {items.map(item => <article key={item.label} className={`field-pack-source field-pack-source-${item.tone}`}>
          <span>{item.label}</span>
          <strong>{item.value}</strong>
          <small>{item.detail}</small>
        </article>)}
      </div>
    </details>

    <p className="microcopy">This pack is a dispatch aid only. It separates public evidence from field observations and does not assert current operating status, service responsibility, safety status, compliance or roof access.</p>
  </div>
}
