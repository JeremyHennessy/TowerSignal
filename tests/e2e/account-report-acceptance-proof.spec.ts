import { expect, test } from './fixtures'

const DENSE_ACCOUNTS = [
  { id: '2000000237', label: '1 PENN PLZ' },
  { id: '2000014267', label: '500 W 33RD ST' },
  { id: '2000015564', label: '16 E 39TH ST' },
]

const SPARSE_ACCOUNTS = [
  { id: '2000012577', label: '1813 Oriental Boulevard' },
  { id: '2000000948', label: '245 EAST 56th STREET' },
  { id: '2000000992', label: '715 Ocean Terrace' },
]

test.setTimeout(300_000)

async function openAccount(page: import('@playwright/test').Page, id: string) {
  await page.evaluate(accountId => { window.location.hash = `#/account/${accountId}` }, id)
  const detail = page.getByLabel('Selected cooling tower detail')
  await expect(detail).toBeVisible({ timeout: 90_000 })
  await expect(detail.locator('.loading-state')).toHaveCount(0, { timeout: 90_000 })
  await expect(detail.getByRole('heading', { name: 'Identity', exact: true })).toBeVisible()
  return detail
}

async function assertDesktopSingleFlow(page: import('@playwright/test').Page) {
  const result = await page.locator('.account-profile-page .detail-panel').evaluate(panel => {
    const panelRect = panel.getBoundingClientRect()
    const children = [...panel.children]
      .filter(child => child.matches('section,.technician-field-pack,.workflow-account-section'))
      .map(child => {
        const rect = child.getBoundingClientRect()
        const style = getComputedStyle(child)
        return {
          tag: child.tagName,
          className: child.className,
          width: rect.width,
          left: rect.left,
          right: rect.right,
          gridColumnStart: style.gridColumnStart,
          gridColumnEnd: style.gridColumnEnd,
        }
      })
    return { panelWidth: panelRect.width, panelLeft: panelRect.left, panelRight: panelRect.right, children }
  })
  expect(result.children.length).toBeGreaterThan(8)
  for (const child of result.children) {
    expect(child.width, `${child.tag}.${child.className} should span report width`).toBeGreaterThanOrEqual(result.panelWidth - 2)
    expect(Math.abs(child.left - result.panelLeft)).toBeLessThanOrEqual(1.5)
    expect(Math.abs(child.right - result.panelRight)).toBeLessThanOrEqual(1.5)
    expect(child.gridColumnStart).toBe('1')
    expect(child.gridColumnEnd).toBe('-1')
  }
}

async function assertIphoneSingleFlow(page: import('@playwright/test').Page) {
  const result = await page.locator('.account-profile-page .detail-panel').evaluate(panel => {
    const panelStyle = getComputedStyle(panel)
    const bodyWidth = document.body.scrollWidth
    const viewportWidth = window.innerWidth
    const children = [...panel.children]
      .filter(child => child.matches('section,.technician-field-pack,.workflow-account-section'))
      .map(child => {
        const rect = child.getBoundingClientRect()
        return { left: rect.left, right: rect.right, width: rect.width }
      })
    const offenders = [...document.querySelectorAll<HTMLElement>('body *')]
      .map(element => {
        const rect = element.getBoundingClientRect()
        const style = getComputedStyle(element)
        const className = typeof element.className === 'string' ? element.className : ''
        return {
          tag: element.tagName.toLowerCase(),
          id: element.id,
          className,
          left: Math.round(rect.left * 10) / 10,
          right: Math.round(rect.right * 10) / 10,
          width: Math.round(rect.width * 10) / 10,
          scrollWidth: element.scrollWidth,
          clientWidth: element.clientWidth,
          overflowX: style.overflowX,
          whiteSpace: style.whiteSpace,
          text: (element.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 140),
        }
      })
      .filter(item => item.right > viewportWidth + 1 || item.left < -1 || item.scrollWidth > item.clientWidth + 2)
      .sort((a, b) => Math.max(b.right - viewportWidth, b.scrollWidth - b.clientWidth) - Math.max(a.right - viewportWidth, a.scrollWidth - a.clientWidth))
      .slice(0, 25)
    return { display: panelStyle.display, bodyWidth, viewportWidth, children, offenders }
  })
  expect(result.display).toBe('block')
  expect(result.bodyWidth, `Horizontal overflow diagnostics:\n${JSON.stringify(result.offenders, null, 2)}`).toBeLessThanOrEqual(result.viewportWidth + 2)
  expect(result.children.length).toBeGreaterThan(8)
  for (const child of result.children) {
    expect(child.left).toBeGreaterThanOrEqual(-1)
    expect(child.right).toBeLessThanOrEqual(result.viewportWidth + 1)
    expect(child.width).toBeGreaterThan(0)
  }
}

async function capture(page: import('@playwright/test').Page, testInfo: import('@playwright/test').TestInfo, name: string) {
  await page.evaluate(() => window.scrollTo(0, 0))
  await testInfo.attach(name, { body: await page.screenshot({ fullPage: false }), contentType: 'image/png' })
}

for (const cohort of [
  { name: 'dense', accounts: DENSE_ACCOUNTS },
  { name: 'sparse', accounts: SPARSE_ACCOUNTS },
]) {
  test(`hosted ${cohort.name} account reports preserve the approved single-flow layout`, async ({ page }, testInfo) => {
    const consoleErrors: string[] = []
    const sameOriginFailures: string[] = []
    page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()) })
    page.on('requestfailed', request => {
      try {
        if (new URL(request.url()).origin === new URL(testInfo.project.use.baseURL as string).origin) {
          sameOriginFailures.push(`${request.url()} :: ${request.failure()?.errorText}`)
        }
      } catch { /* ignore non-URL diagnostics */ }
    })

    for (const account of cohort.accounts) {
      const detail = await openAccount(page, account.id)
      await expect(detail).toContainText(account.label, { timeout: 30_000 })
      await expect(detail.getByRole('heading', { name: 'NYC building-water signals', exact: true })).toBeVisible()
      await expect(detail.getByRole('heading', { name: 'NYC service-line records', exact: true })).toBeVisible()
      await expect(detail.getByRole('heading', { name: 'Historical profile', exact: true })).toBeVisible()
      await expect(detail.getByRole('heading', { name: 'Source & provenance', exact: true })).toBeVisible()

      await capture(page, testInfo, `${testInfo.project.name}-${cohort.name}-${account.id}-top`)
      if (testInfo.project.name === 'desktop-chromium') await assertDesktopSingleFlow(page)
      else await assertIphoneSingleFlow(page)
    }

    expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
    expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
  })
}
