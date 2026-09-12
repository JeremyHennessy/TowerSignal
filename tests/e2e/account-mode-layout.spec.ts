import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, isIphoneProject } from './iphone.helpers'

test.setTimeout(120_000)

test('account mode tabs span the report and switch visible evidence on desktop and iPhone', async ({ page }, testInfo) => {
  const isIphone = isIphoneProject(testInfo)
  if (isIphone) testInfo.setTimeout(240_000)

  await signInForProject(page, testInfo.project.name, '#/account/2000015564')
  await expect(page).toHaveURL(/#\/account\/2000015564$/)
  if (isIphone) await expectAccountDetailHydrated(page)

  const detail = page.locator('.account-profile-page .detail-panel')
  const tabs = detail.locator('.account-mode-tabs')
  await expect(tabs).toBeVisible()
  const detailBox = await detail.boundingBox()
  const tabsBox = await tabs.boundingBox()
  expect(detailBox).not.toBeNull()
  expect(tabsBox).not.toBeNull()
  expect(tabsBox!.width).toBeGreaterThanOrEqual(detailBox!.width * 0.9)

  await tabs.getByRole('button', { name: /^Sales/ }).click()
  await expect(page.locator('.sales-precall-pack')).toBeVisible()
  await expect(page.locator('.technician-field-pack')).toBeHidden()

  await tabs.getByRole('button', { name: /^Field/ }).click()
  await expect(page.locator('.technician-field-pack')).toBeVisible()
  await expect(page.locator('section.planimetric-section')).toBeVisible()
  await expect(page.locator('.sales-precall-pack')).toBeHidden()

  await tabs.getByRole('button', { name: /^Evidence/ }).click()
  await expect(page.getByRole('heading', { name: 'Identity', exact: true })).toBeVisible()
  await expect(page.locator('.technician-field-pack')).toBeHidden()

  await tabs.getByRole('button', { name: /^History/ }).click()
  await expect(page.locator('.account-unified-timeline')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Historical profile', exact: true })).toBeVisible()

  const viewportWidth = page.viewportSize()?.width ?? 0
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
})