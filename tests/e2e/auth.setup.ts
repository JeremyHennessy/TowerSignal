import { expect, test as setup } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { authStatePath, testCredentials } from './auth.helpers'
import { installCandidateRoutes } from './candidate-routes'
import { seedArcnyWorkflowForProject } from './workflow.seed'

setup('create hosted TowerSignal test account and prove signed-out route gate', async ({ page }, testInfo) => {
  page.on('response', async response => {
    if (!response.url().includes('.neonauth.')) return
    const headers = await response.allHeaders().catch(() => ({} as Record<string, string>))
    const pathname = new URL(response.url()).pathname
    console.log(`[NEON_AUTH_DIAG] project=${testInfo.project.name} path=${pathname} status=${response.status()} jwt=${Boolean(headers['set-auth-jwt'])} cookie=${Boolean(headers['set-cookie'])}`)
  })

  await installCandidateRoutes(page)
  await page.goto('./#/companies', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Known companies & firms', exact: true })).toHaveCount(0)

  const credentials = testCredentials(testInfo.project.name)
  await page.getByRole('tab', { name: 'Create account', exact: true }).click()
  await page.getByLabel('Full name').fill(credentials.name)
  await page.getByLabel('Email').fill(credentials.email)
  await page.getByLabel('Password', { exact: true }).fill(credentials.password)
  await page.getByLabel('Confirm password').fill(credentials.password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Known companies & firms', exact: true })).toBeVisible()

  await seedArcnyWorkflowForProject(page, testInfo.project.name)

  const statePath = authStatePath(testInfo.project.name)
  mkdirSync(dirname(statePath), { recursive: true })
  await page.context().storageState({ path: statePath })
})
