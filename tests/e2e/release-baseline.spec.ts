import { expect, test } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { signInForProject } from './auth.helpers'
import { expectContained } from './iphone.helpers'

const routes = [
  ['root', '#/'],
  ['prospect', '#/prospect'],
  ['monitor', '#/monitor'],
  ['map', '#/map'],
  ['opportunities', '#/opportunities'],
  ['companies', '#/companies'],
  ['rmc-company-profile', '#/company/known-firm-4abb52cdffb968606f23'],
  ['water-quality', '#/water-quality'],
  ['portfolios', '#/portfolios'],
  ['source-health', '#/source-health'],
] as const

type CohortPick = {
  label: string
  system_id: string
  address: string | null
  borough: string | null
  priority_score: number
  metrics: Record<string, unknown>
}

type Cohort = {
  generated_at: string | null
  snapshot_date: string | null
  system_count: number
  picks: CohortPick[]
}

async function navigate(page: import('@playwright/test').Page, hash: string) {
  await page.evaluate(nextHash => { window.location.hash = nextHash }, hash)
  await page.waitForLoadState('networkidle').catch(() => undefined)
  await expect(page.locator('body')).not.toContainText('Failed to load TowerSignal data')
  await expect(page.locator('body')).not.toContainText('Application error')
  await expectContained(page)
}

async function capture(page: import('@playwright/test').Page, testInfo: import('@playwright/test').TestInfo, name: string) {
  const directory = path.join('test-results', 'release-baseline', testInfo.project.name)
  await mkdir(directory, { recursive: true })
  const screenshotPath = path.join(directory, `${name}.png`)
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: screenshotPath, fullPage: true, animations: 'disabled', scale: 'css' })
  await testInfo.attach(`${name}-${testInfo.project.name}.png`, { path: screenshotPath, contentType: 'image/png' })
}

async function selectDeployedCohort(page: import('@playwright/test').Page): Promise<Cohort> {
  return page.evaluate(async () => {
    const response = await fetch(new URL('data/systems.json', window.location.href), { cache: 'no-store' })
    if (!response.ok) throw new Error(`systems.json HTTP ${response.status}`)
    const payload = await response.json() as {
      metadata?: { generated_at?: string | null; snapshot_date?: string | null }
      systems?: Array<Record<string, unknown>>
    }
    const systems = (payload.systems ?? []).filter(row => typeof row.system_id === 'string' && row.system_id)
    if (!systems.length) throw new Error('No deployed TowerSignal systems available for release baseline cohort')

    const number = (value: unknown) => Number(value ?? 0)
    const priority = (row: Record<string, unknown>) => number(row.priority_score)
    const used = new Set<string>()
    const picks: Array<{ label: string; row: Record<string, unknown>; metrics: Record<string, unknown> }> = []

    const choose = (
      label: string,
      candidates: Array<Record<string, unknown>>,
      rank: (row: Record<string, unknown>) => number,
      metrics: (row: Record<string, unknown>) => Record<string, unknown>,
    ) => {
      const sorted = [...candidates].sort((a, b) => rank(b) - rank(a) || priority(b) - priority(a) || String(a.system_id).localeCompare(String(b.system_id)))
      const row = sorted.find(candidate => !used.has(String(candidate.system_id))) ?? sorted[0]
      if (!row) throw new Error(`No deployed account satisfies baseline cohort: ${label}`)
      used.add(String(row.system_id))
      picks.push({ label, row, metrics: metrics(row) })
    }

    choose('high-priority', systems, priority, row => ({ priority_score: priority(row), primary_signal: row.primary_signal }))

    choose(
      'no-contact',
      systems.filter(row => number(row.hpd_contact_count) === 0),
      priority,
      row => ({ hpd_contact_count: number(row.hpd_contact_count), priority_score: priority(row), pluto_owner_name: row.pluto_owner_name ?? null }),
    )

    choose(
      'cms-hospital',
      systems.filter(row => Array.isArray(row.cms_institutional_facility_types) && row.cms_institutional_facility_types.includes('HOSPITAL')),
      row => number(row.cms_institutional_facility_count) * 1000 + priority(row),
      row => ({ cms_institutional_facility_count: number(row.cms_institutional_facility_count), cms_institutional_facility_types: row.cms_institutional_facility_types ?? [] }),
    )

    choose(
      'cms-nursing-home',
      systems.filter(row => Array.isArray(row.cms_institutional_facility_types) && row.cms_institutional_facility_types.includes('NURSING_HOME')),
      row => number(row.cms_institutional_facility_count) * 1000 + priority(row),
      row => ({ cms_institutional_facility_count: number(row.cms_institutional_facility_count), cms_institutional_facility_types: row.cms_institutional_facility_types ?? [] }),
    )

    choose(
      'multi-tower',
      systems.filter(row => number(row.active_equipment) > 1 || number(row.planimetric_building_tower_count) > 1),
      row => Math.max(number(row.active_equipment), number(row.planimetric_building_tower_count)) * 1000 + priority(row),
      row => ({ active_equipment: number(row.active_equipment), planimetric_building_tower_count: number(row.planimetric_building_tower_count) }),
    )

    const dwtScore = (row: Record<string, unknown>) =>
      number(row.dwt_planimetric_tank_count) * 10000 +
      number(row.dwt_self_report_record_count) * 100 +
      number(row.dwt_compliance_record_count) * 10 +
      number(row.dwt_violation_record_count)
    choose(
      'dwt-heavy',
      systems.filter(row => dwtScore(row) > 0),
      row => dwtScore(row) * 1000 + priority(row),
      row => ({
        dwt_planimetric_tank_count: number(row.dwt_planimetric_tank_count),
        dwt_self_report_record_count: number(row.dwt_self_report_record_count),
        dwt_compliance_record_count: number(row.dwt_compliance_record_count),
        dwt_violation_record_count: number(row.dwt_violation_record_count),
      }),
    )

    choose(
      'recovered-bbl-outer-borough',
      systems.filter(row => row.bbl_identity_status === 'RECOVERED_EXACT_BIN_MAPPLUTO_BBL' && row.borough && row.borough !== 'Manhattan' && row.bbl),
      priority,
      row => ({ bbl: row.bbl ?? null, bin: row.bin ?? null, bbl_identity_status: row.bbl_identity_status, priority_score: priority(row) }),
    )

    return {
      generated_at: payload.metadata?.generated_at ?? null,
      snapshot_date: payload.metadata?.snapshot_date ?? null,
      system_count: systems.length,
      picks: picks.map(({ label, row, metrics }) => ({
        label,
        system_id: String(row.system_id),
        address: typeof row.address === 'string' ? row.address : null,
        borough: typeof row.borough === 'string' ? row.borough : null,
        priority_score: priority(row),
        metrics,
      })),
    }
  })
}

test.setTimeout(15 * 60_000)

test('retain exact-release route, representative account and Workflow visual baseline', async ({ page }, testInfo) => {
  await signInForProject(page, testInfo.project.name, '#/')

  for (const [name, hash] of routes) {
    await navigate(page, hash)
    if (hash === '#/source-health') await expect(page.getByText('Loading completeness audit…')).toHaveCount(0)
    await capture(page, testInfo, name)
  }

  await navigate(page, '#/prospect')
  const cohort = await selectDeployedCohort(page)
  const cohortDirectory = path.join('test-results', 'release-baseline', testInfo.project.name)
  await mkdir(cohortDirectory, { recursive: true })
  const cohortPath = path.join(cohortDirectory, 'account-cohort.json')
  await writeFile(cohortPath, JSON.stringify(cohort, null, 2), 'utf8')
  await testInfo.attach(`account-cohort-${testInfo.project.name}.json`, { path: cohortPath, contentType: 'application/json' })

  for (const pick of cohort.picks) {
    await navigate(page, `#/account/${encodeURIComponent(pick.system_id)}`)
    const detail = page.locator('aside.detail-panel')
    await expect(detail).toBeVisible()
    await expect(detail).toContainText(pick.system_id)
    await expect(page.locator('body')).not.toContainText('Loading source-backed details…')
    await capture(page, testInfo, `account-${pick.label}-${pick.system_id}`)
  }

  await navigate(page, '#/workflow')
  const workflow = page.locator('section.workflow-workspace-page')
  await expect(workflow).toBeVisible()
  await expect(workflow.getByLabel('Workflow watchlist filter').locator('option[value="arcny-demo-all-associated-sites"]')).toContainText('ArcNY Demo — All Associated Sites (11)')
  await workflow.getByRole('tab', { name: /^Accounts/ }).click()
  await workflow.getByRole('button', { name: 'Map + table', exact: true }).click()

  const accountRow = workflow.locator('.workflow-command-table tbody tr', { hasText: '16 E 39TH ST' }).first()
  await expect(accountRow).toBeVisible()
  await accountRow.scrollIntoViewIfNeeded()
  await accountRow.click()
  const inspector = workflow.locator('.workflow-account-inspector')
  await expect(inspector).toContainText('16 E 39TH ST')
  await capture(page, testInfo, 'workflow-map-table-inspector')

  await workflow.getByRole('button', { name: 'Table', exact: true }).click()
  await expect(inspector).toContainText('16 E 39TH ST')
  await capture(page, testInfo, 'workflow-table-inspector')

  await workflow.getByRole('button', { name: 'Map', exact: true }).click()
  await expect(inspector).toContainText('16 E 39TH ST')
  await capture(page, testInfo, 'workflow-map-inspector')

  await workflow.getByRole('tab', { name: /^Changes/ }).click()
  await capture(page, testInfo, 'workflow-changes')

  await workflow.getByRole('tab', { name: /^Actions/ }).click()
  await capture(page, testInfo, 'workflow-actions')
})
