import { expect, test as setup } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { authStatePath, testCredentials } from './auth.helpers'
import { installCandidateRoutes } from './candidate-routes'

setup('prove signed-out route gate and sign in with a pre-provisioned TowerSignal account', async ({ page }, testInfo) => {
  await installCandidateRoutes(page)
  await page.goto('./#/companies', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Known companies & firms', exact: true })).toHaveCount(0)
  await expect(page.getByRole('tab', { name: 'Create account', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Create account', exact: true })).toHaveCount(0)

  const credentials = testCredentials(testInfo.project.name)
  await page.getByLabel('Email').fill(credentials.email)
  await page.getByLabel('Password', { exact: true }).fill(credentials.password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Known companies & firms', exact: true })).toBeVisible()

  const statePath = authStatePath(testInfo.project.name)
  mkdirSync(dirname(statePath), { recursive: true })
  await page.context().storageState({ path: statePath })
})
