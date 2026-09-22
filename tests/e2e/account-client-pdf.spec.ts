import { readFile, stat } from 'node:fs/promises'
import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { isIphoneProject } from './iphone.helpers'

const SYSTEM_ID = '2000015594'

test('account client PDF export downloads a real site-specific PDF without changing account state', async ({ page }, testInfo) => {
  test.skip(isIphoneProject(testInfo), 'PDF download acceptance runs once in desktop Chromium.')
  test.setTimeout(300_000)

  await page.setViewportSize({ width: 1440, height: 1000 })
  await signInForProject(page, testInfo.project.name, `#/account/${SYSTEM_ID}`)
  await expect(page).toHaveURL(new RegExp(`#\\/account\\/${SYSTEM_ID}$`))

  const detail = page.locator('.account-profile-page .detail-panel')
  await expect(detail).toBeVisible()
  await expect(detail.locator('.account-decision-summary')).toBeVisible()

  const exportButton = detail.getByRole('button', { name: 'Export client PDF' })
  await expect(exportButton).toBeEnabled()

  const downloadPromise = page.waitForEvent('download')
  await exportButton.click()
  const download = await downloadPromise

  expect(download.suggestedFilename()).toMatch(
    /^TowerSignal_.+_2000015594_Site_Intelligence_\d{4}-\d{2}-\d{2}\.pdf$/,
  )

  const path = await download.path()
  expect(path).not.toBeNull()
  if (!path) throw new Error('Playwright download path was unavailable')

  const bytes = await readFile(path)
  const fileStat = await stat(path)
  expect(bytes.subarray(0, 5).toString('ascii')).toBe('%PDF-')
  expect(fileStat.size).toBeGreaterThan(20_000)

  await testInfo.attach('account-2000015594-client-report.pdf', {
    path,
    contentType: 'application/pdf',
  })

  await expect(detail.locator('.account-decision-summary')).toBeVisible()
  await expect(detail.locator('.workflow-account-section')).toBeVisible()
  await expect(page.locator('.account-profile-page .error-state')).toHaveCount(0)
})
