import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, isIphoneProject } from './iphone.helpers'

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
  const firmRows = commercial.locator('.observed-firm-role')
  const emptyFirms = commercial.getByText('No source-named drinking-water inspection/testing firm or relevant DOB applicant business is attached through the current exact BIN/BBL evidence paths.', { exact: true })
  expect((await firmRows.count()) + (await emptyFirms.count())).toBeGreaterThan(0)
  if (await firmRows.count()) {
    const relationshipText = await firmRows.locator('.relationship-chip').allTextContents()
    expect(relationshipText.every(value => ['OBSERVED SERVICE', 'RECORDED ROLE'].includes(value.trim()))).toBe(true)
    const cardsText = await firmRows.allTextContents()
    expect(cardsText.some(value => value.includes('gjm4-k24g') || value.includes('w9ak-ipjd') || value.includes('rbx6-tga4'))).toBe(true)
    expect(cardsText.join(' ')).toMatch(/not proof|not a current/i)
  }

  await expect(commercial.getByRole('heading', { name: 'Explicitly linked procurement', exact: true })).toBeVisible()
  await expect(commercial.getByText('Loading explicitly linked procurement evidence…', { exact: true })).toHaveCount(0, { timeout: 120_000 })
  const procurementRows = commercial.locator('.procurement-evidence-card')
  const procurementEmpty = commercial.getByText('No generated procurement record explicitly links this system through `tower_account_system_ids`. This is not evidence that no public or private contract exists.', { exact: true })
  const procurementUnavailable = commercial.getByText('Procurement evidence unavailable.', { exact: true })
  expect((await procurementRows.count()) + (await procurementEmpty.count()) + (await procurementUnavailable.count())).toBeGreaterThan(0)

  const viewportWidth = page.viewportSize()?.width ?? 0
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
  expect(errors).toEqual([])
})
