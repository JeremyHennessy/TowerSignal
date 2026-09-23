import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(300_000)

test('400 West 61st scores missing public sampling at 30 while remaining VERIFY', async ({ page }, testInfo) => {
  if (!isIphoneProject(testInfo)) await page.setViewportSize({ width: 1792, height: 862 })

  await signInForProject(page, testInfo.project.name, '#/account/2000014227')
  await expectAccountDetailHydrated(page)

  const profile = page.locator('.account-profile-page')
  const summary = profile.locator('.account-decision-summary')
  await expect(profile.locator('.detail-header')).toContainText('400 West 61st Street', { ignoreCase: true })
  await expect(summary.locator('.account-decision-score strong')).toHaveText('30')
  await expect(summary.locator('.account-decision-score')).toContainText('VERIFY')
  await expect(summary).toContainText('No public Legionella sample dates reported')
  await expect(summary).toContainText(/Absence of a public date is not a violation/i)
  await expect(summary.locator('.account-score-drivers')).toContainText('+30')
  await expect(summary.locator('.account-score-drivers')).toContainText('No usable public sample date')
  await expect(page.getByRole('button', { name: 'Export client PDF', exact: true })).toBeVisible()
  await expectContained(page)

  await testInfo.attach(`400-west-61st-priority-${testInfo.project.name}.png`, {
    body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }),
    contentType: 'image/png',
  })

  if (!isIphoneProject(testInfo)) {
    const report = page.locator('.client-pdf-report')
    await expect(report).toHaveAttribute('data-report-design', 'approved-20260922')
    await expect(report).toHaveAttribute('data-report-system', '2000014227')
    // Exercise the approved export's asset readiness without an operating-system print dialog.
    await page.evaluate(() => { window.print = () => { document.body.dataset.nativePrintCalled = 'true'; window.dispatchEvent(new Event('afterprint')) } })
    await page.getByRole('button', { name: 'Export client PDF', exact: true }).click()
    await expect(report).toHaveAttribute('data-assets-ready', 'true')
    await expect(page.locator('body')).toHaveAttribute('data-native-print-called', 'true')
    await page.emulateMedia({ media: 'print' })
    await expect(report).toBeVisible()
    await expect(report.locator('.tsr-page')).toHaveCount(4)
    await expect(report).toContainText('400 West 61st Street', { ignoreCase: true })
    await expect(report.locator('.tsr-priority > strong')).toHaveText(/^30\s*\/\s*100$/)
    const samplingFinding = report.locator('.tsr-finding').filter({ hasText: 'No public Legionella sample date is shown.' })
    await expect(samplingFinding.locator('.tsr-badge')).toHaveText('VERIFY')
    await expect(samplingFinding).toContainText('Missing public dates do not prove that testing did not occur.')
    const pdf = await page.pdf({ printBackground: true, preferCSSPageSize: true, displayHeaderFooter: false })
    expect(pdf.byteLength).toBeGreaterThan(10_000)
    await testInfo.attach('400-west-61st-priority-30.pdf', { body: pdf, contentType: 'application/pdf' })
  }
})

test('225 Broadway score remains unchanged by the missing-sample rule', async ({ page }, testInfo) => {
  await signInForProject(page, testInfo.project.name, '#/account/2000011002')
  await expectAccountDetailHydrated(page)
  const released = await page.evaluate(async () => {
    const response = await fetch(new URL('data/details/20/2000011002.json', location.href))
    if (!response.ok) throw new Error(`Released account HTTP ${response.status}`)
    return response.json()
  })
  // Live findings age across the model's recency boundaries. The independent
  // generated-score gate validates the rules; this checks the displayed payload
  // and proves the missing-date rule is not applied to an account with dates.
  expect(released.sample_history.dates.length).toBeGreaterThan(0)
  expect(released.scoring.components.some((c: { reason: string }) => /No usable public sample date/i.test(c.reason))).toBe(false)
  await expect(page.locator('.account-decision-summary .account-decision-score strong')).toHaveText(String(released.scoring.score))
  await expectContained(page)
})
