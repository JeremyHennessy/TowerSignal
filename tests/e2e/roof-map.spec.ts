import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained, expectDomAttribute, expectDomCount, expectElementContained, expectSectionText, isIphoneProject } from './iphone.helpers'

test.setTimeout(120_000)

test('direct hosted roof link signs in and renders on desktop and iPhone', async ({ page }, testInfo) => {
  const isIphone = isIphoneProject(testInfo)
  if (isIphone) testInfo.setTimeout(240_000)
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

  await signInForProject(page, testInfo.project.name, '#/account/2000015564')
  await expect(page).toHaveURL(/#\/account\/2000015564$/)

  const section = page.locator('section.planimetric-section')
  if (isIphone) {
    await expectAccountDetailHydrated(page)
    await expectDomCount(page, 'section.planimetric-section', 1)
    await expectSectionText(page, testInfo, 'Physical tower location', [
      '1 mapped cooling-tower footprint · 1 building outline',
      '1 roof level · 0 ground level · cooling-tower classification is source-coded by NYC OTI',
      'Roof level',
      'BIN 1089811',
      '212000',
    ])
  } else {
    await expect(section).toBeVisible()
    await section.scrollIntoViewIfNeeded()
    await expect(section.getByRole('heading', { name: 'Physical tower location', exact: true })).toBeVisible()
    await expect(section.getByText('1 mapped cooling-tower footprint · 1 building outline', { exact: true })).toBeVisible()
    await expect(section.getByText('1 roof level · 0 ground level · cooling-tower classification is source-coded by NYC OTI', { exact: true })).toBeVisible()
    await expect(section.getByText('Roof level', { exact: true }).first()).toBeVisible()
    await expect(section.getByText('212000', { exact: true }).first()).toBeVisible()
  }
  const map = section.locator('.planimetric-map')
  if (isIphone) {
    await expectDomCount(page, 'section.planimetric-section .planimetric-map', 1)
    await expectDomAttribute(page, 'section.planimetric-section .planimetric-map', 'aria-label', /BIN 1089811/)
  } else {
    await expect(map).toBeVisible()
    await expect(map).toHaveAttribute('aria-label', /BIN 1089811/)

    await page.waitForFunction(() => [...document.querySelectorAll('.planimetric-map img.leaflet-tile')]
      .some(image => image instanceof HTMLImageElement
        && image.src.includes('orthos.its.ny.gov')
        && image.complete
        && image.naturalWidth > 0), null, { timeout: 30_000 })

    expect(await map.locator('path[stroke="#ffffff"]').count()).toBeGreaterThanOrEqual(1)
    expect(await map.locator('path[fill="#f59e0b"]').count()).toBeGreaterThanOrEqual(1)
    expect(await map.locator('path[fill="#38bdf8"]').count()).toBeGreaterThanOrEqual(1)
    await expect(map.locator('.leaflet-control-layers')).toBeVisible()
    await expect(map.locator('.leaflet-control-scale')).toBeVisible()
    await expect(section.locator('.roof-map-legend')).toBeVisible()
    await expect(section.locator('.roof-legend-water-tank')).toBeVisible()
    await expect(section.getByText('Drinking-water tank footprint', { exact: true })).toBeVisible()
    await expect(section.getByRole('link', { name: 'Tower polygons ↗', exact: true })).toBeVisible()
    await expect(section.getByRole('link', { name: 'Roof/ground code domain ↗', exact: true })).toBeVisible()
    await expect(section.getByRole('link', { name: 'Building footprints ↗', exact: true })).toBeVisible()
    await expect(section.getByRole('link', { name: '2022 NYS orthophoto ↗', exact: true })).toBeVisible()
  }

  const domestic = page.locator('section.domestic-water-section')
  if (isIphone) {
    await expectDomCount(page, 'section.domestic-water-section', 1)
    await expectSectionText(page, testInfo, 'Domestic water context', [
      '2022 rooftop drinking-water tank polygons · 1',
      'Roof level',
      '22.8 ft',
      'Water-tank polygons',
      'DOHMH oversight',
      'Self-reported inspections',
    ])
  } else {
    await expect(domestic).toBeVisible()
    await domestic.scrollIntoViewIfNeeded()
    await expect(domestic.getByRole('heading', { name: 'Domestic water context', exact: true })).toBeVisible()
    const physicalDwtSummary = domestic.getByText('2022 rooftop drinking-water tank polygons · 1', { exact: true })
    await expect(physicalDwtSummary).toBeVisible()
    await physicalDwtSummary.click()
    await expect(domestic.getByText('Roof level', { exact: true }).first()).toBeVisible()
    await expect(domestic.getByText('22.8 ft', { exact: true }).first()).toBeVisible()
    await expect(domestic.getByRole('link', { name: 'Water-tank polygons ↗', exact: true })).toBeVisible()
    await expect(domestic.getByRole('link', { name: 'DOHMH oversight ↗', exact: true })).toBeVisible()
    await expect(domestic.getByRole('link', { name: 'Self-reported inspections ↗', exact: true })).toBeVisible()
  }

  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await page.waitForTimeout(750)
  if (isIphone) {
    await expectDomCount(page, 'section.planimetric-section', 1)
    await expectDomCount(page, 'section.domestic-water-section', 1)
  } else {
    await expect(section).toBeVisible()
    await expect(domestic).toBeVisible()
  }

  await expectContained(page)
  if (isIphone) {
    await expectElementContained(page, 'section.planimetric-section')
    await expectElementContained(page, 'section.domestic-water-section')
  } else {
    const viewportWidth = page.viewportSize()?.width ?? 0
    const sectionBox = await section.boundingBox()
    const domesticBox = await domestic.boundingBox()
    expect(sectionBox).not.toBeNull()
    expect(domesticBox).not.toBeNull()
    expect(sectionBox!.width).toBeLessThanOrEqual(viewportWidth + 0.5)
    expect(domesticBox!.width).toBeLessThanOrEqual(viewportWidth + 0.5)
  }

  if (!isIphone) {
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

    const screenshot = await section.screenshot()
    await testInfo.attach(`roof-map-${testInfo.project.name}.png`, { body: screenshot, contentType: 'image/png' })
    const domesticScreenshot = await domestic.screenshot()
    await testInfo.attach(`domestic-water-${testInfo.project.name}.png`, { body: domesticScreenshot, contentType: 'image/png' })
  }

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})
