import { expect, type Page } from '@playwright/test'

const PASSWORD = 'TowerSignal-E2E-2026!'

function family(projectName: string): 'desktop' | 'iphone' {
  return projectName.includes('iphone') ? 'iphone' : 'desktop'
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
  await gotoHosted(page, targetHash)
  const loginHeading = page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })
  if (await loginHeading.isVisible().catch(() => false)) {
    await submitSignIn(page, projectName)
  }
}
