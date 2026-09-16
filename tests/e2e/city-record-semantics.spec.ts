import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(180_000)

test('City Record sentinel deadlines are not presented as genuine open deadlines', async ({ page }, testInfo) => {
  if (isIphoneProject(testInfo)) testInfo.setTimeout(300_000)
  await signInForProject(page, testInfo.project.name, '#/opportunities')
  const workspace = page.locator('section.opportunities-page')
  await expect(workspace).toBeVisible()
  await expect(workspace).toContainText('Unverified deadlines')
  const search = workspace.getByLabel('Search procurement')
  await search.fill('20240411118')
  const row = workspace.locator('.procurement-table tbody tr').first()
  await expect(row).toContainText('Deadline unverified')
  await expect(row).toContainText('9999-09-09')
  await expect(row).not.toContainText('due date')
  await expectContained(page)
})
