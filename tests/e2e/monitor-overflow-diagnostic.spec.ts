import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

const categories = ['All changes', 'High priority', 'Violations', 'OATH activity', 'DOB / permits', 'Sampling', 'Property / contact']

test.setTimeout(180_000)

test('diagnose exact hosted Monitor overflow owners on iPhone', async ({ page }, testInfo) => {
  await signInForProject(page, testInfo.project.name, '#/monitor')
  const monitor = page.getByRole('region', { name: 'TowerSignal changes' })
  await expect(monitor.locator('.change-reference-row').first()).toBeVisible()

  for (const width of [390, 320]) {
    await page.setViewportSize({ width, height: 844 })
    for (const category of categories) {
      const tab = monitor.getByRole('tab', { name: new RegExp('^' + category.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\s*\\d') })
      await tab.click()
      await expect(tab).toHaveAttribute('aria-selected', 'true')
      const row = monitor.getByRole('table', { name: `${category} events`, exact: true }).locator('tbody tr').first()
      await expect(row).toBeVisible()
      await row.scrollIntoViewIfNeeded()

      const diagnostic = await page.evaluate(() => {
        const vw = window.innerWidth
        const all = [...document.querySelectorAll('body *')]
        const offenders = all.map((element) => {
          const el = element as HTMLElement
          const rect = el.getBoundingClientRect()
          const style = getComputedStyle(el)
          return {
            tag: el.tagName.toLowerCase(),
            cls: typeof el.className === 'string' ? el.className : '',
            text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 140),
            left: Math.round(rect.left * 10) / 10,
            right: Math.round(rect.right * 10) / 10,
            width: Math.round(rect.width * 10) / 10,
            scrollWidth: el.scrollWidth,
            clientWidth: el.clientWidth,
            minWidth: style.minWidth,
            widthCss: style.width,
            overflowX: style.overflowX,
            position: style.position,
            display: style.display,
          }
        }).filter(item => item.width > 0 && (item.right > vw + 2 || item.left < -2 || item.scrollWidth > item.clientWidth + 2))
          .sort((a, b) => Math.max(b.right - vw, b.scrollWidth - b.clientWidth) - Math.max(a.right - vw, a.scrollWidth - a.clientWidth))
          .slice(0, 30)
        return {
          viewport: vw,
          bodyScrollWidth: document.body.scrollWidth,
          htmlScrollWidth: document.documentElement.scrollWidth,
          offenders,
        }
      })
      console.log(`MONITOR_OVERFLOW ${width} ${category} ${JSON.stringify(diagnostic)}`)
    }
  }
})
