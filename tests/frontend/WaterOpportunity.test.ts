import { describe, expect, it } from 'vitest'
import { filterSystems, initialFilters } from '../../src/components/Filters'
import {
  observedDwtProvider,
  replacementServiceLineMaterials,
  specificBuildingWaterSignalTypes,
  waterEvidenceFamilies,
  type WaterEnrichedSystemSummary,
} from '../../src/domain/waterOpportunity'

function baseRow(systemId: string): WaterEnrichedSystemSummary {
  return {
    system_id: systemId,
    bin: null,
    bbl: null,
    address: `${systemId} MAIN ST`,
    borough: 'Manhattan',
    zip: '10001',
    active_equipment: 1,
    latitude: null,
    longitude: null,
    coordinate_status: 'MISSING',
    latest_sample_date: null,
    days_since_latest_sample: null,
    latest_inspection_date: null,
    latest_inspection_type: null,
    confirmed_violation: false,
    recent_confirmed_violation: false,
    violation_types: [],
    signal_types: [],
    primary_signal: 'NO_CURRENT_SIGNAL',
    evidence_confidence: 'STRONG_SIGNAL',
    priority_score: 0,
    score_components: [],
  }
}

describe('water opportunity evidence', () => {
  it('does not promote ordinary DWT inspection, compliance or mapped-tank presence into a specific opportunity', () => {
    const row: WaterEnrichedSystemSummary = {
      ...baseRow('BROAD-CONTEXT'),
      dwt_market_inspection_count: 4,
      dwt_market_compliance_activity_count: 2,
      dwt_market_violation_count: 0,
    }
    expect(waterEvidenceFamilies(row)).toEqual([])
  })

  it('counts only DWT violation, high-specificity building water and replacement service-line families', () => {
    const row: WaterEnrichedSystemSummary = {
      ...baseRow('MULTI'),
      dwt_violation_record_count: 2,
      nyc_building_water_signal_types: ['BUILDING_WATER_QUALITY', 'PLUMBING_WATER_RELATED'],
      nyc_lead_service_line_materials: ['Lead'],
    }
    expect(waterEvidenceFamilies(row)).toEqual([
      'DWT_VIOLATION',
      'SPECIFIC_BUILDING_WATER',
      'LEAD_SERVICE_LINE_REPLACEMENT',
    ])
  })

  it('keeps generic plumbing, fire-water, leak and LL84-only context outside the specific opportunity filter', () => {
    const generic: WaterEnrichedSystemSummary = {
      ...baseRow('GENERIC'),
      nyc_building_water_signal_count: 5,
      nyc_building_water_signal_types: ['PLUMBING_WATER_RELATED', 'FIRE_WATER_CONTEXT', 'BUILDING_WATER_LEAK'],
      nyc_lead_service_line_materials: ['Non-Lead', 'Unknown - Lead Status Unknown'],
    }
    expect(specificBuildingWaterSignalTypes(generic)).toEqual([])
    expect(replacementServiceLineMaterials(generic)).toEqual([])
    expect(waterEvidenceFamilies(generic)).toEqual([])
    expect(filterSystems([generic], { ...initialFilters, waterOpportunity: 'ANY_EVIDENCE' })).toHaveLength(0)
  })

  it('includes the selected high-specificity building-water categories but excludes broad plumbing categories', () => {
    const row: WaterEnrichedSystemSummary = {
      ...baseRow('SPECIFIC'),
      nyc_building_water_signal_types: [
        'BACKFLOW_PREVENTION',
        'BUILDING_NO_WATER_OR_PRESSURE',
        'BUILDING_WATER_QUALITY',
        'DOMESTIC_WATER_STORAGE',
        'DOMESTIC_WATER_SYSTEM',
        'WATER_PUMP',
        'PLUMBING_WATER_RELATED',
      ],
    }
    expect(specificBuildingWaterSignalTypes(row)).toEqual([
      'BACKFLOW_PREVENTION',
      'BUILDING_NO_WATER_OR_PRESSURE',
      'BUILDING_WATER_QUALITY',
      'DOMESTIC_WATER_STORAGE',
      'DOMESTIC_WATER_SYSTEM',
      'WATER_PUMP',
    ])
  })

  it('requires both provider id and source name before calling a provider observed', () => {
    const missingName: WaterEnrichedSystemSummary = {
      ...baseRow('MISSING-NAME'),
      dwt_market_current_provider_id: 'provider-a',
    }
    const observed: WaterEnrichedSystemSummary = {
      ...baseRow('OBSERVED'),
      dwt_market_current_provider_id: 'provider-a',
      dwt_market_current_provider_raw: 'Example Water Service LLC',
      dwt_market_latest_inspection_date: '2026-03-15',
    }
    expect(observedDwtProvider(missingName)).toBeNull()
    expect(observedDwtProvider(observed)).toEqual({ id: 'provider-a', name: 'Example Water Service LLC', observedDate: '2026-03-15' })
  })

  it('filters selective water evidence separately from cooling-tower Priority Score and provider context', () => {
    const rows: WaterEnrichedSystemSummary[] = [
      { ...baseRow('NONE'), priority_score: 90 },
      { ...baseRow('ONE'), priority_score: 10, dwt_violation_record_count: 1 },
      {
        ...baseRow('MULTI'),
        priority_score: 5,
        dwt_violation_record_count: 1,
        nyc_building_water_signal_types: ['BACKFLOW_PREVENTION'],
      },
      {
        ...baseRow('PROVIDER'),
        priority_score: 1,
        dwt_market_inspection_count: 2,
        dwt_market_current_provider_id: 'provider-a',
        dwt_market_current_provider_raw: 'Example Water Service LLC',
      },
      {
        ...baseRow('SERVICE-LINE'),
        priority_score: 2,
        nyc_lead_service_line_materials: ['Galvanized Service Line Requiring Replacement'],
      },
    ]

    expect(filterSystems(rows, { ...initialFilters, waterOpportunity: 'ANY_EVIDENCE' }).map(row => row.system_id)).toEqual(['ONE', 'MULTI', 'SERVICE-LINE'])
    expect(filterSystems(rows, { ...initialFilters, waterOpportunity: 'MULTI_SOURCE' }).map(row => row.system_id)).toEqual(['MULTI'])
    expect(filterSystems(rows, { ...initialFilters, waterOpportunity: 'OBSERVED_PROVIDER' }).map(row => row.system_id)).toEqual(['PROVIDER'])
    expect(rows.map(row => row.priority_score)).toEqual([90, 10, 5, 1, 2])
  })

  it('includes the observed provider name in general prospect search', () => {
    const rows: WaterEnrichedSystemSummary[] = [{
      ...baseRow('PROVIDER'),
      dwt_market_current_provider_id: 'provider-a',
      dwt_market_current_provider_raw: 'Example Water Service LLC',
    }]
    expect(filterSystems(rows, { ...initialFilters, search: 'water service' })).toHaveLength(1)
  })
})
