import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { BuildingWaterSignalsSection } from '../../src/components/BuildingWaterSignalsSection'
import type { SystemDetail } from '../../src/types/data'

function row(id: string, date: string, category: string) {
  return {
    activity_id: id,
    source_record_id: id,
    category,
    job_description: id,
    applicant_business_raw: 'TEST WATER LLC',
    relationship_evidence: 'RECORDED_DOB_ROLE',
    service_assignment_confidence: 'NOT_PROOF_OF_SERVICE_CONTRACT',
    filing_date: date,
  }
}

describe('BuildingWaterSignalsSection DOB preview', () => {
  it('sorts jobs and permits together before limiting the preview and exposes the remainder', () => {
    const jobs = Array.from({ length: 9 }, (_, i) => row(`JOB-${i + 1}`, `2026-01-${String(i + 1).padStart(2, '0')}`, 'JOB'))
    const permit = { ...row('PERMIT-NEW', '2026-01-10', 'PERMIT'), issued_date: '2026-01-10' }
    const detail = {
      nyc_building_water_signals: {
        summary: {
          record_count: 10,
          water_311_building_signal_count: 0,
          hpd_open_water_violation_count: 0,
          dob_water_job_filing_count: 9,
          dob_water_permit_count: 1,
          ll84_water_benchmark_count: 0,
          dob_applicant_business_count: 1,
          category_counts: { JOB: 9, PERMIT: 1 },
          latest_observation_date: '2026-01-10',
        },
        water_311_requests: [],
        hpd_open_water_violations: [],
        dob_water_job_filings: jobs,
        dob_water_permits: [permit],
        ll84_water_benchmarks: [],
        evidence_boundaries: { property_link: '', roles: '', ll84: '' },
        source: { dataset_ids: [], source_record_count: 10, generated_at: '', query_boundaries: {} },
      },
    } as unknown as SystemDetail

    const { container, getByText } = render(<BuildingWaterSignalsSection detail={detail} />)
    const lists = container.querySelectorAll('.signal-list')
    expect(lists.length).toBe(2)
    const previewText = lists[0].textContent ?? ''
    expect(previewText).toContain('PERMIT-NEW')
    expect(previewText.indexOf('PERMIT-NEW')).toBeLessThan(previewText.indexOf('JOB-9'))
    expect(previewText).not.toContain('JOB-1')
    expect(previewText).not.toContain('JOB-2')
    expect(getByText('Additional DOB water work records · 2')).toBeTruthy()
    expect(lists[1].textContent).toContain('JOB-2')
    expect(lists[1].textContent).toContain('JOB-1')
  })
})
