import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import type { SystemsPayload } from '../../src/types/data'
import type { ProcurementBundle } from '../../src/types/procurement'
import { SourceHealthDirectory, SourceHealthLinks, SourceHealthSource } from '../../src/components/SourceHealthLinks'

afterEach(cleanup)

test('source name is plain text and publisher control has one consistent safe presentation', () => {
  const { container } = render(<SourceHealthSource name="Tower registry" detail="y4fw-iqfr" links={[{ url: 'https://data.cityofnewyork.us/d/y4fw-iqfr' }]} />)
  expect(container.querySelector('strong a')).toBeNull()
  const link = screen.getByRole('link', { name: 'Official source' })
  expect(link).toHaveClass('source-health-link')
  expect(link).toHaveAttribute('target', '_blank')
  expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  expect(link).toHaveAttribute('href', 'https://data.cityofnewyork.us/d/y4fw-iqfr')
})

test('unsafe and duplicate publisher URLs never become clickable controls', () => {
  render(<SourceHealthLinks links={[{ url: 'javascript:alert(1)' }, { url: 'http://example.com' }, { url: 'data:text/html,test' }, { url: 'https://example.com/data' }, { url: 'https://example.com/data' }]} />)
  expect(screen.getAllByRole('link')).toHaveLength(1)
})

test('JSON controls retain exact file names and never escape the published data directory', () => {
  render(<SourceHealthLinks links={[{ artifact: 'property-enforcement.json', label: 'property-enforcement.json' }, { artifact: '../secret.json' }, { artifact: 'history/../../secret.json' }, { artifact: 'https://example.com/foreign.json' }]} />)
  const link = screen.getByRole('link', { name: 'property-enforcement.json' })
  expect(link.getAttribute('href')).toMatch(/\/data\/property-enforcement\.json$/)
  expect(link.getAttribute('title')).toContain('Published TowerSignal dataset')
  expect(screen.getAllByRole('link')).toHaveLength(1)
})

test('missing URLs are explicit and do not claim a successful retrieval', () => {
  render(<SourceHealthLinks links={[{ url: null }, { url: 'not-a-url' }]} />)
  expect(screen.queryByRole('link')).toBeNull()
  expect(screen.getByText('Source link not reported')).toBeInTheDocument()
  expect(screen.queryByText('HEALTHY')).toBeNull()
})

test('directory includes every metadata entry, procurement reference and authoritative dataset, with searchable missing entries', () => {
  const payload = { metadata: { sources: [
    { dataset_id: 'abcd-1234', name: 'Registry', url: 'https://data.cityofnewyork.us/d/abcd-1234' },
    { dataset_id: 'missing-source', name: 'Missing source', url: null },
  ] } } as unknown as SystemsPayload
  const procurement = {
    cityRecord: { source: { dataset_page: 'https://data.cityofnewyork.us/d/city' } },
    checkbook: { source: { documentation_url: 'https://www.checkbooknyc.com/doc', api_url: 'https://www.checkbooknyc.com/api' } },
    nysAuthorities: { source: { api_root: 'https://data.ny.gov' }, source_health: [{ dataset_id: 'ehig-g5x3', dataset_name: 'Authority contracts' }] },
    openBookWater: { source: { source_page: 'https://wwe2.osc.state.ny.us/search', export_url: 'https://wwe2.osc.state.ny.us/export' } },
    nychaWater: null,
  } as unknown as ProcurementBundle
  const before = JSON.stringify({ payload, procurement })
  const { container } = render(<SourceHealthDirectory payload={payload} procurement={procurement} />)
  container.querySelector('details')!.open = true
  expect(container.querySelectorAll('tbody tr')).toHaveLength(8)
  expect(container.querySelector('a[href="https://data.ny.gov/d/ehig-g5x3"]')).not.toBeNull()
  expect(container.querySelector('a[href="https://wwe2.osc.state.ny.us/search"]')).not.toBeNull()
  const search = screen.getByLabelText('Find a publisher or dataset')
  fireEvent.change(search, { target: { value: 'missing' } })
  expect(screen.getByRole('status')).toHaveTextContent('1 of 8')
  expect(screen.getByText('Source link not reported')).toBeInTheDocument()
  fireEvent.change(search, { target: { value: 'nothing-matches' } })
  expect(screen.getByText(/No matching sources/)).toBeInTheDocument()
  fireEvent.change(search, { target: { value: '' } })
  expect(container.querySelectorAll('tbody tr')).toHaveLength(8)
  expect(JSON.stringify({ payload, procurement })).toBe(before)
})
