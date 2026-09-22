import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(300_000)

test('225 Broadway exposes client PDF and centers the Account canvas', async ({ page }, testInfo) => {
  if (!isIphoneProject(testInfo)) await page.setViewportSize({ width: 1792, height: 862 })

  await signInForProject(page, testInfo.project.name, '#/account/2000011002')
  await expectAccountDetailHydrated(page)

  const profile = page.locator('.account-profile-page')
  const panel = profile.locator('.detail-panel')
  await expect(panel).toContainText('225 BROADWAY')
  await expect(panel).toContainText('2000011002')
  await expect(panel.getByRole('button', { name: 'Export client PDF', exact: true })).toBeVisible()

  const geometry = await page.evaluate(() => {
    const panel = document.querySelector('.account-profile-page .detail-panel') as HTMLElement
    const toolbar = document.querySelector('.account-profile-page .account-profile-toolbar') as HTMLElement
    const header = panel.querySelector('.detail-header') as HTMLElement
    const panelBox = panel.getBoundingClientRect()
    const toolbarBox = toolbar.getBoundingClientRect()
    const headerBox = header.getBoundingClientRect()
    return {
      viewportWidth: innerWidth,
      panelLeft: panelBox.left,
      panelRight: panelBox.right,
      leftMargin: panelBox.left,
      rightMargin: innerWidth - panelBox.right,
      toolbarLeft: toolbarBox.left,
      toolbarRight: toolbarBox.right,
      headerInset: headerBox.left - panelBox.left,
      panelPaddingLeft: getComputedStyle(panel).paddingLeft,
      toolbarPaddingLeft: getComputedStyle(toolbar).paddingLeft,
      scrollWidth: document.documentElement.scrollWidth,
    }
  })

  if (!isIphoneProject(testInfo)) {
    expect(geometry.viewportWidth).toBe(1792)
    expect(geometry.panelPaddingLeft).toBe('0px')
    expect(geometry.toolbarPaddingLeft).toBe('0px')
    expect(geometry.headerInset).toBeLessThanOrEqual(1)
    expect(Math.abs(geometry.panelLeft - geometry.toolbarLeft)).toBeLessThanOrEqual(1)
    expect(Math.abs(geometry.panelRight - geometry.toolbarRight)).toBeLessThanOrEqual(1)
    expect(geometry.leftMargin).toBeLessThanOrEqual(24)
    expect(geometry.rightMargin).toBeLessThanOrEqual(24)
    expect(Math.abs(geometry.leftMargin - geometry.rightMargin)).toBeLessThanOrEqual(2)
  }
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.viewportWidth + 1)
  await expectContained(page)

  await testInfo.attach(`225-broadway-account-${testInfo.project.name}.png`, {
    body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }),
    contentType: 'image/png',
  })
  await testInfo.attach(`225-broadway-geometry-${testInfo.project.name}.json`, {
    body: JSON.stringify(geometry, null, 2),
    contentType: 'application/json',
  })

  if (!isIphoneProject(testInfo)) {
    await page.emulateMedia({ media: 'print' })
    const report = page.locator('.client-pdf-report')
    await expect(report).toBeVisible()
    await expect(report).toContainText('225 Broadway')
    await expect(report).toContainText('2000011002')
    await expect(report).toContainText('Every key fact has a source.')
    await page.evaluate(() => Promise.all([400,500,600,700,800].map(w => document.fonts.load(`${w} 12px TowerSignalReportInter`))))
    const pdf = await page.pdf({ format: 'Letter', printBackground: true, preferCSSPageSize: true })
    expect(pdf.byteLength).toBeGreaterThan(10_000)
    await testInfo.attach('225-broadway-client-report.pdf', { body: pdf, contentType: 'application/pdf' })
  }
})

test('400 West 61st retains the missing-sample warning after the application-only release', async ({ page }, testInfo) => {
  await signInForProject(page, testInfo.project.name, '#/account/2000014227')
  await expectAccountDetailHydrated(page)

  const summary = page.locator('.account-profile-page .account-decision-summary')
  await expect(summary).toContainText('No public Legionella sample dates reported')
  await expect(summary).toContainText('VERIFY')
  await expect(summary).toContainText(/NYC Health inspection/i)
  await expect(page.getByRole('button', { name: 'Export client PDF', exact: true })).toBeVisible()
  await expectContained(page)
})
