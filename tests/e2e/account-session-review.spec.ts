import { expect, test } from '@playwright/test'
import { signInForProject } from './auth.helpers'

test.use({ trace: 'off' })
test.setTimeout(120_000)

test('record cookie-backed session behavior across Account reload without changing auth', async ({ page, context }, info) => {
  const requests: unknown[] = [], pending: Promise<void>[] = []
  page.on('response', response => {
    const url = new URL(response.url())
    if (!/get-session|sign-in\/email/.test(url.pathname)) return
    pending.push((async () => {
      const headers = await response.request().allHeaders()
      const body: unknown = await response.json().catch(() => null)
      const object = body && typeof body === 'object' ? body as Record<string, unknown> : {}
      const data = object.data && typeof object.data === 'object' ? object.data as Record<string, unknown> : object
      requests.push({ endpoint: `${url.origin}${url.pathname}`, status: response.status(), cookieSent: !!headers.cookie,
        hasUser: !!data.user, hasSession: !!data.session, topLevelKeys: Object.keys(object), hasError: !!object.error })
    })())
  })
  const cookieMetadata = async () => (await context.cookies()).map(cookie => ({
    name: cookie.name, domain: cookie.domain, path: cookie.path, secure: cookie.secure, httpOnly: cookie.httpOnly, sameSite: cookie.sameSite, expires: cookie.expires,
  }))
  let before: unknown = null
  try {
    await signInForProject(page, info.project.name, '#/account/2000015564')
    await expect(page.locator('.account-profile-page .account-mode-tabs')).toBeVisible({ timeout: 60_000 })
    before = { url: page.url(), cookies: await cookieMetadata() }
    await page.reload({ waitUntil: 'networkidle' })
    await expect(page.locator('.account-profile-page .account-mode-tabs')).toBeVisible({ timeout: 20_000 })
  } finally {
    await Promise.all(pending)
    await info.attach('session-reload-diagnostic.json', { body: JSON.stringify({ project: info.project.name, target: process.env.CANDIDATE_ROOT ? 'candidate' : 'actual-hosted', before,
      after: { url: page.url(), cookies: await cookieMetadata(), accountVisible: await page.locator('.account-profile-page .account-mode-tabs').isVisible(), signInVisible: await page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true }).isVisible() }, requests }, null, 2), contentType: 'application/json' })
    await info.attach('reload-state', { body: await page.screenshot({ animations: 'disabled' }), contentType: 'image/png' })
  }
})
