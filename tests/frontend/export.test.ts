import { expect, test } from 'vitest'
import { leadSummary } from '../../src/utils/export'
import type { Metadata, SystemDetail, SystemSummary } from '../../src/types/data'

const metadata: Metadata = {
  generated_at:'2026-08-22T00:00:00Z', snapshot_date:'2026-08-22', sources:[], normalized_system_count:1,
  source_duplicate_registration_rows:0, source_missing_registration_system_id_rows:0, invalid_coordinate_system_count:0,
  rules_version:'nyc-2026-05-08', priority_model_version:'1.0',
}

const row: SystemSummary = {
  system_id:'SYS-1', bin:'1001', bbl:'1000000001', address:'10 ALPHA ST', borough:'Manhattan', zip:'10001',
  active_equipment:2, latitude:40.7, longitude:-73.9, coordinate_status:'VALID', latest_sample_date:'2026-07-01',
  days_since_latest_sample:52, latest_inspection_date:null, latest_inspection_type:null, confirmed_violation:false,
  recent_confirmed_violation:false, violation_types:[], signal_types:['POTENTIAL_SAMPLING_GAP'], primary_signal:'POTENTIAL_SAMPLING_GAP',
  evidence_confidence:'VERIFY', priority_score:25, score_components:[], oath_case_count:0, pluto_match:true, hpd_contact_count:1,
}

const detail: SystemDetail = {
  schema_version:'1.0', metadata,
  identity:{ system_id:'SYS-1',bin:'1001',bbl:'1000000001',address:'10 ALPHA ST',borough:'Manhattan',zip:'10001',active_equipment:2,latitude:40.7,longitude:-73.9,coordinate_status:'VALID',source_latitude_raw:'40.7',source_longitude_raw:'-73.9' },
  building_context:{ bbl:'1000000001',owner_name:'ALPHA OWNER LLC',land_use:'08',building_class:'D6',lot_area_sqft:10000,building_area_sqft:50000,floors:8,residential_units:40,total_units:42,year_built:1980,year_altered_1:null,year_altered_2:null,source:'NYC_DCP_PLUTO' },
  hpd_registration:{ registration_id:'REG-1',building_id:'BLDG-1',last_registration_date:'2026-06-01',source:'NYC_HPD_MULTIPLE_DWELLING_REGISTRATION',contacts:[{ registration_contact_id:'CONTACT-1',type:'ManagingAgent',description:null,corporation_name:'ALPHA MANAGEMENT LLC',person_name:'JANE DOE',title:'MANAGER',business_address:'123 MAIN ST, NEW YORK NY 10001',source:'NYC_HPD_REGISTRATION_CONTACTS' }] },
  sample_history:{ source_raw:'07/01/2026',dates:['2026-07-01'],malformed_values:[],latest_sample_date:'2026-07-01',previous_sample_date:null,latest_sample_interval_days:null,intervals_days:[],sample_count:1 },
  signals:[], inspection_history:[], oath_case_history:[], scoring:{score:25,components:[],priority_model_version:'1.0'},
}

test('lead summary includes loaded PLUTO and HPD context with sourcing caveat', () => {
  const text = leadSummary(row, metadata, detail)
  expect(text).toContain('PLUTO owner: ALPHA OWNER LLC')
  expect(text).toContain('ManagingAgent: ALPHA MANAGEMENT LLC')
  expect(text).toContain('person JANE DOE')
  expect(text).toContain('business address 123 MAIN ST, NEW YORK NY 10001')
  expect(text).toContain('does not establish who procures or is responsible for cooling-tower service')
})

test('lead summary distinguishes an absent HPD registration match', () => {
  const text = leadSummary(row, metadata, { ...detail, hpd_registration:null })
  expect(text).toContain('HPD registration: No exact BBL match in Multiple Dwelling Registrations')
})
