import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, test } from 'vitest'
import { ClientSiteReport } from '../../src/components/ClientSiteReport'
import { reportModel, reportGeometry, reportMoney, reportDate } from '../../src/utils/accountReportModel'
import type { Metadata, SystemDetail, SystemSummary } from '../../src/types/data'
import fixture from '../fixtures/approved-account-report-2000000407.json'

afterEach(cleanup)
const row = fixture.row as SystemSummary
const detail = fixture.detail as unknown as SystemDetail
const metadata = fixture.metadata as Metadata
const copy = () => structuredClone(detail)

test('approved four-page PDF retains exact example identity, source-backed values and sections', () => {
  const { container } = render(<ClientSiteReport row={row} detail={detail} metadata={metadata} historyEvents={[]} />)
  expect(container.querySelectorAll('.tsr-page')).toHaveLength(4)
  expect(container.querySelector('.tsr-hero h1')).toHaveTextContent('805 Columbus Avenue')
  expect(container.querySelector('.tsr-summary')).toHaveTextContent('Check the one remaining July penalty.')
  expect(container.querySelector('.tsr-priority')).toHaveTextContent('80 / 100')
  expect(container.querySelectorAll('.tsr-case-row')).toHaveLength(3)
  expect(screen.getAllByText('Excluded from the findings score')).toHaveLength(2)
  expect(container.querySelectorAll('.tsr-sources tbody tr')).toHaveLength(7)
  expect(container.querySelectorAll('.tsr-checkbox')).toHaveLength(3)
  expect(container.querySelectorAll('.tsr-qr svg')).toHaveLength(1)
  expect(screen.getAllByText('Columbus Square 805 LLC').length).toBeGreaterThan(0)
  expect(screen.getByText('Western Residential, Inc.')).toBeInTheDocument()
  expect(screen.getByText('What this report does not establish')).toBeInTheDocument()
  expect(container.textContent).toContain('It is not a health or safety score')
  expect(container.textContent).not.toContain('Design mock-up')
  expect(container.querySelector<HTMLAnchorElement>('.tsr-account-link')?.href).toBe('https://jeremyhennessy.github.io/TowerSignal/#/account/2000000407')
})

test('published snapshot date, latest inspection and exact-ticket outcomes drive the report without mutating input', () => {
  const before = JSON.stringify({ row, detail, metadata })
  const m = reportModel(row, detail, metadata)
  expect(m.age).toBe(75)
  expect(m.interval).toBe(94)
  expect(m.balance).toBe(2000)
  expect(m.dismissed).toBe(2)
  expect(m.unpaid[0].ticket_number).toBe('0881344164')
  expect(m.ownerFromHpd).toBe(true)
  expect(m.plutoOwner).toBe('Not shown')
  expect(m.scoreCopy).toBe('This snapshot uses 50 points for findings and 30 for sampling follow-up.')
  expect(JSON.stringify({ row, detail, metadata })).toBe(before)
})

test('missing sample, cases, contacts and geometry remain unknown rather than zero or an all-clear', () => {
  const missing = copy()
  missing.identity.system_id = '2000014227'
  missing.sample_history = { ...missing.sample_history, dates: [], latest_sample_date: null, previous_sample_date: null, sample_count: 0 }
  missing.oath_case_history = []
  missing.inspection_history = []
  missing.building_footprints = []
  missing.planimetric_building_tower_features = []
  missing.building_context = null
  missing.hpd_registration = null
  const other = { ...row, system_id: '2000014227', address: '400 West 61st Street' }
  const m = reportModel(other, missing, metadata)
  expect(m.balance).toBeNull()
  expect(m.age).toBeNull()
  expect(m.owner).toBe('Not shown')
  expect(reportGeometry(missing)).toBeNull()
  const { container } = render(<ClientSiteReport row={other} detail={missing} metadata={metadata} historyEvents={[]} />)
  expect(container.querySelector('.tsr-hero h1')).toHaveTextContent('400 West 61st Street')
  expect(container.textContent).toContain('No public Legionella sample date is shown')
  expect(container.textContent).toContain('Missing public dates do not prove that testing did not occur')
  expect(container.querySelector('.tsr-stats')?.textContent).not.toContain('$0')
  expect(container.querySelector('.tsr-map')?.textContent).toContain('No exact building geometry is shown')
})

test('different-ticket case records and different-building geometry are not attached', () => {
  const changed = copy()
  changed.oath_case_history = changed.oath_case_history!.map(c => ({ ...c, ticket_number: 'unrelated' }))
  changed.building_footprints = changed.building_footprints!.map(b => ({ ...b, bin: 'wrong' }))
  changed.planimetric_building_tower_features = changed.planimetric_building_tower_features!.map(t => ({ ...t, bin: 'wrong' }))
  expect(reportModel(row, changed, metadata).balance).toBeNull()
  expect(reportModel(row, changed, metadata).dismissed).toBe(0)
  expect(reportGeometry(changed)).toBeNull()
  expect(() => reportModel({ ...row, system_id: 'wrong' }, detail, metadata)).toThrow('identity mismatch')
})

test('partial balances do not claim a complete total or remaining penalty; known zero remains zero', () => {
  const changed = copy()
  changed.oath_case_history![1].balance_due = null
  const m = reportModel(row, changed, metadata)
  expect(m.balanceComplete).toBe(false)
  expect(m.penaltyLine).not.toContain('remaining')
  expect(reportMoney(null)).toBe('Not shown')
  expect(reportMoney(0)).toBe('$0')
  expect(reportDate('2026-09-22')).toBe('22 Sep 2026')
})

test('sources link to their actual datasets and the selected account, not a placeholder release JSON', () => {
  const { container } = render(<ClientSiteReport row={row} detail={detail} metadata={metadata} historyEvents={[]} />)
  for (const a of container.querySelectorAll<HTMLAnchorElement>('.tsr-sources a')) expect(a.href).toMatch(/^https:\/\//)
  expect(container.querySelector('[href$="account-release.json"]')).toBeNull()
  expect(reportGeometry(detail)?.towerCount).toBe(1)
  expect(reportGeometry(detail)?.buildingPath).toMatch(/^M/)
})
