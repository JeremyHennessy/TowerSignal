import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

test.setTimeout(90_000)

test('prove parent containment for Monitor native select on hosted iPhone', async ({ page }, testInfo) => {
  await signInForProject(page, testInfo.project.name, '#/monitor')
  const monitor = page.getByRole('region', { name: 'TowerSignal changes' })
  await expect(monitor.locator('.change-reference-row').first()).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  const typeSelect = monitor.getByLabel(/^Change type/)
  await typeSelect.selectOption('LATEST_SAMPLE_CHANGED')
  await expect(monitor.locator('.change-reference-row').first()).toContainText('Public sample date')

  const metrics = () => page.evaluate(() => ({
    body: document.body.scrollWidth,
    html: document.documentElement.scrollWidth,
    railClient: (document.querySelector('.change-filter-rail') as HTMLElement).clientWidth,
    railScroll: (document.querySelector('.change-filter-rail') as HTMLElement).scrollWidth,
    labelClient: (document.querySelector('.change-filter-rail label:nth-of-type(3)') as HTMLElement).clientWidth,
    labelScroll: (document.querySelector('.change-filter-rail label:nth-of-type(3)') as HTMLElement).scrollWidth,
    selectClient: (document.querySelector('.change-filter-rail label:nth-of-type(3) select') as HTMLElement).clientWidth,
    selectScroll: (document.querySelector('.change-filter-rail label:nth-of-type(3) select') as HTMLElement).scrollWidth,
  }))

  console.log(`PARENT_CONTAIN_BEFORE ${JSON.stringify(await metrics())}`)
  await page.addStyleTag({ content: `.changes-table-view .change-filter-rail>label{overflow-x:hidden}` })
  const labelHidden = await metrics()
  console.log(`PARENT_CONTAIN_LABEL_HIDDEN ${JSON.stringify(labelHidden)}`)

  await page.addStyleTag({ content: `.changes-table-view .change-filter-rail{overflow-x:hidden}` })
  const railHidden = await metrics()
  console.log(`PARENT_CONTAIN_RAIL_HIDDEN ${JSON.stringify(railHidden)}`)
  expect(railHidden.body).toBeLessThanOrEqual(392)
})
