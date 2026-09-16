import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

const details: Array<[string, string]> = [
  ['OATH_PENALTY_CHANGED', '$'],
  ['OATH_BALANCE_CHANGED', '$'],
  ['DOB_JOB_FILED', 'Job'],
  ['LATEST_SAMPLE_CHANGED', 'Public sample date'],
  ['HPD_CONTACT_ADDED', 'Business address'],
]

test.setTimeout(120_000)

test('diagnose exact hosted Monitor detail-state overflow owners on iPhone', async ({ page }, testInfo) => {
  await signInForProject(page, testInfo.project.name, '#/monitor')
  const monitor = page.getByRole('region', { name: 'TowerSignal changes' })
  await expect(monitor.locator('.change-reference-row').first()).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })

  for (const [type, required] of details) {
    await monitor.getByLabel(/^Change type/).selectOption(type)
    const row = monitor.locator('.change-reference-row').first()
    await expect(row).toContainText(required)
    await row.scrollIntoViewIfNeeded()

    const diagnostic = await page.evaluate(() => {
      const vw = window.innerWidth
      const visible = [...document.querySelectorAll('body *')].flatMap(element => {
        const el = element as HTMLElement
        const rect = el.getBoundingClientRect()
        const style = getComputedStyle(el)
        if (rect.width <= 0 || rect.height <= 0 || style.visibility === 'hidden' || style.display === 'none') return []
        const clippedHeader = el.closest('.change-reference-table thead')
        if (clippedHeader) return []
        if (!(rect.right > vw + 2 || rect.left < -2)) return []
        return [{
          tag: el.tagName.toLowerCase(),
          cls: typeof el.className === 'string' ? el.className : '',
          text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 180),
          left: Math.round(rect.left * 10) / 10,
          right: Math.round(rect.right * 10) / 10,
          width: Math.round(rect.width * 10) / 10,
          minWidth: style.minWidth,
          maxWidth: style.maxWidth,
          widthCss: style.width,
          overflowX: style.overflowX,
          whiteSpace: style.whiteSpace,
          display: style.display,
          position: style.position,
        }]
      }).sort((a, b) => b.right - a.right).slice(0, 25)

      return {
        viewport: vw,
        bodyScrollWidth: document.body.scrollWidth,
        htmlScrollWidth: document.documentElement.scrollWidth,
        visible,
      }
    })
    console.log(`DETAIL_OVERFLOW ${type} ${JSON.stringify(diagnostic)}`)
  }
})
