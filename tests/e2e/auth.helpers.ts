import { expect, type Page } from '@playwright/test'
import { installCandidateRoutes } from './candidate-routes'

const PASSWORD = 'TowerSignal-E2E-2026!'
const AUTH_STATE_DIR = 'test-results/.auth'

function family(projectName: string): 'desktop' | 'iphone' {
  return projectName.includes('iphone') ? 'iphone' : 'desktop'
}

export function authStatePath(projectName: string): string {
  return `${AUTH_STATE_DIR}/${family(projectName)}.json`
}

export function testCredentials(projectName: string) {
  const runId = process.env.GITHUB_RUN_ID || 'local'
  const attempt = process.env.GITHUB_RUN_ATTEMPT || '1'
  const browserFamily = family(projectName)
  return {
    email: `towersignal-e2e-${runId}-${attempt}-${browserFamily}@example.com`,
    password: PASSWORD,
    name: 'E2E Verification',
  }
}

async function gotoHosted(page: Page, targetHash: string): Promise<void> {
  const attempts = process.env.CI ? 2 : 1
  let lastError: unknown
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      await page.goto(`./${targetHash}`, { waitUntil: 'networkidle' })
      return
    } catch (error) {
      lastError = error
      if (attempt === attempts) throw error
      const message = error instanceof Error ? error.message : String(error)
      if (!/ERR_CONNECTION_RESET|ERR_NETWORK_CHANGED|ERR_HTTP2_PROTOCOL_ERROR|Navigation timeout/i.test(message)) throw error
      await page.waitForTimeout(750)
    }
  }
  throw lastError
}

export async function submitSignIn(page: Page, projectName: string): Promise<void> {
  const credentials = testCredentials(projectName)
  const loginHeading = page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })
  const attempts = process.env.CI && family(projectName) === 'iphone' ? 2 : 1

  // CI uses real managed auth. Retained traces showed HTTP 429 with 4-6 second
  // retry windows. Wait before each test login rather than disabling production
  // protection or suppressing failures. Existing retries/assertions stay intact.
  if (process.env.CI) await page.waitForTimeout(11_000)

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    await page.getByLabel('Email').fill(credentials.email)
    await page.getByLabel('Password', { exact: true }).fill(credentials.password)
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    try {
      await expect(loginHeading).toHaveCount(0, { timeout: attempt < attempts ? 6_000 : 15_000 })
      return
    } catch (error) {
      if (attempt === attempts) throw error
      await expect(loginHeading).toBeVisible()
      await page.waitForTimeout(500)
    }
  }
}

export async function signInForProject(page: Page, projectName: string, targetHash: string): Promise<void> {
  await installCandidateRoutes(page)
  await gotoHosted(page, targetHash)
  const loginHeading = page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })
  if (await loginHeading.isVisible().catch(() => false)) {
    await submitSignIn(page, projectName)
  }
}

export async function signInFreshForProject(page: Page, projectName: string, targetHash: string): Promise<void> {
  await installCandidateRoutes(page)

  // GitHub Pages uses cross-origin managed auth. WebKit does not reliably carry
  // that remote cookie through a brand-new Playwright context, even when local
  // app storage was restored. For persistence-sensitive hosted tests, prove the
  // supported boundary explicitly: discard restored auth, perform a real sign-in
  // in this browser context, then stay in the same hydrated SPA session.
  await gotoHosted(page, '#/')
  await page.context().clearCookies()
  await page.evaluate(() => {
    window.localStorage.clear()
    window.sessionStorage.clear()
  })
  await gotoHosted(page, targetHash)

  const loginHeading = page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })
  await expect(loginHeading).toBeVisible()
  await submitSignIn(page, projectName)

  // Do not full-reload after sign-in. Hash navigation preserves the authenticated
  // SPA session and matches the known hosted WebKit support boundary.
  await page.evaluate(nextHash => { window.location.hash = nextHash }, targetHash)
  await page.waitForLoadState('networkidle').catch(() => undefined)
}
