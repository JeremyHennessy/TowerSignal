import { expect, test } from '@playwright/test'

test('classify hosted WebKit auth persistence boundary', async ({ page, context }) => {
  const authResponses: Array<{ url: string; status: number }> = []
  page.on('response', (response) => {
    const url = response.url()
    if (url.includes('neonauth') || url.includes('/auth/')) {
      authResponses.push({ url: url.replace(/\?.*$/, ''), status: response.status() })
    }
  })

  const runId = process.env.GITHUB_RUN_ID || 'local'
  const attempt = process.env.GITHUB_RUN_ATTEMPT || '1'
  const email = `towersignal-e2e-${runId}-${attempt}-cookie-diag@example.com`
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

  const summarize = (cookies: Awaited<ReturnType<typeof context.cookies>>) => cookies.map((cookie) => ({
    name: cookie.name,
    domain: cookie.domain,
    path: cookie.path,
    expires: cookie.expires,
    httpOnly: cookie.httpOnly,
    secure: cookie.secure,
    sameSite: cookie.sameSite,
    partitionKey: 'partitionKey' in cookie ? cookie.partitionKey : undefined,
  }))

  const afterSignup = summarize(await context.cookies())
  console.log('AUTH_DIAG cookies_after_signup', JSON.stringify(afterSignup))
  console.log('AUTH_DIAG responses_after_signup', JSON.stringify(authResponses))

  authResponses.length = 0
  await page.goto('./#/home', { waitUntil: 'networkidle' })

  const loginAfterNavigation = await page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true }).isVisible().catch(() => false)
  const homeAfterNavigation = await page.getByRole('heading', { name: /Good (morning|afternoon|evening), E2E/ }).isVisible().catch(() => false)
  const afterNavigation = summarize(await context.cookies())

  console.log('AUTH_DIAG login_after_navigation', String(loginAfterNavigation))
  console.log('AUTH_DIAG home_after_navigation', String(homeAfterNavigation))
  console.log('AUTH_DIAG cookies_after_navigation', JSON.stringify(afterNavigation))
  console.log('AUTH_DIAG responses_after_navigation', JSON.stringify(authResponses))

  expect(homeAfterNavigation, 'authenticated session must survive a full WebKit navigation').toBe(true)
})
