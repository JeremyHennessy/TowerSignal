import { expect, test as setup } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { authStatePath, testCredentials } from './auth.helpers'

setup('create hosted TowerSignal test account and prove signed-out route gate', async ({ page }, testInfo) => {
  await page.goto('./#/companies', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Companies', exact: true })).toHaveCount(0)

  const credentials = testCredentials(testInfo.project.name)
  await page.getByRole('tab', { name: 'Create account', exact: true }).click()
  await page.getByLabel('Full name').fill(credentials.name)
  await page.getByLabel('Email').fill(credentials.email)
  await page.getByLabel('Password', { exact: true }).fill(credentials.password)
  await page.getByLabel('Confirm password').fill(credentials.password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Companies', exact: true })).toBeVisible()

  const statePath = authStatePath(testInfo.project.name)
  mkdirSync(dirname(statePath), { recursive: true })
  await page.context().storageState({ path: statePath })
})
