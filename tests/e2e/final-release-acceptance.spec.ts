import { expect, test } from './fixtures'
import { signInForProject } from './auth.helpers'
import { expectAccountDetailHydrated, expectContained, isIphoneProject } from './iphone.helpers'

test.setTimeout(180_000)

test('final acceptance covers the generated Rochester Midland firm profile without inventing a mapped tower relationship', async ({ page }, testInfo) => {
  if (isIphoneProject(testInfo)) testInfo.setTimeout(300_000)
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

  await signInForProject(page, testInfo.project.name, '#/companies')
  await expect(page.getByRole('heading', { name: 'Known companies & firms', exact: true })).toBeVisible()

  const firm = await page.evaluate(async () => {
    const base = window.location.href.split('#')[0]
    const response = await fetch(new URL('data/known-firms.json', base).toString(), { cache: 'no-store' })
    if (!response.ok) throw new Error(`known-firms.json HTTP ${response.status}`)
    const payload = await response.json() as {
      firms?: Array<{
        firm_id: string
        canonical_name: string
        normalized_name: string
        identity_confidence: string
        roles: string[]
        observation_count: number
        observed_site_count: number
        mapped_site_count: number
        tower_account_count: number
        qualification_count: number
        active_qualification_count: number
        observed_contract_count: number
      }>
    }
    const matches = (payload.firms ?? []).filter(row =>
      row.normalized_name.toUpperCase().includes('ROCHESTER MIDLAND')
      || row.canonical_name.toUpperCase().includes('ROCHESTER MIDLAND')
    )
    if (matches.length !== 1) throw new Error(`Expected exactly one Rochester Midland firm, found ${matches.length}`)
    return matches[0]
  })

  expect(firm.identity_confidence).toBe('STRONG')
  expect(firm.observation_count).toBeGreaterThan(0)
  expect(firm.roles).toContain('DWT_INSPECTION_PROVIDER')
  expect(firm.roles).toContain('PROCUREMENT_VENDOR')
  expect(firm.roles).toContain('DEC_7G_REGISTERED_BUSINESS')
  expect(firm.qualification_count).toBeGreaterThan(0)
  expect(firm.active_qualification_count).toBeGreaterThan(0)
  expect(firm.observed_contract_count).toBeGreaterThan(0)

  await page.evaluate(firmId => { window.location.hash = `#/company/${encodeURIComponent(firmId)}` }, firm.firm_id)
  await expect(page.getByRole('heading', { level: 1, name: firm.canonical_name, exact: true })).toBeVisible()
  await expect(page.getByText('Identity & observed roles', { exact: true })).toBeVisible()
  await expect(page.getByText('Everything TowerSignal knows about this firm', { exact: true })).toBeVisible()
  await expect(page.getByText('DEC 7G qualifications', { exact: true })).toBeVisible()
  await expect(page.getByText('Public procurement observations', { exact: true })).toBeVisible()
  await expect(page.getByText('Intelligence workspace unavailable', { exact: true })).toHaveCount(0)

  const identityCard = page.locator('.company-identity-card')
  await expect(identityCard).toContainText('STRONG')
  await expect(page.locator('.firm-role-chip-row')).toContainText('DWT service provider')
  await expect(page.locator('.firm-role-chip-row')).toContainText('Procurement vendor')
  await expect(page.locator('.firm-role-chip-row')).toContainText('DEC 7G business')

  if (firm.mapped_site_count === 0) {
    await expect(page.getByText('No mapped site relationships match these filters.', { exact: true })).toBeVisible()
  } else {
    await expect(page.getByRole('region', { name: 'Known firm site relationship map', exact: true })).toBeVisible()
  }
  if (firm.tower_account_count === 0) {
    await expect(page.locator('.firm-site-account-links a[href^="#/account/"]')).toHaveCount(0)
  }

  await expectContained(page)
  expect(sameOriginFailures, `Same-origin request failures:\n${sameOriginFailures.join('\n')}`).toEqual([])
  expect(consoleErrors, `Console errors:\n${consoleErrors.join('\n')}`).toEqual([])
})


test('final acceptance opens a real recovered-BBL account selected from durable history provenance', async ({ page }, testInfo) => {
  if (isIphoneProject(testInfo)) testInfo.setTimeout(300_000)
  await signInForProject(page, testInfo.project.name, '#/prospect')

  const recovered = await page.evaluate(async () => {
    const base = window.location.href.split('#')[0]
    const response = await fetch(new URL('data/history/segments/core.json', base).toString(), { cache: 'no-store' })
    if (!response.ok) throw new Error(`history core HTTP ${response.status}`)
    const payload = await response.json() as {
      systems?: Array<{
        system_id: string
        bin: string | null
        bbl: string | null
        registry_bbl: string | null
        bbl_identity_status?: string
        bbl_identity_basis?: string
      }>
    }
    const matches = (payload.systems ?? []).filter(row =>
      row.registry_bbl == null
      && typeof row.bbl === 'string'
      && row.bbl.length > 0
      && row.bbl_identity_status === 'RECOVERED_EXACT_BIN_MAPPLUTO_BBL'
      && row.bbl_identity_basis === 'BUILDING_FOOTPRINT_MAPPLUTO_BBL_EXACT_BIN'
    )
    if (matches.length === 0) throw new Error('No current recovered-BBL system is present in durable history provenance')
    return matches[0]
  })

  expect(recovered.registry_bbl).toBeNull()
  expect(recovered.bbl).toMatch(/^\d{10}$/)
  expect(recovered.bin).toBeTruthy()
  expect(recovered.bbl_identity_status).toBe('RECOVERED_EXACT_BIN_MAPPLUTO_BBL')
  expect(recovered.bbl_identity_basis).toBe('BUILDING_FOOTPRINT_MAPPLUTO_BBL_EXACT_BIN')

  await page.evaluate(systemId => { window.location.hash = `#/account/${encodeURIComponent(systemId)}` }, recovered.system_id)
  const detail = page.locator('.account-profile-page .detail-panel')
  await expectAccountDetailHydrated(page)
  await expect(detail).toBeVisible()
  await expect(detail).toContainText(recovered.system_id)
  await expect(detail).toContainText(recovered.bbl!)
  await detail.locator('.account-mode-tabs').getByRole('button', { name: /^Evidence/ }).click()
  const workspace = detail.locator('.account-evidence-workspace')
  await expect(workspace).toBeVisible()
  await expect(workspace.locator(':scope > details.account-evidence-group')).toHaveCount(7)
  await expectContained(page)
})


test('retains visual evidence for every Account mode on desktop and iPhone', async ({ page }, testInfo) => {
  if (isIphoneProject(testInfo)) testInfo.setTimeout(300_000)
  await signInForProject(page, testInfo.project.name, '#/account/2000015564')
  await expectAccountDetailHydrated(page)

  const detail = page.locator('.account-profile-page .detail-panel')
  const tabs = detail.locator('.account-mode-tabs')
  const modes = [
    { name: 'Summary', selector: '.account-decision-summary' },
    { name: 'Sales', selector: '.sales-precall-pack' },
    { name: 'Field', selector: '.technician-field-pack' },
    { name: 'Evidence', selector: '.account-evidence-workspace' },
    { name: 'History', selector: '.account-unified-timeline' },
  ] as const

  for (const mode of modes) {
    await test.step(mode.name, async () => {
      await tabs.getByRole('button', { name: new RegExp(`^${mode.name}`) }).click()
      await expect(detail.locator(mode.selector)).toBeVisible()
      await tabs.scrollIntoViewIfNeeded()
      await expectContained(page)
      await testInfo.attach(`account-${mode.name.toLowerCase()}-${testInfo.project.name}.png`, {
        body: await page.screenshot({ animations: 'disabled' }),
        contentType: 'image/png',
      })
    })
  }
})
