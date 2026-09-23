import { expect, type Page } from '@playwright/test'
import { installCandidateRoutes } from './candidate-routes'

const AUTH_STATE_DIR = 'test-results/.auth'

function family(projectName: string): 'desktop' | 'iphone' {
  return projectName.includes('iphone') ? 'iphone' : 'desktop'
}

export function authStatePath(projectName: string): string {
  return `${AUTH_STATE_DIR}/${family(projectName)}.json`
}

export function testCredentials(_projectName: string) {
  const email = process.env.TOWERSIGNAL_E2E_EMAIL?.trim()
  const password = process.env.TOWERSIGNAL_E2E_PASSWORD
  if (!email || !password) {
    throw new Error('Hosted authentication verification requires pre-provisioned TOWERSIGNAL_E2E_EMAIL and TOWERSIGNAL_E2E_PASSWORD; tests must not create production users.')
  }
  return {
    email,
    password,
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
