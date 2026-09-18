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
  const captureMode = async (mode: string) => {
    await page.evaluate(() => window.scrollTo(0, 0))
    await testInfo.attach(`account-${mode.toLowerCase()}-${testInfo.project.name}.png`, {
      body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }),
      contentType: 'image/png',
    })
  }
  await expect(tabs).toBeVisible()
  await captureMode('Summary')
  const detailBox = await detail.boundingBox()
  const tabsBox = await tabs.boundingBox()
  expect(detailBox).not.toBeNull()
  expect(tabsBox).not.toBeNull()
  expect(tabsBox!.width).toBeGreaterThanOrEqual(detailBox!.width * 0.9)

  await tabs.getByRole('button', { name: /^Sales/ }).click()
  await expect(page.locator('.sales-precall-pack')).toBeVisible()
  await expect(page.locator('.technician-field-pack')).toBeHidden()
  await captureMode('Sales')

  await tabs.getByRole('button', { name: /^Field/ }).click()
  await expect(page.locator('.technician-field-pack')).toBeVisible()
  await expect(page.locator('section.planimetric-section')).toBeVisible()
  await expect(page.locator('.sales-precall-pack')).toBeHidden()
  await captureMode('Field')

  await tabs.getByRole('button', { name: /^Evidence/ }).click()
  const evidence = detail.locator('.account-evidence-workspace')
  await expect(evidence).toBeVisible()
  await expect(evidence.getByRole('heading', { name: 'Account evidence', exact: true })).toBeVisible()
  await expect(evidence.locator(':scope > details.account-evidence-group')).toHaveCount(7)
  await expect(page.locator('.technician-field-pack')).toBeHidden()
  await captureMode('Evidence')

  await tabs.getByRole('button', { name: /^History/ }).click()
  await expect(page.locator('.account-unified-timeline')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Historical profile', exact: true })).toBeVisible()
  await expect(evidence).toHaveCount(0)
  await captureMode('History')

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


test('Sales keeps Account mode navigation above the brief and can switch to every other mode', async ({ page }, testInfo) => {
  const isIphone = isIphoneProject(testInfo)
  if (isIphone) testInfo.setTimeout(300_000)
  await signInForProject(page, testInfo.project.name, '#/account/2000015564?view=sales')
  await expectAccountDetailHydrated(page)

  const detail = page.locator('.account-profile-page .detail-panel')
  const tabs = detail.locator('.account-mode-tabs')
  const sales = detail.locator('.sales-precall-pack')

  await expect(tabs.getByRole('button', { name: /^Sales/ })).toHaveAttribute('aria-pressed', 'true')
  await expect(sales).toBeVisible()
  await expect(page).toHaveURL(/#\/account\/2000015564\?view=sales$/)

  const geometry = await page.evaluate(() => {
    const tabs = document.querySelector<HTMLElement>('.account-profile-page .account-mode-tabs')
    const sales = document.querySelector<HTMLElement>('.account-profile-page .sales-precall-pack')
    if (!tabs || !sales) return null
    const tabBox = tabs.getBoundingClientRect()
    const salesBox = sales.getBoundingClientRect()
    return { tabTop: tabBox.top, tabBottom: tabBox.bottom, salesTop: salesBox.top }
  })
  expect(geometry).not.toBeNull()
  expect(geometry!.tabTop).toBeLessThan(geometry!.salesTop)
  expect(geometry!.tabBottom).toBeLessThanOrEqual(geometry!.salesTop + 1)

  const transitions = [
    { name: 'Field', selector: '.technician-field-pack', view: 'field' },
    { name: 'Evidence', selector: '.account-evidence-workspace', view: 'evidence' },
    { name: 'History', selector: '.account-unified-timeline', view: 'history' },
    { name: 'Summary', selector: '.account-decision-summary', view: null },
    { name: 'Sales', selector: '.sales-precall-pack', view: 'sales' },
  ] as const

  for (const transition of transitions) {
    await tabs.getByRole('button', { name: new RegExp(`^${transition.name}`) }).click()
    await expect(detail.locator(transition.selector)).toBeVisible()
    await expect(tabs.getByRole('button', { name: new RegExp(`^${transition.name}`) })).toHaveAttribute('aria-pressed', 'true')
    if (transition.view) await expect(page).toHaveURL(new RegExp(`#\\/account\\/2000015564\\?view=${transition.view}$`))
    else await expect(page).toHaveURL(/#\/account\/2000015564$/)
    await expectContained(page)
  }

  const finalGeometry = await page.evaluate(() => {
    const tabs = document.querySelector<HTMLElement>('.account-profile-page .account-mode-tabs')
    const sales = document.querySelector<HTMLElement>('.account-profile-page .sales-precall-pack')
    if (!tabs || !sales) return null
    const tabBox = tabs.getBoundingClientRect()
    const salesBox = sales.getBoundingClientRect()
    return { tabBottom: tabBox.bottom, salesTop: salesBox.top }
  })
  expect(finalGeometry).not.toBeNull()
  expect(finalGeometry!.tabBottom).toBeLessThanOrEqual(finalGeometry!.salesTop + 1)
})
