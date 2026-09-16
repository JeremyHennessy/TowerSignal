import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained, isIphoneProject } from './iphone.helpers'

const SYSTEM_ID = '2000015594'

async function openAccount(page: import('@playwright/test').Page, projectName: string) {
  await signInForProject(page, projectName, `#/account/${SYSTEM_ID}`)
  await expect(page).toHaveURL(new RegExp(`#\\/account\\/${SYSTEM_ID}$`))
  const detail = page.locator('.account-profile-page .detail-panel')
  await expect(detail).toBeVisible()
  return detail
}

async function assertFullTileCoverage(page: import('@playwright/test').Page) {
  await page.waitForFunction(() => {
    const map = document.querySelector('.planimetric-map') as HTMLElement | null
    if (!map || map.clientWidth < 100) return false
    const tiles = [...map.querySelectorAll('img.leaflet-tile')].filter(tile => {
      const image = tile as HTMLImageElement
      return image.complete && image.naturalWidth > 0
    }) as HTMLImageElement[]
    if (!tiles.length) return false
    const mapBox = map.getBoundingClientRect()
    const boxes = tiles.map(tile => tile.getBoundingClientRect()).filter(box => box.width > 0 && box.height > 0)
    if (!boxes.length) return false
    const left = Math.min(...boxes.map(box => box.left))
    const right = Math.max(...boxes.map(box => box.right))
    return left <= mapBox.left + 8 && right >= mapBox.right - 8
  }, undefined, { timeout: 20_000 })

  const geometry = await page.evaluate(() => {
    const map = document.querySelector('.planimetric-map') as HTMLElement
    const mapBox = map.getBoundingClientRect()
    const boxes = [...map.querySelectorAll('img.leaflet-tile')]
      .map(tile => (tile as HTMLImageElement).getBoundingClientRect())
      .filter(box => box.width > 0 && box.height > 0)
    return {
      mapLeft: mapBox.left,
      mapRight: mapBox.right,
      mapWidth: mapBox.width,
      tileLeft: Math.min(...boxes.map(box => box.left)),
      tileRight: Math.max(...boxes.map(box => box.right)),
      tileCount: boxes.length,
    }
  })
  expect(geometry.mapWidth).toBeGreaterThan(700)
  expect(geometry.tileCount).toBeGreaterThan(0)
  expect(geometry.tileLeft).toBeLessThanOrEqual(geometry.mapLeft + 8)
  expect(geometry.tileRight).toBeGreaterThanOrEqual(geometry.mapRight - 8)
}

test('desktop account detail uses tab-owned content, modern navigation and a full-width Field map', async ({ page }, testInfo) => {
  test.skip(isIphoneProject(testInfo), 'Desktop account acceptance runs in Chromium; iPhone has separate containment coverage.')
  test.setTimeout(300_000)
  await page.setViewportSize({ width: 1440, height: 1000 })
  const detail = await openAccount(page, testInfo.project.name)
  const tabs = detail.locator('.account-mode-tabs')

  await expect(page.locator('.account-jump-control')).toBeHidden()
  await expect(page.locator('.account-section-rail')).toBeHidden()

  const more = page.locator('.reference-more-menu > button').first()
  await more.click()
  const morePanel = page.locator('.reference-more-popover')
  await expect(morePanel).toBeVisible()
  await expect(morePanel).toContainText('More workspaces')
  await expect(morePanel).toContainText('Providers, labs, vendors and project firms')
  await detail.locator('.detail-header').click()
  await expect(morePanel).toBeHidden()

  await expect(detail.locator('.account-decision-summary')).toBeVisible()
  await expect(detail.locator('.workflow-account-section')).toBeVisible()
  await expect(detail.locator('.account-decision-summary')).toContainText('5 registered units · 12 mapped footprints')
  await expect(detail.locator('.account-decision-summary')).toContainText('Latest sample Sep 3, 2026')
  await expect(detail.locator('.account-decision-summary')).toContainText('NYC DEPARTMENT OF SMALL BUSINESS SERVICES')
  await expect(detail.locator('.account-decision-summary')).toContainText('Non-Lead · NYC DEP service line')
  await expect(detail.locator('.account-decision-summary')).toContainText('Failure to report Legionella sample test date within 5 days')
  await testInfo.attach('account-2000015594-summary-desktop.png', { body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }), contentType: 'image/png' })

  await tabs.getByRole('button', { name: /^Sales/ }).click()
  await expect(detail.locator('.sales-precall-pack')).toBeVisible()
  await expect(detail.locator('.account-decision-summary')).toBeHidden()
  await expect(detail.locator('.workflow-account-section')).toBeHidden()
  await testInfo.attach('account-2000015594-sales-desktop.png', { body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }), contentType: 'image/png' })

  await tabs.getByRole('button', { name: /^Field/ }).click()
  await expect(detail.locator('.technician-field-pack')).toBeVisible()
  const map = detail.locator('.planimetric-map')
  await map.scrollIntoViewIfNeeded()
  await assertFullTileCoverage(page)
  await testInfo.attach('account-2000015594-field-desktop.png', { body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }), contentType: 'image/png' })

  await tabs.getByRole('button', { name: /^Evidence/ }).click()
  await expect(detail.getByRole('heading', { name: 'Identity', exact: true })).toBeVisible()
  await expect(detail).toContainText('3,897,404 sq ft')
  await expect(detail).toContainText('Non-Lead')
  await expect(detail.locator('.account-decision-summary')).toBeHidden()
  await testInfo.attach('account-2000015594-evidence-desktop.png', { body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }), contentType: 'image/png' })

  await tabs.getByRole('button', { name: /^History/ }).click()
  await expect(detail.locator('.account-unified-timeline')).toBeVisible()
  await expect(detail.getByRole('heading', { name: 'Historical profile', exact: true })).toBeVisible()
  await expect(detail).toContainText('Jun 11, 2026')
  await expect(detail.locator('.workflow-account-section')).toBeHidden()
  await testInfo.attach('account-2000015594-history-desktop.png', { body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }), contentType: 'image/png' })

  await expectContained(page)
})

test('iPhone account detail keeps the five modes usable without legacy overlays or page overflow', async ({ page }, testInfo) => {
  test.skip(!isIphoneProject(testInfo), 'iPhone-only account containment acceptance.')
  test.setTimeout(300_000)
  const detail = await openAccount(page, testInfo.project.name)
  await expectAccountDetailHydrated(page)
  const tabs = detail.locator('.account-mode-tabs')

  await expect(page.locator('.account-jump-control')).toBeHidden()
  await expect(page.locator('.account-section-rail')).toBeHidden()
  await expect(tabs.getByRole('button')).toHaveCount(5)

  for (const mode of ['Sales', 'Field', 'Evidence', 'History'] as const) {
    await tabs.getByRole('button', { name: new RegExp(`^${mode}`) }).click()
    await expect(tabs.getByRole('button', { name: new RegExp(`^${mode}`) })).toHaveAttribute('aria-pressed', 'true')
    if (mode !== 'Field') await expect(detail.locator('.workflow-account-section')).toBeHidden()
  }

  await tabs.getByRole('button', { name: /^Summary/ }).click()
  await expect(detail.locator('.account-decision-summary')).toBeVisible()
  await expect(detail.locator('.workflow-account-section')).toBeVisible()
  await expect(detail.locator('.account-decision-summary')).toContainText('Non-Lead · NYC DEP service line')
  await expectContained(page)
  await testInfo.attach('account-2000015594-summary-iphone.png', { body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }), contentType: 'image/png' })
})