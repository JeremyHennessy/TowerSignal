import { expect, test } from '@playwright/test'

test('diagnostic: WebKit mode switch is observable through plain DOM selectors', async ({ page }) => {
  await page.goto('./', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'TowerSignal' })).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()

  const startedAt = Date.now()
  await page.getByRole('button', { name: 'Changes' }).click()

  const heading = page.locator('.changes-view h2')
  await heading.waitFor({ state: 'visible', timeout: 15_000 })
  const elapsedMs = Date.now() - startedAt
  const headingText = await heading.textContent()
  const leadsWrapper = page.locator('.workspace').locator('..')
  const hiddenAttribute = await leadsWrapper.getAttribute('hidden')
  const mapDisplay = await page.locator('.map-shell').evaluate(element => getComputedStyle(element).display)
  const domState = await page.evaluate(() => ({
    changesViewPresent: Boolean(document.querySelector('.changes-view')),
    changesHeading: document.querySelector('.changes-view h2')?.textContent ?? null,
    bodyWidth: document.body.scrollWidth,
    viewportWidth: window.innerWidth,
  }))

  console.log(JSON.stringify({ elapsedMs, headingText, hiddenAttribute, mapDisplay, domState }))

  expect(headingText).toBe('What changed?')
  expect(hiddenAttribute).not.toBeNull()
  expect(mapDisplay).toBe('none')
  expect(domState.changesViewPresent).toBe(true)
  expect(domState.changesHeading).toBe('What changed?')
  expect(elapsedMs).toBeLessThan(15_000)
})
