import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(180_000)

test('official DOB SWO evidence remains a dated snapshot and never a current-status claim', async ({ page }, testInfo) => {
  if (isIphoneProject(testInfo)) testInfo.setTimeout(300_000)
  await signInForProject(page, testInfo.project.name, '#/account/2000015564')
  const section = page.getByRole('region', { name: 'Official DOB stop work order snapshot' })
  await expect(section).toBeVisible()
  await expect(section).toContainText('Historical DOB snapshot · not current status')
  await expect(section).toContainText('Current status available')
  await expect(section).toContainText('No')
  await expect(section).toContainText('does not affect Priority Score')
  await expectContained(page)
})
