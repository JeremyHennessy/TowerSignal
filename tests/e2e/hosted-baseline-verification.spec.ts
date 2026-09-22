import { expect, test } from './fixtures'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained } from './iphone.helpers'

test.setTimeout(180_000)

test('hosted System 2000014227 surfaces the missing public Legionella sample warning', async ({ page }, testInfo) => {
  await signInForProject(page, testInfo.project.name, '#/account/2000014227')
  await expectAccountDetailHydrated(page)

  const panel = page.locator('.account-profile-page .detail-panel')
  await expect(panel).toContainText('2000014227')
  await expect(panel).toContainText('400 West 61st Street', { ignoreCase: true })

  const summary = panel.locator('.account-decision-summary')
  await expect(summary).toBeVisible()
  const sampling = summary.locator('.account-decision-evidence-grid article').filter({ hasText: 'Sampling & inspections' })
  await expect(sampling).toBeVisible()
  await expect(sampling).toContainText('VERIFY')
  await expect(sampling).toContainText('No public Legionella sample dates reported')
  await expect(sampling).toContainText(/NYC Health inspection/i)
  await expect(sampling).toContainText(/does not include a usable reported sample date/i)

  await expectContained(page)
  await testInfo.attach(`system-2000014227-${testInfo.project.name}.png`, {
    body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }),
    contentType: 'image/png',
  })
})
