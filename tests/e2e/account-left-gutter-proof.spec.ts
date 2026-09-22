import { expect, test } from './fixtures'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(240_000)

test('Account report removes the retired 180px rail gutter without mobile regression', async ({ page }, testInfo) => {
  if (!isIphoneProject(testInfo)) await page.setViewportSize({ width: 1792, height: 862 })

  await signInForProject(page, testInfo.project.name, '#/account/2000015564')
  await expectAccountDetailHydrated(page)

  const report = page.locator('.account-profile-page')
  const panel = report.locator('.detail-panel')
  await expect(panel).toBeVisible()

  const geometry = await page.evaluate(() => {
    const pageEl = document.querySelector('.account-profile-page') as HTMLElement
    const panelEl = document.querySelector('.account-profile-page .detail-panel') as HTMLElement
    const toolbarEl = document.querySelector('.account-profile-page .account-profile-toolbar') as HTMLElement
    const panelStyle = getComputedStyle(panelEl)
    const toolbarStyle = getComputedStyle(toolbarEl)
    const pageBox = pageEl.getBoundingClientRect()
    const panelBox = panelEl.getBoundingClientRect()
    const toolbarBox = toolbarEl.getBoundingClientRect()
    return {
      viewport: { width: innerWidth, height: innerHeight },
      pageLeft: pageBox.left,
      panelLeft: panelBox.left,
      toolbarLeft: toolbarBox.left,
      panelPaddingLeft: panelStyle.paddingLeft,
      toolbarPaddingLeft: toolbarStyle.paddingLeft,
      scrollWidth: document.documentElement.scrollWidth,
    }
  })

  if (!isIphoneProject(testInfo)) {
    expect(geometry.viewport.width).toBe(1792)
    expect(geometry.panelPaddingLeft).toBe('0px')
    expect(geometry.toolbarPaddingLeft).toBe('0px')
    expect(Math.abs(geometry.panelLeft - geometry.toolbarLeft)).toBeLessThanOrEqual(1)
    expect(geometry.panelLeft - geometry.pageLeft).toBeLessThan(40)
  }

  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.viewport.width + 1)
  await expect(page.locator('.account-section-rail')).toBeHidden()
  await expect(page.locator('.account-jump-control')).toBeHidden()
  await expectContained(page)

  await testInfo.attach(`account-gutter-${testInfo.project.name}.png`, {
    body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }),
    contentType: 'image/png',
  })
  await testInfo.attach(`account-gutter-${testInfo.project.name}.json`, {
    body: JSON.stringify(geometry, null, 2),
    contentType: 'application/json',
  })
})
