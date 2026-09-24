import { readFileSync } from 'node:fs'
import { expect, test } from 'vitest'

const dashboard=readFileSync('src/components/AdminCompaniesPage.tsx','utf8')
const today=readFileSync('src/components/AdminSalesTodayPanel.tsx','utf8')

test('admin landing page prioritizes Sales Today and pipeline before research',()=>{
  const salesToday=dashboard.indexOf('<AdminSalesTodayPanel')
  const pipeline=dashboard.indexOf('TowerSignal sales pipeline')
  const directory=dashboard.indexOf('Company family directory')
  const research=dashboard.indexOf('Research, enrichment &amp; account intelligence')
  expect(salesToday).toBeGreaterThan(-1)
  expect(pipeline).toBeGreaterThan(salesToday)
  expect(directory).toBeGreaterThan(pipeline)
  expect(research).toBeGreaterThan(directory)
})

test('Sales Today surfaces actionable commercial exceptions',()=>{
  expect(today).toContain('Overdue')
  expect(today).toContain('Due today')
  expect(today).toContain('Next 7 days')
  expect(today).toContain('Demos')
  expect(today).toContain('Proposal / negotiation')
  expect(today).toContain('No next step')
  expect(today).toContain('untouched 14+ days')
  expect(today).toContain('Recent sales activity')
})
