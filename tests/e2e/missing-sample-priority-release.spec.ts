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
  await expect(summary).toContainText('400 West 61st Street', { ignoreCase: true })
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
    await page.emulateMedia({ media: 'print' })
    const report = page.locator('.client-pdf-report')
    await expect(report).toBeVisible()
    await expect(report).toContainText('400 West 61st Street', { ignoreCase: true })
    await expect(report).toContainText('30/100')
    await expect(report).toContainText('VERIFY · No public Legionella sample date')
    const pdf = await page.pdf({ format: 'A4', printBackground: true, preferCSSPageSize: true })
    expect(pdf.byteLength).toBeGreaterThan(10_000)
    await testInfo.attach('400-west-61st-priority-30.pdf', { body: pdf, contentType: 'application/pdf' })
  }
})

test('225 Broadway score remains unchanged by the missing-sample rule', async ({ page }, testInfo) => {
  await signInForProject(page, testInfo.project.name, '#/account/2000011002')
  await expectAccountDetailHydrated(page)
  await expect(page.locator('.account-decision-summary .account-decision-score strong')).toHaveText('86')
  await expectContained(page)
})
