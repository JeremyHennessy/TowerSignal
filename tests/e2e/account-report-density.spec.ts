import { expect, test, type Page } from '@playwright/test'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained, expectElementContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(120_000)

async function currentUnresolvedBblSystemId(page: Page, baseURL: string): Promise<string> {
  const response = await page.request.get(new URL('data/systems.json', baseURL).toString())
  expect(response.ok(), `systems.json HTTP ${response.status()}`).toBeTruthy()
  const payload = await response.json() as {
    systems?: Array<{ system_id?: string; bbl?: string | null; bbl_identity_status?: string | null }>
  }
  const selected = (payload.systems ?? [])
    .filter(row => row.system_id && !row.bbl && String(row.bbl_identity_status ?? '').startsWith('UNRESOLVED'))
    .sort((left, right) => String(left.system_id).localeCompare(String(right.system_id)))[0]
  if (!selected?.system_id) throw new Error('Current hosted systems payload contains no unresolved-BBL cooling-tower account')
  return selected.system_id
}

test('full account report groups missing-BBL property evidence and keeps provenance expandable', async ({ page }, testInfo) => {
  const isIphone = isIphoneProject(testInfo)
  if (isIphone) testInfo.setTimeout(240_000)
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

  const baseURL = testInfo.project.use.baseURL as string
  const unresolvedSystemId = await currentUnresolvedBblSystemId(page, baseURL)
  await signInForProject(page, testInfo.project.name, `#/account/${encodeURIComponent(unresolvedSystemId)}`)
  await expect(page).toHaveURL(new RegExp(`#\\/account\\/${unresolvedSystemId.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}$`))
  if (isIphone) await expectAccountDetailHydrated(page)

  const detail = page.locator('.account-profile-page .detail-panel')
  const property = detail.locator('section.property-context-section')
  await expect(property).toHaveCount(1)
  await expect(property.getByRole('heading', { name: 'Property records', exact: true })).toBeVisible()
  await expect(property).toContainText('Property-level BBL context is unavailable')
  await expect(property).toContainText('PLUTO building context')
  await expect(property).toContainText('HPD registered contacts')
  await expect(property).toContainText('DOB NOW project activity')
  await expect(property).toContainText('ACRIS property activity')

  const legacyBblHeadings = await detail.locator('h3').evaluateAll(headings => headings
    .map(heading => heading.textContent?.trim())
    .filter(text => ['Building context', 'HPD registered contacts', 'DOB NOW project activity', 'ACRIS property activity'].includes(text ?? '')))
  expect(legacyBblHeadings).toEqual([])

  const provenance = detail.locator('section.source-provenance-section')
  await expect(provenance.getByRole('heading', { name: 'Source & provenance', exact: true })).toBeVisible()
  await expect(provenance).toContainText(/source datasets?/)
  const provenanceDetails = provenance.locator('details.account-provenance-details')
  await expect(provenanceDetails).toBeVisible()
  await expect(provenanceDetails).not.toHaveAttribute('open', '')
  await provenanceDetails.locator(':scope > summary').click()
  expect(await provenanceDetails.locator('.source-row').count()).toBeGreaterThan(0)
  await expect(provenanceDetails.locator('.source-row').first()).toBeVisible()

  await expectContained(page)
  await expectElementContained(page, 'section.property-context-section')
  await expectElementContained(page, 'section.source-provenance-section')

  const propertyScreenshot = await property.screenshot()
  await testInfo.attach(`account-property-boundary-${unresolvedSystemId}-${testInfo.project.name}.png`, { body: propertyScreenshot, contentType: 'image/png' })

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})