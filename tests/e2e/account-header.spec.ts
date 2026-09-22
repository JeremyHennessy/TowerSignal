import { expect, test, type Page } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(300_000)

async function headerGeometry(page: Page) {
  return page.evaluate(() => {
    const box = (selector: string) => {
      const element = document.querySelector<HTMLElement>(selector)
      if (!element) throw new Error(`Missing Account header element: ${selector}`)
      const rect = element.getBoundingClientRect()
      return { x: rect.x, y: rect.y, width: rect.width, height: rect.height, right: rect.right, bottom: rect.bottom }
    }
    const root = '.account-profile-page .detail-panel > '
    return {
      viewport: innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      title: box(`${root}.detail-header`),
      actions: box(`${root}.detail-actions`),
      copy: box(`${root}.detail-actions > button:first-child`),
      pdf: box(`${root}.detail-actions > button:nth-child(2)`),
      score: box(`${root}.detail-actions > .score.large`),
      label: box(`${root}.detail-actions > span:last-child`),
    }
  })
}

function expectHeaderGeometry(geometry: Awaited<ReturnType<typeof headerGeometry>>) {
  const { viewport, title, actions, copy, pdf, score, label } = geometry
  expect(geometry.scrollWidth).toBeLessThanOrEqual(viewport + 1)
  for (const control of [copy, pdf, score, label]) {
    expect(control.x).toBeGreaterThanOrEqual(actions.x)
    expect(control.right).toBeLessThanOrEqual(actions.right + 1)
    expect(control.y).toBeGreaterThanOrEqual(actions.y)
    expect(control.bottom).toBeLessThanOrEqual(actions.bottom + 1)
  }
  expect(copy.height).toBeGreaterThanOrEqual(44)
  expect(pdf.height).toBeGreaterThanOrEqual(44)
  expect(copy.right).toBeLessThanOrEqual(pdf.x + 1)
  if (viewport >= 1181) {
    expect(Math.abs(title.y - actions.y)).toBeLessThanOrEqual(1)
    expect(Math.abs(title.height - actions.height)).toBeLessThanOrEqual(1)
    expect(title.right).toBeLessThanOrEqual(actions.x)
  }
  if (viewport > 600) {
    expect(Math.abs(score.x + score.width / 2 - label.x - label.width / 2)).toBeLessThanOrEqual(1)
    expect(label.y - score.bottom).toBeGreaterThanOrEqual(0)
    expect(label.y - score.bottom).toBeLessThanOrEqual(10)
    expect(pdf.right).toBeLessThanOrEqual(score.x + 1)
  } else {
    expect(label.x - score.right).toBeGreaterThanOrEqual(0)
    expect(label.x - score.right).toBeLessThanOrEqual(12)
    expect(Math.abs(score.y + score.height / 2 - label.y - label.height / 2)).toBeLessThanOrEqual(1)
    expect(copy.y).toBeGreaterThanOrEqual(score.bottom)
  }
}

test('2537 Broadway header aligns actions and score across desktop and mobile widths', async ({ page }, testInfo) => {
  await signInForProject(page, testInfo.project.name, '#/account/2000001381')
  await expectAccountDetailHydrated(page)
  const header = page.locator('.account-profile-page .detail-header')
  const actions = page.locator('.account-profile-page .detail-actions')
  await expect(header).toContainText('2537 BROADWAY')
  await expect(header).toContainText('2000001381')
  await expect(actions.getByRole('button', { name: 'Copy lead brief', exact: true })).toBeEnabled()
  await expect(actions.getByRole('button', { name: 'Export client PDF', exact: true })).toBeEnabled()
  const originalScore = await actions.locator('.score.large').innerText()
  const widths = isIphoneProject(testInfo) ? [390, 320] : [1880, 1440, 1280, 1181, 1180, 1024, 768, 601, 600]
  const results = []
  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 })
    await expectContained(page)
    const geometry = await headerGeometry(page)
    expectHeaderGeometry(geometry)
    await expect(actions.locator('.score.large')).toHaveText(originalScore)
    results.push(geometry)
    if ([1880, 1280, 390, 320].includes(width)) {
      await header.scrollIntoViewIfNeeded()
      await testInfo.attach(`account-header-${width}-${testInfo.project.name}.png`, {
        body: await page.screenshot({ animations: 'disabled', scale: 'css' }),
        contentType: 'image/png',
      })
    }
  }
  await testInfo.attach(`account-header-geometry-${testInfo.project.name}.json`, {
    body: JSON.stringify(results, null, 2),
    contentType: 'application/json',
  })

  // A long source address must wrap, never widen the Account canvas or clip controls.
  const heading = header.locator('h2')
  const originalAddress = await heading.innerText()
  await heading.evaluate(element => { element.textContent = '2537 BROADWAY / LONG BUILDING AND CAMPUS ADDRESS '.repeat(5) })
  expectHeaderGeometry(await headerGeometry(page))
  await heading.evaluate((element, value) => { element.textContent = value }, originalAddress)
  await expect(header).toContainText(originalAddress)
})
