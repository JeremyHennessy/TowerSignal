import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

test.setTimeout(90_000)

test('prove Monitor native-select containment rule on hosted iPhone', async ({ page }, testInfo) => {
  await signInForProject(page, testInfo.project.name, '#/monitor')
  const monitor = page.getByRole('region', { name: 'TowerSignal changes' })
  await expect(monitor.locator('.change-reference-row').first()).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  const typeSelect = monitor.getByLabel(/^Change type/)
  await typeSelect.selectOption('LATEST_SAMPLE_CHANGED')
  await expect(monitor.locator('.change-reference-row').first()).toContainText('Public sample date')

  const before = await page.evaluate(() => ({ body: document.body.scrollWidth, html: document.documentElement.scrollWidth,
    rail: (document.querySelector('.change-filter-rail') as HTMLElement).scrollWidth,
    select: (document.querySelector('.change-filter-rail label:nth-of-type(3) select') as HTMLElement).scrollWidth }))
  console.log(`MONITOR_CONTAIN_BEFORE ${JSON.stringify(before)}`)

  await page.addStyleTag({ content: `.changes-table-view .change-filter-rail :is(select,input[type="date"],input[type="number"]){min-width:0;width:100%;max-width:100%;box-sizing:border-box}` })
  const widthOnly = await page.evaluate(() => ({ body: document.body.scrollWidth, html: document.documentElement.scrollWidth,
    rail: (document.querySelector('.change-filter-rail') as HTMLElement).scrollWidth,
    select: (document.querySelector('.change-filter-rail label:nth-of-type(3) select') as HTMLElement).scrollWidth }))
  console.log(`MONITOR_CONTAIN_WIDTH_ONLY ${JSON.stringify(widthOnly)}`)

  await page.addStyleTag({ content: `.changes-table-view .change-filter-rail :is(select,input[type="date"],input[type="number"]){overflow:hidden}` })
  const clippedNative = await page.evaluate(() => ({ body: document.body.scrollWidth, html: document.documentElement.scrollWidth,
    rail: (document.querySelector('.change-filter-rail') as HTMLElement).scrollWidth,
    select: (document.querySelector('.change-filter-rail label:nth-of-type(3) select') as HTMLElement).scrollWidth }))
  console.log(`MONITOR_CONTAIN_OVERFLOW_HIDDEN ${JSON.stringify(clippedNative)}`)
  expect(clippedNative.body).toBeLessThanOrEqual(392)
})
