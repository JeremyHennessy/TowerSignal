import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

test('hosted domestic-water account shows physical, oversight and compact self-report evidence', async ({ page }, testInfo) => {
  const consoleErrors: string[] = []
  const sameOriginFailures: string[] = []
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('requestfailed', request => {
    try {
      if (new URL(request.url()).origin === new URL(testInfo.project.use.baseURL as string).origin) {
        sameOriginFailures.push(`${request.url()} :: ${request.failure()?.errorText}`)
      }
    } catch { /* ignore non-URL diagnostics */ }
  })

  await signInForProject(page, testInfo.project.name, '#/account/2000010073')
  await expect(page).toHaveURL(/#\/account\/2000010073$/)

  const roof = page.locator('section.planimetric-section')
  const domestic = page.locator('section.domestic-water-section')
  await expect(roof).toBeVisible()
  await expect(domestic).toBeVisible()
  await expect(roof.getByText('5 mapped rooftop drinking-water tank footprints', { exact: true })).toBeVisible()
  expect(await roof.locator('.planimetric-map path[fill="#38bdf8"]').count()).toBeGreaterThanOrEqual(5)

  await expect(domestic.getByRole('heading', { name: 'Domestic water context', exact: true })).toBeVisible()
  await expect(domestic.getByText('Latest self-reported inspection evidence', { exact: true })).toBeVisible()
  expect(await domestic.locator('.dwt-latest-card').count()).toBeGreaterThan(0)
  await expect(domestic.locator('details.domestic-water-history').first().locator(':scope > summary')).toHaveText(/DOHMH oversight \/ compliance history · [1-9]\d* records?/)
  expect(await domestic.locator('details.dwt-older-history').count()).toBeGreaterThan(0)
  await expect(domestic.getByText(/2022 rooftop drinking-water tank polygons · [1-9]\d*/)).toBeVisible()
  await expect(domestic.locator('.signal-card').first()).toBeVisible()
  await expect(domestic.getByRole('link', { name: 'Water-tank polygons ↗', exact: true })).toBeVisible()
  await expect(domestic.getByRole('link', { name: 'DOHMH oversight ↗', exact: true })).toBeVisible()
  await expect(domestic.getByRole('link', { name: 'Self-reported inspections ↗', exact: true })).toBeVisible()

  const viewportWidth = page.viewportSize()?.width ?? 0
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
  const domesticBox = await domestic.boundingBox()
  expect(domesticBox).not.toBeNull()
  expect(domesticBox!.width).toBeLessThanOrEqual(viewportWidth + 0.5)

  const screenshot = await domestic.screenshot()
  await testInfo.attach(`domestic-water-rich-${testInfo.project.name}.png`, { body: screenshot, contentType: 'image/png' })

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})
