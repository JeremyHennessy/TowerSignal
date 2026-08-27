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

export async function signInForProject(page: Page, projectName: string, targetHash: string): Promise<void> {
  await page.goto(`./${targetHash}`, { waitUntil: 'networkidle' })
  const loginHeading = page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })
  if (await loginHeading.isVisible().catch(() => false)) {
    const credentials = testCredentials(projectName)
    await page.getByLabel('Email').fill(credentials.email)
    await page.getByLabel('Password', { exact: true }).fill(credentials.password)
    await page.getByRole('button', { name: 'Sign in', exact: true }).click()
    await expect(loginHeading).toHaveCount(0)
  }
}
