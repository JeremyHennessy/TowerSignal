import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { LaborLawDecisionSection } from '../../src/components/LaborLawDecisionSection'

type LaborLawDetail = Parameters<typeof LaborLawDecisionSection>[0]['detail']

const detail = {
  labor_law_published_decisions: {
    records: [{
      decision_id: 'decision-1',
      title: 'Worker v Owner',
      decision_url: 'https://www.nycourts.gov/reporter/example.htm',
      publication_date: '2026-09-16',
      labor_law_sections: ['240(1)', '241(6)'],
      index_numbers: ['123456/2025'],
      case_numbers: [],
      nyscef_document_numbers: [],
      published_subject_address: '350 West 71st Street',
      matched_normalized_address: '350 W 71ST ST',
      property_system_ids: ['SYS-1'],
      match_basis: 'PUBLISHED_DECISION_EXPLICIT_WORKSITE_ADDRESS_EXACT',
      fact_class: 'CONFIRMED_FACT',
      evidence_confidence: 'CONFIRMED',
      building_level_context: true,
      liability_claim: false,
      source: 'NYS_OFFICIAL_REPORTS_PUBLISHED_DECISION',
    }],
    source: {
      name: 'New York Official Reports — Labor Law published decisions',
      url: 'https://www.nycourts.gov/reporter/RSS.shtml',
      source_health_status: 'WARNING',
      source_health_reasons: ['Selected trial-court coverage only'],
      current_filing_status_available: false,
    },
    evidence_boundaries: {
      coverage: 'Official Reports covers appellate decisions and selected trial-court decisions; this is not a comprehensive filing or docket feed.',
      property_identity: 'Exact explicit subject-worksite address only.',
      building_level: 'Building-level context only.',
      liability: 'Presence does not establish current liability.',
      scoring: 'Does not modify Priority Score.',
      absence: 'No match is not evidence of no litigation.',
    },
    generated_at: '2026-09-17T00:00:00Z',
  },
} as unknown as LaborLawDetail

test('renders attached published-decision evidence with explicit source and boundary language', () => {
  render(<LaborLawDecisionSection detail={detail} />)
  expect(screen.getByRole('heading', { name: 'Labor Law published-decision evidence' })).toBeInTheDocument()
  expect(screen.getByText('Published court decision · partial case coverage')).toBeInTheDocument()
  expect(screen.getByText('Worker v Owner')).toBeInTheDocument()
  expect(screen.getByText('350 West 71st Street')).toBeInTheDocument()
  expect(screen.getByText('240(1), 241(6)')).toBeInTheDocument()
  expect(screen.getByText('123456/2025')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Open official published decision ↗' })).toHaveAttribute('href', 'https://www.nycourts.gov/reporter/example.htm')
  expect(screen.getByText(/does not identify an individual cooling tower/i)).toBeInTheDocument()
  expect(screen.getByText(/does not.*affect Priority Score/i)).toBeInTheDocument()
})

test('renders nothing when no exact property-linked published decision exists', () => {
  const empty = {
    labor_law_published_decisions: {
      records: [],
      source: {},
      evidence_boundaries: {},
    },
  } as unknown as LaborLawDetail
  const { container } = render(<LaborLawDecisionSection detail={empty} />)
  expect(container).toBeEmptyDOMElement()
})
