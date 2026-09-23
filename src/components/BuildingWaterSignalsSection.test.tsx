import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { SystemDetail } from '../types/data'
import { BuildingWaterSignalsSection, orderedDobWaterRows } from './BuildingWaterSignalsSection'

describe('BuildingWaterSignalsSection DOB preview', () => {
  it('orders jobs and permits together before applying the eight-record preview', () => {
    const jobs = Array.from({ length: 8 }, (_, index) => ({
      source_record_id: `JOB-${index}`,
      filing_date: `2025-01-${String(index + 1).padStart(2, '0')}`,
      category: 'PLUMBING_WATER_RELATED',
    }))
    const permits = [{
      source_record_id: 'PERMIT-NEW',
      issued_date: '2026-09-01',
      category: 'PLUMBING_WATER_RELATED',
    }]
    const ordered = orderedDobWaterRows(jobs, permits)
    expect(ordered[0].source_record_id).toBe('PERMIT-NEW')
    expect(ordered.slice(0, 8).some(row => row.source_record_id === 'PERMIT-NEW')).toBe(true)
  })

  it('keeps the eight-card preview compact while exposing every remaining DOB row', () => {
    const jobs = Array.from({ length: 8 }, (_, index) => ({
      source_record_id: `JOB-${index}`,
      filing_date: `2025-01-${String(index + 1).padStart(2, '0')}`,
      category: 'PLUMBING_WATER_RELATED',
      job_description: `Job ${index}`,
      applicant_business_raw: 'Job Co',
      relationship_evidence: 'RECORDED_DOB_ROLE',
      service_assignment_confidence: 'NOT_PROOF_OF_SERVICE_CONTRACT',
    }))
    const permits = [{
      source_record_id: 'PERMIT-NEW',
      issued_date: '2026-09-01',
      category: 'PLUMBING_WATER_RELATED',
      job_description: 'Newest permit',
      applicant_business_raw: 'Permit Co',
      relationship_evidence: 'RECORDED_DOB_ROLE',
      service_assignment_confidence: 'NOT_PROOF_OF_SERVICE_CONTRACT',
    }]
    const detail = {
      nyc_building_water_signals: {
        summary: {
          record_count: 9,
          water_311_building_signal_count: 0,
          hpd_open_water_violation_count: 0,
          dob_water_job_filing_count: 8,
          dob_water_permit_count: 1,
          ll84_water_benchmark_count: 0,
          category_counts: { PLUMBING_WATER_RELATED: 9 },
          latest_observation_date: '2026-09-01',
        },
        water_311_requests: [],
        hpd_open_water_violations: [],
        dob_water_job_filings: jobs,
        dob_water_permits: permits,
        ll84_water_benchmarks: [],
        evidence_boundaries: { property_link: 'Exact.', roles: 'Roles.', ll84: 'LL84.' },
        source: { generated_at: '2026-09-23T00:00:00Z' },
      },
    } as unknown as SystemDetail

    render(<BuildingWaterSignalsSection detail={detail} />)
    expect(screen.getByText('Newest permit')).toBeInTheDocument()
    expect(screen.getByText('View remaining DOB water work records · 1')).toBeInTheDocument()
    expect(screen.getByText('DOB water work roles · 9')).toBeInTheDocument()
  })
})
