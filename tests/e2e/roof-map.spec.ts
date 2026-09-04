import { expect, test } from '@playwright/test'
import { testCredentials } from './auth.helpers'

test('direct hosted roof link signs in and renders on desktop and iPhone', async ({ page }, testInfo) => {
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

  await page.goto('./#/account/2000015564', { waitUntil: 'networkidle' })
  const loginHeading = page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })
  await expect(loginHeading).toBeVisible()
  const credentials = testCredentials(testInfo.project.name)
  await page.getByLabel('Email').fill(credentials.email)
  await page.getByLabel('Password', { exact: true }).fill(credentials.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(loginHeading).toHaveCount(0)
  await expect(page).toHaveURL(/#\/account\/2000015564$/)

  const section = page.locator('section.planimetric-section')
  await expect(section).toBeVisible()
  await expect(section.getByRole('heading', { name: 'Physical tower location', exact: true })).toBeVisible()
  await expect(section.getByText('1 mapped cooling-tower footprint · 1 building outline', { exact: true })).toBeVisible()

  const map = section.locator('.planimetric-map')
  await expect(map).toBeVisible()
  await expect(map).toHaveAttribute('aria-label', /BIN 1089811/)

  await page.waitForFunction(() => [...document.querySelectorAll('.planimetric-map img.leaflet-tile')]
    .some(image => image instanceof HTMLImageElement
      && image.src.includes('orthos.its.ny.gov')
      && image.complete
      && image.naturalWidth > 0), null, { timeout: 30_000 })

  expect(await map.locator('path[stroke="#ffffff"]').count()).toBeGreaterThanOrEqual(1)
  expect(await map.locator('path[fill="#f59e0b"]').count()).toBeGreaterThanOrEqual(1)
  await expect(map.locator('.leaflet-control-layers')).toBeVisible()
  await expect(map.locator('.leaflet-control-scale')).toBeVisible()
  await expect(section.locator('.roof-map-legend')).toBeVisible()
  await expect(section.getByRole('link', { name: 'Tower polygons ↗', exact: true })).toBeVisible()
  await expect(section.getByRole('link', { name: 'Building footprints ↗', exact: true })).toBeVisible()
  await expect(section.getByRole('link', { name: '2022 NYS orthophoto ↗', exact: true })).toBeVisible()

  // Reproduce a Safari focus/foreground check without hard-reloading the page.
  // A missing third-party cookie must not erase the tab that just authenticated.
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await page.waitForTimeout(750)
  await expect(section).toBeVisible()

  const viewportWidth = page.viewportSize()?.width ?? 0
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
  const sectionBox = await section.boundingBox()
  expect(sectionBox).not.toBeNull()
  expect(sectionBox!.width).toBeLessThanOrEqual(viewportWidth + 0.5)

  if (testInfo.project.name === 'desktop-chromium') {
    const layerControl = map.locator('.leaflet-control-layers')
    await layerControl.hover()
    await map.locator('.leaflet-control-layers-base label', { hasText: 'Street map' }).click()
    await page.waitForFunction(() => [...document.querySelectorAll('.planimetric-map img.leaflet-tile')]
      .some(image => image instanceof HTMLImageElement
        && image.src.includes('tile.openstreetmap.org')
        && image.complete
        && image.naturalWidth > 0), null, { timeout: 20_000 })
    await layerControl.hover()
    await map.locator('.leaflet-control-layers-base label', { hasText: '2022 NYS aerial' }).click()
  }

  const screenshot = await section.screenshot()
  await testInfo.attach(`roof-map-${testInfo.project.name}.png`, { body: screenshot, contentType: 'image/png' })

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})
