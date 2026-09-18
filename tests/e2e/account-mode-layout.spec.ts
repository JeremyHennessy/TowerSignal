import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained, isIphoneProject } from './iphone.helpers'

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
  const evidence = detail.locator('.account-evidence-workspace')
  await expect(evidence).toBeVisible()
  await expect(evidence.getByRole('heading', { name: 'Account evidence', exact: true })).toBeVisible()
  await expect(evidence.locator(':scope > details.account-evidence-group')).toHaveCount(7)
  await expect(page.locator('.technician-field-pack')).toBeHidden()

  await tabs.getByRole('button', { name: /^History/ }).click()
  await expect(page.locator('.account-unified-timeline')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Historical profile', exact: true })).toBeVisible()
  await expect(evidence).toHaveCount(0)

  const viewportWidth = page.viewportSize()?.width ?? 0
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
})


test('account modes restore from the share URL and all five modes remain visible on iPhone', async ({ page }, testInfo) => {
  const isIphone = isIphoneProject(testInfo)
  if (isIphone) testInfo.setTimeout(300_000)
  await signInForProject(page, testInfo.project.name, '#/account/2000015564?view=evidence')
  if (isIphone) await expectAccountDetailHydrated(page)

  const detail = page.locator('.account-profile-page .detail-panel')
  const tabs = detail.locator('.account-mode-tabs')
  await expect(tabs.getByRole('button', { name: /^Evidence/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(detail.locator('.account-evidence-workspace')).toBeVisible()
  await expect(page).toHaveURL(/#\/account\/2000015564\?view=evidence$/)

  await tabs.getByRole('button', { name: /^History/ }).click()
  await expect(page).toHaveURL(/#\/account\/2000015564\?view=history$/)
  await expect(detail.locator('.account-unified-timeline')).toBeVisible()

  await tabs.getByRole('button', { name: /^Summary/ }).click()
  await expect(page).toHaveURL(/#\/account\/2000015564$/)
  await expect(detail.locator('.account-decision-summary')).toBeVisible()

  if (isIphone) {
    const viewportWidth = page.viewportSize()?.width ?? 0
    const geometry = await tabs.getByRole('button').evaluateAll(buttons => buttons.map(button => {
      const box = button.getBoundingClientRect()
      return { left: box.left, right: box.right, width: box.width }
    }))
    expect(geometry).toHaveLength(5)
    for (const box of geometry) {
      expect(box.width).toBeGreaterThan(0)
      expect(box.left).toBeGreaterThanOrEqual(-0.5)
      expect(box.right).toBeLessThanOrEqual(viewportWidth + 0.5)
    }
    const strip = await tabs.evaluate(element => ({ clientWidth: element.clientWidth, scrollWidth: element.scrollWidth }))
    expect(strip.scrollWidth).toBeLessThanOrEqual(strip.clientWidth + 2)
  }
  await expectContained(page)
})
