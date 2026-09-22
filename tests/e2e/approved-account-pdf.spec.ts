import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(240_000)
for (const systemId of ['2000000407', '2000014227']) {
  test(`approved Account PDF uses this account's records: ${systemId}`, async ({ page }, info) => {
    if (!isIphoneProject(info)) await page.setViewportSize({ width: 1792, height: 1000 })
    await signInForProject(page, info.project.name, `#/account/${systemId}`)
    await expectAccountDetailHydrated(page)
    const report = page.locator('.client-pdf-report')
    await expect(report).toHaveAttribute('data-report-design', 'approved-20260922')
    await expect(report).toHaveAttribute('data-report-system', systemId)
    if (process.env.EXPECTED_REPORT_SHA) await expect(report).toHaveAttribute('data-report-app-sha', process.env.EXPECTED_REPORT_SHA)
    await expect(report).toBeHidden()
    await expectContained(page)
    const before = await page.locator('.account-profile-page .detail-panel').boundingBox()
    await info.attach(`account-screen-${systemId}.png`, { body: await page.screenshot({ fullPage: true, animations: 'disabled', scale: 'css' }), contentType: 'image/png' })
    // Exercise the real click/asset-readiness handler without opening an OS dialog in CI.
    await page.evaluate(() => { window.print = () => { document.body.dataset.nativePrintCalled = 'true'; window.dispatchEvent(new Event('afterprint')) } })
    await page.getByRole('button', { name: 'Export client PDF', exact: true }).click()
    await expect(report).toHaveAttribute('data-assets-ready', 'true')
    await expect(page.locator('body')).toHaveAttribute('data-native-print-called', 'true')
    await expect(report).toBeHidden()
    await page.emulateMedia({ media: 'print' })
    await expect(report).toBeVisible()
    await expect(page.locator('#root')).toBeHidden()
    await expect(report.locator('.tsr-page')).toHaveCount(4)
    await expect(report.locator('.tsr-sources tbody tr')).toHaveCount(7)
    await expect(report.locator('.tsr-checkbox')).toHaveCount(3)
    await expect(report.locator('.tsr-account-link')).toHaveAttribute('href', `https://jeremyhennessy.github.io/TowerSignal/#/account/${systemId}`)
    if (systemId === '2000000407') {
      await expect(report.locator('.tsr-hero h1')).toHaveText('805 Columbus Avenue')
      await expect(report.locator('.tsr-summary')).toContainText('Check the one remaining July penalty.')
      await expect(report.locator('.tsr-case-row')).toHaveCount(3)
      await expect(report).toContainText('Columbus Square 805 LLC')
      await expect(report).toContainText('Western Residential, Inc.')
    } else {
      await expect(report).toContainText('No public Legionella sample date is shown')
      await expect(report).not.toContainText('805 Columbus')
      await expect(report).not.toContainText('0881344164')
    }
    const geometry = await report.evaluate(root => {
      const issues: string[] = []
      const pages = [...root.querySelectorAll<HTMLElement>('.tsr-page')].map((page, index) => {
        const box = page.getBoundingClientRect()
        if (Math.abs(box.width - 816) > 1 || Math.abs(box.height - 1056) > 1) issues.push(`page ${index + 1} size`)
        const blocks = [...page.children].filter(el => !el.matches('header,nav,footer'))
        for (const block of blocks) {
          const b = block.getBoundingClientRect()
          if (b.right > box.left + 769 || b.bottom > box.top + 1000) issues.push(`page ${index + 1} overflow ${block.className}`)
        }
        for (const el of page.querySelectorAll<HTMLElement>('.tsr-case-row,.tsr-action,.tsr-hero,.tsr-stats>div')) {
          // The approved hero intentionally clips decorative rings. Grid-cell
          // scrollHeight also includes transparent trailing padding. Check every
          // rendered text fragment instead, so genuine clipping still fails.
          const bounds = el.getBoundingClientRect()
          const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT)
          let node: Node | null
          while ((node = walker.nextNode())) {
            if (!node.textContent?.trim()) continue
            const range = document.createRange()
            range.selectNodeContents(node)
            for (const text of range.getClientRects()) {
              if (text.left < bounds.left - 1 || text.right > bounds.right + 1 || text.top < bounds.top - 1 || text.bottom > bounds.bottom + 1) {
                issues.push(`text overflow: ${el.className}: ${node.textContent}`)
              }
            }
          }
        }
        return { width: box.width, height: box.height, top: box.top }
      })
      const clear = (a: string, b: string) => {
        const first = root.querySelector(a)!.getBoundingClientRect(), second = root.querySelector(b)!.getBoundingClientRect()
        if (first.bottom > second.top + 1) issues.push(`overlap: ${a} / ${b}`)
      }
      clear('.tsr-samples', '.tsr-cases'); clear('.tsr-cases', '.tsr-separate'); clear('.tsr-sources', '.tsr-return')
      return { pages, issues, font: getComputedStyle(root).fontFamily }
    })
    // Retain actual PDF and geometry even if a later containment check fails.
    await info.attach(`report-geometry-${systemId}.json`, { body: JSON.stringify(geometry, null, 2), contentType: 'application/json' })
    if (!isIphoneProject(info)) {
      const output = info.outputPath(`approved-account-report-${systemId}.pdf`)
      const pdf = await page.pdf({ path: output, printBackground: true, preferCSSPageSize: true, displayHeaderFooter: false, tagged: true, outline: true })
      expect(pdf.byteLength).toBeGreaterThan(30_000)
      await info.attach(`account-report-${systemId}.pdf`, { body: pdf, contentType: 'application/pdf' })
      for (let i = 0; i < 4; i++) await info.attach(`report-${systemId}-page-${i + 1}.png`, { body: await report.locator('.tsr-page').nth(i).screenshot({ animations: 'disabled', scale: 'css' }), contentType: 'image/png' })
    }
    expect(geometry.issues).toEqual([])
    expect(geometry.font).toContain('TowerSignalReportInter')
    await page.emulateMedia({ media: 'screen' })
    await expect(report).toBeHidden()
    const after = await page.locator('.account-profile-page .detail-panel').boundingBox()
    expect(after?.x).toBe(before?.x)
    expect(after?.width).toBe(before?.width)
    await expectContained(page)
    if (systemId === '2000000407') {
      await page.evaluate(() => { window.location.hash = '#/account/2000014227' })
      await expect(report).toHaveAttribute('data-report-system', '2000014227')
      await expect(report).not.toContainText('805 Columbus')
      await expect(report).toBeHidden()
    }
  })
}
