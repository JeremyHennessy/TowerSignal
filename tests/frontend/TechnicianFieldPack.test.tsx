import { render, screen, within } from '@testing-library/react'
import { expect, test } from 'vitest'
import { TechnicianFieldPack } from '../../src/components/TechnicianFieldPack'
import type { SystemSummary } from '../../src/types/data'
import type { SystemDetailWithDomesticWater } from '../../src/components/DomesticWaterSection'

const row: SystemSummary = {
  system_id: 'SYS-1',
  bin: '1001',
  bbl: '1000000001',
  address: '10 ALPHA ST',
  borough: 'Manhattan',
  zip: '10001',
  active_equipment: 3,
  latitude: 40.7,
  longitude: -73.9,
  coordinate_status: 'VALID',
  latest_sample_date: '2026-07-01',
  days_since_latest_sample: 66,
  latest_inspection_date: '2026-08-10',
  latest_inspection_type: 'Cycle',
  confirmed_violation: true,
  recent_confirmed_violation: true,
  violation_types: ['Critical'],
  signal_types: ['CONFIRMED_RECENT_VIOLATION', 'POTENTIAL_SAMPLING_GAP'],
  primary_signal: 'CONFIRMED_RECENT_VIOLATION',
  evidence_confidence: 'CONFIRMED',
  priority_score: 92,
  score_components: [{ points: 40, reason: 'confirmed recent violation' }],
  oath_case_count: 1,
  pluto_match: true,
  hpd_contact_count: 1,
}

const polygon = {
  type: 'Polygon' as const,
  coordinates: [[[0, 0], [0, 1], [1, 1], [0, 0]]],
}

const detail: SystemDetailWithDomesticWater = {
  schema_version: '1.0',
  metadata: {
    generated_at: '2026-09-05T00:00:00Z',
    snapshot_date: '2026-09-05',
    sources: [],
    normalized_system_count: 1,
    source_duplicate_registration_rows: 0,
    source_missing_registration_system_id_rows: 0,
    invalid_coordinate_system_count: 0,
    rules_version: 'nyc-2026-05-08',
    priority_model_version: '1.0',
  },
  identity: {
    system_id: 'SYS-1',
    bin: '1001',
    bbl: '1000000001',
    address: '10 ALPHA ST',
    borough: 'Manhattan',
    zip: '10001',
    active_equipment: 3,
    latitude: 40.7,
    longitude: -73.9,
    coordinate_status: 'VALID',
    source_latitude_raw: '40.7',
    source_longitude_raw: '-73.9',
  },
  building_context: null,
  hpd_registration: {
    registration_id: 'REG-1',
    building_id: 'BLDG-1',
    last_registration_date: '2026-06-01',
    source: 'NYC_HPD_MULTIPLE_DWELLING_REGISTRATION',
    contacts: [{
      registration_contact_id: 'CONTACT-1',
      type: 'ManagingAgent',
      description: null,
      corporation_name: 'ALPHA MANAGEMENT LLC',
      person_name: 'JANE DOE',
      title: 'Manager',
      business_address: '123 MAIN ST',
      source: 'NYC_HPD_REGISTRATION_CONTACTS',
    }],
  },
  dob_activity_history: [{
    job_filing_number: 'M0001-I1',
    bbl: '1000000001',
    filing_status: 'Approved',
    job_type: 'Alteration',
    job_description: 'Replace existing cooling tower and associated piping.',
    initial_cost: 100000,
    filing_date: '2026-06-01',
    current_status_date: '2026-08-20',
    first_permit_date: null,
    approved_date: '2026-07-01',
    signoff_date: null,
    activity_date: '2026-08-20',
    mechanical_systems: true,
    boiler_equipment: false,
    explicit_cooling_tower_mention: true,
    commercial_relevance: 'COOLING_TOWER_EXPLICIT',
    owner_business_name: 'ALPHA OWNER LLC',
    applicant_business_name: 'ALPHA ENGINEERING PC',
    source: 'NYC_DOB_NOW_JOB_APPLICATION_FILINGS',
    match_basis: 'BBL_EXACT',
  }],
  planimetric_building_tower_features: [
    { source_id: '1', global_id: 'tower-1', bin: '1001', feature_code: '2120', sub_feature_code: '212000', status: 'Unchanged', geometry: polygon, source: 'NYC_OTI_PLANIMETRICS_COOLING_TOWERS', match_basis: 'BIN_EXACT', feature_identity_basis: 'GLOBALID', imagery_year: 2022 },
    { source_id: '2', global_id: 'tower-2', bin: '1001', feature_code: '2120', sub_feature_code: '212010', status: 'Unchanged', geometry: polygon, source: 'NYC_OTI_PLANIMETRICS_COOLING_TOWERS', match_basis: 'BIN_EXACT', feature_identity_basis: 'GLOBALID', imagery_year: 2022 },
  ],
  building_footprints: [{
    bin: '1001',
    name: null,
    doitt_id: 'D1',
    object_id: null,
    shape_area: 1000,
    base_bbl: '1000000001',
    mappluto_bbl: '1000000001',
    construction_year: 1980,
    feature_code: '2100',
    geometry_source: 'Photogrammetric',
    ground_elevation_ft: 20,
    height_roof_ft: 120,
    last_edited_date: '2026-01-01',
    last_status_type: 'Constructed',
    geometry: polygon,
    source: 'NYC_OTI_BUILDING_FOOTPRINTS',
    match_basis: 'BIN_EXACT',
    feature_identity_basis: 'DOITT_ID',
  }],
  domestic_water: {
    summary: {
      planimetric_tank_count: 1,
      compliance_record_count: 2,
      self_report_record_count: 3,
      latest_status: 'Active',
      latest_reported_dwt_count: 1,
      latest_activity_type: 'Inspection',
      latest_activity_year: '2026',
      latest_compliance_year: '2026',
      violation_record_count: 0,
      latest_self_report_inspection_date: '2026-06-15',
      latest_self_report_reporting_year: '2026',
      latest_self_report_meet_standards: 'Y',
    },
    planimetric_tank_features: [],
    compliance_history: [],
    self_report_history: [],
  },
  sample_history: { source_raw: '07/01/2026', dates: ['2026-07-01'], malformed_values: [], latest_sample_date: '2026-07-01', previous_sample_date: null, latest_sample_interval_days: null, intervals_days: [], sample_count: 1 },
  signals: [],
  inspection_history: [],
  oath_case_history: [],
  scoring: { score: 92, components: [], priority_model_version: '1.0' },
}

test('renders source-backed technician field context and unavailable drawing status', () => {
  render(<TechnicianFieldPack row={row} detail={detail} />)

  expect(screen.getByRole('heading', { name: 'Pre-visit field pack' })).toBeInTheDocument()
  expect(screen.getByText('Priority field review')).toBeInTheDocument()
  expect(screen.getAllByText(/System SYS-1; BIN 1001; BBL 1000000001/).length).toBeGreaterThanOrEqual(2)
  expect(screen.getByText(/3 active units in registration; 2 mapped tower footprints/)).toBeInTheDocument()
  expect(screen.getByText(/1 mapped rooftop drinking-water tank on this BIN/)).toBeInTheDocument()
  expect(screen.getByText(/Registered active equipment count and mapped footprint count differ/)).toBeInTheDocument()

  const sourceDetails = screen.getByText('Public inputs available for this field pack').closest('details')
  expect(sourceDetails).not.toBeNull()
  expect(within(sourceDetails as HTMLElement).getByText('Schematics / mechanical drawings')).toBeInTheDocument()
  expect(within(sourceDetails as HTMLElement).getByText('Not in current public payload')).toBeInTheDocument()
})
