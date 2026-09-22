import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated } from './iphone.helpers'

test.use({ trace: 'off' })
test.setTimeout(300_000)

const cases = [
  {
    systemId: '2000014227',
    label: 'missing-sample',
    requiredText: [
      '400 West 61st Street',
      'VERIFY · No public Legionella sample date',
      'The current public registration record does not include a usable reported sample date.',
      'Sources & provenance',
      'Interpretation boundary',
    ],
  },
  {
    systemId: '2000015594',
    label: 'high-evidence',
    requiredText: [
      'NYC DEPARTMENT OF SMALL BUSINESS SERVICES',
      'Failure to report Legionella sample test date within 5 days',
      'Sources & provenance',
      'Interpretation boundary',
    ],
  },
] as const

for (const item of cases) {
  test(`client PDF renders source-backed ${item.label} account`, async ({ page }, testInfo) => {
    await signInForProject(page, testInfo.project.name, `#/account/${item.systemId}`)
    await expectAccountDetailHydrated(page)

    await expect(page.getByRole('button', { name: 'Export client PDF', exact: true })).toBeVisible()

    await page.emulateMedia({ media: 'print' })
    const report = page.locator('.client-pdf-report')
    await expect(report).toBeVisible()

    for (const text of item.requiredText) await expect(report).toContainText(text)

    const reportText = await report.innerText()
    expect(reportText).not.toContain('Copy lead brief')
    expect(reportText).not.toContain('Export client PDF')
    expect(reportText).not.toContain('No private follow-up set')
    expect(reportText).not.toContain('Use Summary workflow controls')

    const printState = await page.evaluate(() => ({
      rootDisplay: getComputedStyle(document.querySelector('#root') as HTMLElement).display,
      reportDisplay: getComputedStyle(document.querySelector('.client-pdf-report') as HTMLElement).display,
      reportWidth: (document.querySelector('.client-pdf-report') as HTMLElement).getBoundingClientRect().width,
    }))
    expect(printState.rootDisplay).toBe('none')
    expect(printState.reportDisplay).toBe('block')
    expect(printState.reportWidth).toBeGreaterThan(500)

    const pdf = await page.pdf({
      format: 'A4',
      printBackground: true,
      preferCSSPageSize: true,
      displayHeaderFooter: false,
    })
    const path = testInfo.outputPath(`TowerSignal-${item.systemId}-client-report.pdf`)
    await import('node:fs/promises').then(fs => fs.writeFile(path, pdf))
    await testInfo.attach(`TowerSignal-${item.systemId}-client-report.pdf`, {
      body: pdf,
      contentType: 'application/pdf',
    })
    await testInfo.attach(`TowerSignal-${item.systemId}-print-state.json`, {
      body: JSON.stringify(printState, null, 2),
      contentType: 'application/json',
    })
  })
}
