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
  const modeTabs = detail.locator('.account-mode-tabs')
  await expect(modeTabs).toBeVisible()
  const detailBox = await detail.boundingBox()
  const tabsBox = await modeTabs.boundingBox()
  expect(detailBox).not.toBeNull()
  expect(tabsBox).not.toBeNull()
  expect(tabsBox!.width).toBeGreaterThanOrEqual(detailBox!.width * 0.9)
  await modeTabs.getByRole('button', { name: /^Evidence/ }).click()

  const evidence = detail.locator('.account-evidence-workspace')
  await expect(evidence.locator(':scope > details')).toHaveCount(7)
  const property = evidence.locator(':scope > details').filter({ has: page.locator('summary strong', { hasText: 'Property / Ownership' }) })
  await expect(property).not.toHaveAttribute('open', '')
  await property.locator(':scope > summary').click()
  const boundary = property.locator('.evidence-boundary')
  await expect(boundary).toBeVisible()
  await expect(boundary).toContainText('Property-level BBL evidence unavailable')
  for (const source of ['PLUTO ownership', 'HPD contacts', 'DOB project roles', 'ACRIS parties']) await expect(boundary).toContainText(source)
  await expect(boundary).toContainText('does not infer a parcel identity')

  // The old flat Evidence sections must remain hidden, not leak a second layout.
  for (const legacy of await detail.locator(':scope > [data-account-mode-group="legacy-evidence"]').all()) await expect(legacy).toBeHidden()

  const historical = evidence.locator(':scope > details').filter({ has: page.locator('summary strong', { hasText: 'Historical Evidence' }) })
  await historical.locator(':scope > summary').click()
  const provenance = historical.locator('.evidence-provenance-details')
  await expect(provenance.locator(':scope > summary').getByText('Source & provenance', { exact: true })).toBeVisible()
  await expect(provenance).not.toHaveAttribute('open', '')
  await provenance.locator(':scope > summary').click()
  expect(await provenance.locator('.evidence-card').count()).toBeGreaterThan(0)
  await expect(provenance.locator('.evidence-card').first()).toBeVisible()
  await expect(provenance).toContainText('Generated')
  await expect(provenance).toContainText('Rules')
  await expect(provenance).toContainText('Priority model')

  await expectContained(page)
  await expectElementContained(page, '.account-evidence-workspace')
  const provenanceBox = await provenance.boundingBox()
  expect(provenanceBox).not.toBeNull()
  expect(provenanceBox!.width).toBeGreaterThan(0)
  expect(provenanceBox!.width).toBeLessThanOrEqual((page.viewportSize()?.width ?? 0) + 0.5)
  await testInfo.attach(`account-property-boundary-${unresolvedSystemId}-${testInfo.project.name}.png`, { body: await property.screenshot(), contentType: 'image/png' })

  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})
