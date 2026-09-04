import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import { TorontoBenchmarkingPage } from '../../src/components/TorontoBenchmarkingPage'

const payload = {
  schema_version: 'toronto-ewrb-market-1.0',
  scope: 'TORONTO_AGGREGATE_ONLY',
  title: 'Energy and water usage of large buildings in Ontario',
  catalogue_url: 'https://data.ontario.ca/dataset/example',
  license: 'Open Government Licence – Ontario',
  retrieved_at: '2026-08-31T00:00:00Z',
  reporting_years: [2022, 2023, 2024],
  latest_reporting_year: 2024,
  toronto_reporting_rows: 7169,
  annual: [
    { year: 2022, reporting_rows: 2445, unique_ewrb_ids: 2445, data_quality_check_yes_rows: 1800, data_quality_check_yes_percent: 73.6, energy_star_numeric_score_rows: 500, published_energy_star_certification_value_rows: 30, top_property_types: [{ property_type: 'Multifamily Housing', rows: 1200 }], top_postal_fsa: [{ fsa: 'M5V', rows: 100 }] },
    { year: 2023, reporting_rows: 2265, unique_ewrb_ids: 2265, data_quality_check_yes_rows: 1700, data_quality_check_yes_percent: 75.1, energy_star_numeric_score_rows: 520, published_energy_star_certification_value_rows: 35, top_property_types: [{ property_type: 'Office', rows: 900 }], top_postal_fsa: [{ fsa: 'M5H', rows: 110 }] },
    { year: 2024, reporting_rows: 2459, unique_ewrb_ids: 2459, data_quality_check_yes_rows: 1900, data_quality_check_yes_percent: 77.3, energy_star_numeric_score_rows: 600, published_energy_star_certification_value_rows: 40, top_property_types: [{ property_type: 'Multifamily Housing', rows: 1400 }], top_postal_fsa: [{ fsa: 'M5V', rows: 130 }] },
  ],
  overall_top_property_types: [{ property_type: 'Multifamily Housing', rows: 4000 }, { property_type: 'Office', rows: 2000 }],
  overall_top_postal_fsa: [{ fsa: 'M5V', rows: 330 }, { fsa: 'M5H', rows: 250 }],
  identity_contract: {
    property_level_links: 0,
    reason: 'The public Ontario EWRB disclosure does not include civic street address or assessment roll number.',
    allowed_use: 'Aggregate Toronto market benchmarking only until an independent lawful address-bearing bridge is available.',
    tower_evidence_effect: 'NONE',
    relationship_effect: 'NONE',
  },
  absence: 'No row is not evidence of absence.',
}

afterEach(() => vi.unstubAllGlobals())

test('renders EWRB only as aggregate Toronto benchmarking with zero property links', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }))
  render(<TorontoBenchmarkingPage />)
  expect(await screen.findByRole('heading', { name: 'Energy & water benchmarking' })).toBeInTheDocument()
  expect(screen.getByText('7,169')).toBeInTheDocument()
  expect(screen.getByText(/does not contain civic street addresses/i)).toBeInTheDocument()
  expect(screen.getByText(/Aggregate Toronto market benchmarking only/i)).toBeInTheDocument()
  expect(screen.getByText('Property-level EWRB links')).toBeInTheDocument()
})

test('uses annual aggregate selection without exposing individual EWRB ids', async () => {
  const user = userEvent.setup()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }))
  render(<TorontoBenchmarkingPage />)
  await screen.findByRole('heading', { name: 'Energy & water benchmarking' })
  await user.click(screen.getByRole('button', { name: '2023' }))
  expect(screen.getByText('2023 selected')).toBeInTheDocument()
  expect(screen.getByText('Office')).toBeInTheDocument()
  expect(screen.getByText('M5H')).toBeInTheDocument()
  expect(screen.queryByText(/EWRB_ID/i)).not.toBeInTheDocument()
})
