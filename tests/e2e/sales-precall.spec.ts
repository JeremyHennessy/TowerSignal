import { expect, test } from '@playwright/test'
import { submitSignIn } from './auth.helpers'
import { expectAccountDetailHydrated, expectDomText, expectElementContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(120_000)

test('hosted account exposes a source-backed sales pre-call brief before the technician field pack', async ({ page }, testInfo) => {
  const consoleErrors: string[] = []
  const sameOriginFailures: string[] = []
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('requestfailed', request => {
    try {
      if (new URL(request.url()).origin === new URL(testInfo.project.use.baseURL as string).origin) {
        sameOriginFailures.push(`${request.url()} :: ${request.failure()?.errorText}`)
      }
    } catch { /* ignore non-URL diagnostics */ }
  })

  await page.goto('./#/account/2000012577', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
  await submitSignIn(page, testInfo.project.name)
  await expect(page).toHaveURL(/#\/account\/2000012577$/)

  const isIphone = isIphoneProject(testInfo)
  if (isIphone) await expectAccountDetailHydrated(page)

  const sales = page.locator('.sales-precall-pack')
  const technician = page.locator('.technician-field-pack')
  if (isIphone) {
    await expectDomText(page, [
      'Pre-call sales brief',
      'Sales pre-call summary',
      'Why call now',
      'Account scale',
      'Contact path',
      'Timing evidence',
      'Call objective',
      'Before the call',
      'During the call',
      'Qualification questions',
      'Verify before asserting',
      'incumbent cooling-tower service provider is not established',
      'evidence class is not win probability',
      'Pre-visit field pack',
    ], '.detail-panel')
  } else {
    await expect(sales).toBeVisible()
    await expect(technician).toBeVisible()
    await expect(sales.getByRole('heading', { name: 'Pre-call sales brief', exact: true })).toBeVisible()
    await expect(sales.getByLabel('Sales pre-call summary')).toBeVisible()
    await expect(sales.getByText('Why call now', { exact: true })).toBeVisible()
    await expect(sales.getByText('Account scale', { exact: true })).toBeVisible()
    await expect(sales.getByText('Contact path', { exact: true })).toBeVisible()
    await expect(sales.getByText('Timing evidence', { exact: true })).toBeVisible()
    await expect(sales.getByText('Call objective', { exact: true })).toBeVisible()
    await expect(sales.getByRole('heading', { name: 'Before the call', exact: true })).toBeVisible()
    await expect(sales.getByRole('heading', { name: 'During the call', exact: true })).toBeVisible()
    await expect(sales.getByText('Qualification questions', { exact: true })).toBeVisible()
    await expect(sales.getByText('Verify before asserting', { exact: true })).toBeVisible()
    await expect(sales.getByText(/incumbent cooling-tower service provider is not established/i)).toBeVisible()
    await expect(sales.getByText(/evidence class is not win probability/i)).toBeVisible()
  }

  const order = await page.locator('.detail-panel').evaluate(element => {
    const sales = element.querySelector('.sales-precall-pack')
    const technician = element.querySelector('.technician-field-pack')
    if (!sales || !technician) return null
    return Boolean(sales.compareDocumentPosition(technician) & Node.DOCUMENT_POSITION_FOLLOWING)
  })
  expect(order).toBe(true)

  const viewportWidth = page.viewportSize()?.width ?? 0
  const bodyWidth = await page.evaluate(() => document.body.scrollWidth)
  expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 2)
  if (isIphone) {
    await expectElementContained(page, '.sales-precall-pack')
  } else {
    const salesBox = await sales.boundingBox()
    expect(salesBox).not.toBeNull()
    expect(salesBox!.width).toBeLessThanOrEqual(viewportWidth + 0.5)

    const screenshot = await sales.screenshot()
    await testInfo.attach(`sales-precall-2000012577-${testInfo.project.name}.png`, { body: screenshot, contentType: 'image/png' })
  }

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})
