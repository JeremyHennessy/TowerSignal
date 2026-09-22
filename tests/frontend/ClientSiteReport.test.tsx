import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { ClientSiteReport } from '../../src/components/ClientSiteReport'
import type { Metadata, SystemDetail, SystemSummary } from '../../src/types/data'

afterEach(cleanup)

const row = {
  system_id: '2000014227',
  address: '400 West 61st Street',
  borough: 'Manhattan',
  zip: '10023',
  priority_score: 18,
  evidence_confidence: 'VERIFY',
  active_equipment: 1,
  signal_types: ['NO_PUBLIC_SAMPLE_DATE'],
  score_components: [{ points: 18, reason: 'no usable public sample date' }],
  recent_confirmed_violation: false,
  primary_signal: 'NO_PUBLIC_SAMPLE_DATE',
  violation_types: [],
} as unknown as SystemSummary

const detail = {
  metadata: {
    generated_at: '2026-09-22T12:00:00Z',
    rules_version: 'rules-test',
    priority_model_version: 'priority-test',
    sources: [{
      dataset_id: 'nyc-health-test',
      name: 'NYC Health Cooling Tower Registry',
      retrieved_at: '2026-09-22T11:00:00Z',
      source_record_count: 1,
      matched_record_count: 1,
      url: 'https://example.test/registry',
    }],
  },
  identity: {
    system_id: '2000014227',
    bin: '1000001',
    bbl: '1000000001',
    active_equipment: 1,
    coordinate_status: 'MISSING',
  },
  building_context: {
    owner_name: 'CLIENT REPORT OWNER',
    building_area_sqft: 150000,
  },
  hpd_registration: null,
  dob_activity_history: [],
  planimetric_building_tower_features: [],
  inspection_history: [{
    inspection_date: '2026-08-14',
    inspection_type: 'ROUTINE',
    violation_count: 0,
    violations: [],
  }],
  oath_case_history: [],
  sample_history: {
    dates: [],
    malformed_values: [],
    sample_count: 0,
    latest_sample_date: null,
    latest_sample_interval_days: null,
  },
  signals: [{
    type: 'NO_PUBLIC_SAMPLE_DATE',
    title: 'No public sample date',
    evidence_confidence: 'VERIFY',
    fact_class: 'COMMERCIAL_SIGNAL',
    reason: 'The current public registration record does not include a usable reported sample date. Verify current operating and sampling status independently.',
  }],
} as unknown as SystemDetail

const metadata = {
  generated_at: '2026-09-22T12:00:00Z',
  rules_version: 'rules-test',
  priority_model_version: 'priority-test',
} as unknown as Metadata

test('client site report carries the current missing-sample warning and site identity', () => {
  render(<ClientSiteReport row={row} detail={detail} metadata={metadata} historyEvents={[]} />)

  expect(screen.getByRole('heading', { name: '400 West 61st Street' })).toBeInTheDocument()
  expect(screen.getAllByText(/2000014227/).length).toBeGreaterThan(0)
  expect(screen.getByText('VERIFY · No public Legionella sample date')).toBeInTheDocument()
  expect(screen.getAllByText(/Verify current operating and sampling status independently/).length).toBeGreaterThan(0)
  expect(screen.getByText('CLIENT REPORT OWNER')).toBeInTheDocument()
})

test('client site report includes source provenance and an explicit interpretation boundary', () => {
  render(<ClientSiteReport row={row} detail={detail} metadata={metadata} historyEvents={[]} />)

  expect(screen.getByText('NYC Health Cooling Tower Registry')).toBeInTheDocument()
  expect(screen.getByText('nyc-health-test')).toBeInTheDocument()
  expect(screen.getByText('Interpretation boundary')).toBeInTheDocument()
  expect(screen.getByText(/not a legal, engineering, health or compliance determination/i)).toBeInTheDocument()
})
