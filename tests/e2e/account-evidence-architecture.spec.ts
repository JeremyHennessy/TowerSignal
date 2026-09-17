import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(180_000)

test('Evidence mode presents seven collapsed source groups with explicit relationship boundaries', async ({ page }, testInfo) => {
  const isIphone = isIphoneProject(testInfo)
  if (isIphone) testInfo.setTimeout(300_000)
  const errors: string[] = []
  page.on('pageerror', error => errors.push(error.message))

  await signInForProject(page, testInfo.project.name, '#/account/2000015564')
  if (isIphone) await expectAccountDetailHydrated(page)
  const detail = page.locator('.account-profile-page .detail-panel')
  await detail.locator('.account-mode-tabs').getByRole('button', { name: /^Evidence/ }).click()

  const workspace = detail.locator('.account-evidence-workspace')
  await expect(workspace).toBeVisible()
  const groups = workspace.locator(':scope > details.account-evidence-group')
  await expect(groups).toHaveCount(7)
  const expectedTitles = [
    'Compliance', 'Property / Ownership', 'Project Activity', 'Domestic Water',
    'Institutional / Infrastructure', 'Procurement / Commercial', 'Historical Evidence',
  ]
  for (const title of expectedTitles) await expect(groups.locator('summary').filter({ hasText: title })).toHaveCount(1)
  for (let index = 0; index < 7; index += 1) expect(await groups.nth(index).getAttribute('open')).toBeNull()

  const compliance = groups.filter({ hasText: 'Compliance' }).first()
  await compliance.locator(':scope > summary').click()
  await expect(compliance).toContainText('remain distinct evidence classes')
  await expect(compliance).toContainText('dated official issued/rescinded SWO snapshot')

  const commercial = groups.filter({ hasText: 'Procurement / Commercial' }).first()
  await commercial.locator(':scope > summary').click()
  await expect(commercial.getByRole('heading', { name: 'Observed firms & roles', exact: true })).toBeVisible()
  await expect(commercial.getByText('Loading source-observed and procurement-linked firm roles…', { exact: true })).toHaveCount(0, { timeout: 120_000 })
  await expect(commercial.getByText('Loading explicitly linked procurement firm roles…', { exact: true })).toHaveCount(0, { timeout: 120_000 })
  const firmRows = commercial.locator('.observed-firm-role')
  const emptyFirms = commercial.getByText('No source-named service/recorded role or explicitly account-linked procurement vendor is represented in the current evidence. This is not evidence that no firm relationship exists.', { exact: true })
  const procurementFirmUnavailable = commercial.getByText('Procurement-linked firm roles unavailable.', { exact: true })
  expect((await firmRows.count()) + (await emptyFirms.count()) + (await procurementFirmUnavailable.count())).toBeGreaterThan(0)
  if (await firmRows.count()) {
    const relationshipText = await firmRows.locator('.relationship-chip').allTextContents()
    expect(relationshipText.every(value => ['OBSERVED SERVICE', 'RECORDED ROLE', 'CONTRACT AWARD EVIDENCE'].includes(value.trim()))).toBe(true)
    const cardsText = await firmRows.allTextContents()
    expect(cardsText.join(' ')).toMatch(/exact|explicit|not proof|not a current|account link/i)
  }

  await expect(commercial.getByRole('heading', { name: 'Explicitly linked procurement', exact: true })).toBeVisible()
  await expect(commercial.getByText('Loading explicitly linked procurement evidence…', { exact: true })).toHaveCount(0, { timeout: 120_000 })
  const procurementRows = commercial.locator('.procurement-evidence-card')
  const procurementEmpty = commercial.getByText('No generated procurement record explicitly links this system through `tower_account_system_ids`. This is not evidence that no public or private contract exists.', { exact: true })
  const procurementUnavailable = commercial.getByText('Procurement evidence unavailable.', { exact: true })
  expect((await procurementRows.count()) + (await procurementEmpty.count()) + (await procurementUnavailable.count())).toBeGreaterThan(0)

  await expectContained(page)
  expect(errors).toEqual([])
})

test('Observed firms & roles surfaces a procurement vendor only from an explicit TowerSignal account link', async ({ page }, testInfo) => {
  const isIphone = isIphoneProject(testInfo)
  if (isIphone) testInfo.setTimeout(300_000)
  const baseURL = testInfo.project.use.baseURL as string
  const dataFiles = [
    ['procurement-city-record.json', 'notices'],
    ['procurement-checkbook.json', 'contracts'],
    ['procurement-nys-authorities.json', 'contracts'],
    ['procurement-openbook-water.json', 'contracts'],
    ['procurement-nycha-water.json', 'records'],
  ] as const

  let candidate: { systemId: string; vendor: string } | null = null
  for (const [file, collection] of dataFiles) {
    const response = await page.request.get(new URL(`data/${file}`, baseURL).toString())
    if (!response.ok()) continue
    const payload = await response.json() as Record<string, unknown>
    const records = Array.isArray(payload[collection]) ? payload[collection] as Array<Record<string, unknown>> : []
    const record = records.find(row => {
      const ids = Array.isArray(row.tower_account_system_ids) ? row.tower_account_system_ids : []
      return typeof row.vendor_raw === 'string' && row.vendor_raw.trim().length > 0
        && (row.tower_link_confidence === 'CONFIRMED' || row.tower_link_confidence === 'STRONG')
        && ids.some(value => typeof value === 'string' && value.length > 0)
    })
    const ids = record && Array.isArray(record.tower_account_system_ids) ? record.tower_account_system_ids : []
    const systemId = ids.find(value => typeof value === 'string' && value.length > 0)
    if (record && typeof systemId === 'string' && typeof record.vendor_raw === 'string') {
      candidate = { systemId, vendor: record.vendor_raw.trim() }
      break
    }
  }

  test.skip(!candidate, 'Current generated procurement datasets contain no vendor record with an explicit CONFIRMED/STRONG tower_account_system_ids link')
  await signInForProject(page, testInfo.project.name, `#/account/${encodeURIComponent(candidate!.systemId)}`)
  if (isIphone) await expectAccountDetailHydrated(page)
  const detail = page.locator('.account-profile-page .detail-panel')
  await detail.locator('.account-mode-tabs').getByRole('button', { name: /^Evidence/ }).click()
  const commercial = detail.locator('.account-evidence-group').filter({ hasText: 'Procurement / Commercial' }).first()
  await commercial.locator(':scope > summary').click()
  await expect(commercial.getByText('Loading explicitly linked procurement firm roles…', { exact: true })).toHaveCount(0, { timeout: 120_000 })

  const vendorRow = commercial.locator('.observed-firm-role').filter({ hasText: candidate!.vendor }).first()
  await expect(vendorRow).toBeVisible()
  await expect(vendorRow.locator('.relationship-chip')).toHaveText('CONTRACT AWARD EVIDENCE')
  await expect(vendorRow).toContainText('SYSTEM ID EXPLICIT')
  await expect(vendorRow).toContainText('no relationship is created from name or mailing-address similarity')
  await expectContained(page)
})
