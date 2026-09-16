import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

test.setTimeout(90_000)

test('trace intrinsic width for hosted LATEST_SAMPLE_CHANGED on iPhone', async ({ page }, testInfo) => {
  await signInForProject(page, testInfo.project.name, '#/monitor')
  const monitor = page.getByRole('region', { name: 'TowerSignal changes' })
  await expect(monitor.locator('.change-reference-row').first()).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await monitor.getByLabel(/^Change type/).selectOption('LATEST_SAMPLE_CHANGED')
  const row = monitor.locator('.change-reference-row').first()
  await expect(row).toContainText('Public sample date')
  await row.scrollIntoViewIfNeeded()

  const diagnostic = await page.evaluate(() => {
    const describe = (el: HTMLElement) => {
      const rect = el.getBoundingClientRect()
      const style = getComputedStyle(el)
      const chain: string[] = []
      let node: HTMLElement | null = el
      for (let i = 0; node && i < 5; i += 1, node = node.parentElement) {
        chain.push(`${node.tagName.toLowerCase()}${node.id ? `#${node.id}` : ''}${typeof node.className === 'string' && node.className ? `.${node.className.trim().replace(/\s+/g, '.')}` : ''}`)
      }
      return {
        chain: chain.join(' < '),
        text: (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 220),
        left: Math.round(rect.left * 10) / 10,
        right: Math.round(rect.right * 10) / 10,
        width: Math.round(rect.width * 10) / 10,
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
        offsetWidth: el.offsetWidth,
        minWidth: style.minWidth,
        maxWidth: style.maxWidth,
        widthCss: style.width,
        overflowX: style.overflowX,
        whiteSpace: style.whiteSpace,
        wordBreak: style.wordBreak,
        overflowWrap: style.overflowWrap,
        display: style.display,
        position: style.position,
        visibility: style.visibility,
      }
    }
    const all = [...document.querySelectorAll('body *')] as HTMLElement[]
    return {
      viewport: window.innerWidth,
      body: describe(document.body),
      html: describe(document.documentElement),
      row: describe(document.querySelector('.change-reference-row') as HTMLElement),
      intrinsic: all.filter(el => el.scrollWidth > el.clientWidth + 1).map(describe)
        .sort((a, b) => (b.scrollWidth - b.clientWidth) - (a.scrollWidth - a.clientWidth)).slice(0, 40),
      rightmost: all.filter(el => {
        const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0
      }).map(describe).sort((a, b) => b.right - a.right).slice(0, 25),
    }
  })
  console.log(`LATEST_SAMPLE_INTRINSIC ${JSON.stringify(diagnostic)}`)
})
