import { expect, test } from '@playwright/test'

function safeCookies(cookies: Awaited<ReturnType<import('@playwright/test').BrowserContext['cookies']>>) {
  return cookies.map(cookie => ({
    name: cookie.name,
    domain: cookie.domain,
    path: cookie.path,
    expires: cookie.expires,
    httpOnly: cookie.httpOnly,
    secure: cookie.secure,
    sameSite: cookie.sameSite,
    partitionKey: 'partitionKey' in cookie ? cookie.partitionKey : undefined,
  }))
}

test('Build 016F serial Login → Home → Prospect → Account Profile → Companies → My Account → sign-out', async ({ page, context }, testInfo) => {
  const runId = process.env.GITHUB_RUN_ID || 'local'
  const attempt = process.env.GITHUB_RUN_ATTEMPT || '1'
  const project = testInfo.project.name.replace(/[^a-z0-9]+/gi, '-').toLowerCase()
  const email = `towersignal-e2e-${runId}-${attempt}-${project}-016f@example.com`
  const password = 'TowerSignal-E2E-2026!'

  await page.goto('./#/home', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()

  await page.getByRole('tab', { name: 'Create account', exact: true }).click()
  await page.getByLabel('Full name').fill('E2E Verification')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()

  await expect(page.getByRole('heading', { name: /Good (morning|afternoon|evening), E2E/ })).toBeVisible()
  console.log(`016F_GATE ${testInfo.project.name} cookies_after_signup`, JSON.stringify(safeCookies(await context.cookies())))

  await page.goto('./#/home', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: /Good (morning|afternoon|evening), E2E/ })).toBeVisible()
  console.log(`016F_GATE ${testInfo.project.name} cookies_after_full_navigation`, JSON.stringify(safeCookies(await context.cookies())))

  await page.getByRole('button', { name: 'Prospect', exact: true }).click()
  await expect(page).toHaveURL(/#\/prospect$/)
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible()

  await expect(page.locator('.account-table tbody tr').first()).toBeVisible()
  await page.locator('.account-table tbody tr').first().click()
  await expect(page).toHaveURL(/#\/account\//)
  await expect(page.getByLabel('Selected cooling tower detail')).toBeVisible()
  const accountUrl = page.url()

  await page.reload({ waitUntil: 'networkidle' })
  await expect(page).toHaveURL(accountUrl)
  await expect(page.getByLabel('Selected cooling tower detail')).toBeVisible()
  console.log(`016F_GATE ${testInfo.project.name} cookies_after_account_reload`, JSON.stringify(safeCookies(await context.cookies())))

  await page.getByRole('button', { name: 'Companies', exact: true }).click()
  await expect(page).toHaveURL(/#\/companies$/)
  await expect(page.getByRole('heading', { name: 'Companies', exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Open TowerSignal account', exact: true }).click()
  await expect(page).toHaveURL(/#\/my-account$/)
  await expect(page.getByRole('heading', { name: 'E2E Verification', exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
  const cookiesAfterSignout = await context.cookies()
  console.log(`016F_GATE ${testInfo.project.name} cookies_after_signout`, JSON.stringify(safeCookies(cookiesAfterSignout)))
  expect(cookiesAfterSignout).toHaveLength(0)
})
