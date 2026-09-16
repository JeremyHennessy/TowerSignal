import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

test.setTimeout(90_000)

test('trace hosted Monitor native select width for LATEST_SAMPLE_CHANGED on iPhone', async ({ page }, testInfo) => {
  await signInForProject(page, testInfo.project.name, '#/monitor')
  const monitor = page.getByRole('region', { name: 'TowerSignal changes' })
  await expect(monitor.locator('.change-reference-row').first()).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  const typeSelect = monitor.getByLabel(/^Change type/)
  await typeSelect.selectOption('LATEST_SAMPLE_CHANGED')
  await expect(monitor.locator('.change-reference-row').first()).toContainText('Public sample date')

  const diagnostic = await page.evaluate(() => {
    const describe = (selector: string) => {
      const el = document.querySelector(selector) as HTMLElement | null
      if (!el) return null
      const rect = el.getBoundingClientRect()
      const style = getComputedStyle(el)
      return {
        selector,
        text: (el instanceof HTMLSelectElement ? el.options[el.selectedIndex]?.text : el.textContent)?.replace(/\s+/g, ' ').trim(),
        left: rect.left,
        right: rect.right,
        width: rect.width,
        clientWidth: el.clientWidth,
        scrollWidth: el.scrollWidth,
        minWidth: style.minWidth,
        maxWidth: style.maxWidth,
        widthCss: style.width,
        boxSizing: style.boxSizing,
        overflowX: style.overflowX,
      }
    }
    return {
      viewport: window.innerWidth,
      bodyScrollWidth: document.body.scrollWidth,
      htmlScrollWidth: document.documentElement.scrollWidth,
      rail: describe('.change-filter-rail'),
      typeLabel: describe('.change-filter-rail label:nth-of-type(3)'),
      typeSelect: describe('.change-filter-rail label:nth-of-type(3) select'),
      allSelects: [...document.querySelectorAll('.change-filter-rail select')].map((el, index) => {
        const node = el as HTMLSelectElement
        const rect = node.getBoundingClientRect()
        const style = getComputedStyle(node)
        return { index, selected: node.options[node.selectedIndex]?.text, left: rect.left, right: rect.right, width: rect.width, clientWidth: node.clientWidth, scrollWidth: node.scrollWidth, widthCss: style.width, minWidth: style.minWidth, maxWidth: style.maxWidth }
      }),
    }
  })
  console.log(`LATEST_SAMPLE_SELECT ${JSON.stringify(diagnostic)}`)
})
