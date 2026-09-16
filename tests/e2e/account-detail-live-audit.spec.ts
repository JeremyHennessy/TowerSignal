import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained, isIphoneProject } from './iphone.helpers'

const SYSTEM_ID = '2000015594'
const modes = ['Summary', 'Sales', 'Field', 'Evidence', 'History'] as const

test.setTimeout(300_000)

async function visibleHeadings(page: import('@playwright/test').Page) {
  return page.locator('.account-profile-page .detail-panel h3:visible').evaluateAll(nodes =>
    nodes.map(node => node.textContent?.trim()).filter((value): value is string => Boolean(value)))
}

test('audit live account 2000015594 across every detail mode and navigation surface', async ({ page }, testInfo) => {
  const isIphone = isIphoneProject(testInfo)
  const consoleErrors: string[] = []
  const requestFailures: string[] = []
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('requestfailed', request => requestFailures.push(`${request.url()} :: ${request.failure()?.errorText ?? 'failed'}`))

  await signInForProject(page, testInfo.project.name, `#/account/${SYSTEM_ID}`)
  await expect(page).toHaveURL(new RegExp(`#\\/account\\/${SYSTEM_ID}$`))
  if (isIphone) await expectAccountDetailHydrated(page)

  const detail = page.locator('.account-profile-page .detail-panel')
  await expect(detail).toBeVisible()
  await expect(detail.locator('.account-mode-tabs')).toBeVisible()

  const navInventory = await page.evaluate(() => ({
    accountJumpControls: document.querySelectorAll('.account-jump-control').length,
    accountSectionRails: document.querySelectorAll('.account-section-rail').length,
    moreTriggers: document.querySelectorAll('.reference-more-trigger').length,
    modeTabs: document.querySelectorAll('.account-mode-tabs button').length,
  }))
  console.info(`[ACCOUNT_AUDIT_NAV] ${JSON.stringify(navInventory)}`)

  const topMore = page.locator('.reference-more-trigger')
  if (await topMore.count()) {
    await topMore.click()
    const popover = page.locator('.reference-more-popover')
    await expect(popover).toBeVisible()
    await testInfo.attach(`account-${SYSTEM_ID}-top-more-${testInfo.project.name}.png`, {
      body: await page.screenshot({ fullPage: false, animations: 'disabled', scale: 'css' }),
      contentType: 'image/png',
    })
    await topMore.click()
  }

  for (const mode of modes) {
    const button = detail.locator('.account-mode-tabs').getByRole('button', { name: new RegExp(`^${mode}`) })
    await button.click()
    await expect(button).toHaveClass(/active/)
    await page.waitForTimeout(250)

    const headings = await visibleHeadings(page)
    const layout = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      bodyWidth: document.body.scrollWidth,
      documentWidth: document.documentElement.scrollWidth,
      modeTabBox: (() => {
        const node = document.querySelector('.account-mode-tabs')
        const box = node?.getBoundingClientRect()
        return box ? { left: box.left, right: box.right, top: box.top, bottom: box.bottom, width: box.width } : null
      })(),
    }))
    console.info(`[ACCOUNT_AUDIT_MODE] ${JSON.stringify({ project: testInfo.project.name, mode, headings, layout })}`)
    expect(layout.bodyWidth).toBeLessThanOrEqual(layout.viewport + 2)
    expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewport + 2)

    if (mode === 'Field') {
      const planimetric = detail.locator('section.planimetric-section')
      const count = await planimetric.count()
      console.info(`[ACCOUNT_AUDIT_FIELD] ${JSON.stringify({ planimetricSectionCount: count })}`)
      if (count) {
        await expect(planimetric).toBeVisible()
        const map = planimetric.locator('.planimetric-map')
        const mapCount = await map.count()
        if (mapCount) {
          await map.scrollIntoViewIfNeeded()
          await page.waitForTimeout(1200)
          const mapState = await page.evaluate(() => {
            const node = document.querySelector('.planimetric-map') as HTMLElement | null
            if (!node) return null
            const box = node.getBoundingClientRect()
            const tiles = [...node.querySelectorAll('img.leaflet-tile')].map(tile => {
              const image = tile as HTMLImageElement
              const rect = image.getBoundingClientRect()
              return { src: image.src, complete: image.complete, naturalWidth: image.naturalWidth, width: rect.width, height: rect.height }
            })
            const pane = node.querySelector('.leaflet-map-pane') as HTMLElement | null
            return {
              width: box.width,
              height: box.height,
              clientWidth: node.clientWidth,
              clientHeight: node.clientHeight,
              tileCount: tiles.length,
              loadedTileCount: tiles.filter(tile => tile.complete && tile.naturalWidth > 0).length,
              zeroSizeTileCount: tiles.filter(tile => tile.width === 0 || tile.height === 0).length,
              mapPaneTransform: pane ? getComputedStyle(pane).transform : null,
              leafletContainerClasses: node.className,
            }
          })
          console.info(`[ACCOUNT_AUDIT_MAP] ${JSON.stringify({ project: testInfo.project.name, mapState })}`)
        }
      }
    }

    await testInfo.attach(`account-${SYSTEM_ID}-${mode.toLowerCase()}-${testInfo.project.name}.png`, {
      body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }),
      contentType: 'image/png',
    })
  }

  await expectContained(page)
  console.info(`[ACCOUNT_AUDIT_ERRORS] ${JSON.stringify({ project: testInfo.project.name, consoleErrors, requestFailures })}`)
})
