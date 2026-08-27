import { expect, test as setup } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import { dirname } from 'node:path'

setup('establish authenticated TowerSignal session', async ({ page }, testInfo) => {
  await page.goto('./#/companies', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Companies', exact: true })).toHaveCount(0)

  const runId = process.env.GITHUB_RUN_ID || `${Date.now()}`
  const attempt = process.env.GITHUB_RUN_ATTEMPT || 'local'
  const project = testInfo.project.name.replace(/[^a-z0-9]+/gi, '-').toLowerCase()
  const email = `towersignal-e2e-${runId}-${attempt}-${project}@example.com`
  const password = 'TowerSignal-E2E-2026!'

  await page.getByRole('tab', { name: 'Create account', exact: true }).click()
  await page.getByLabel('Full name').fill('E2E Verification')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByLabel('Confirm password').fill(password)
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Companies', exact: true })).toBeVisible()

  const path = testInfo.project.name.includes('iphone') ? 'playwright/.auth/iphone.json' : 'playwright/.auth/desktop.json'
  mkdirSync(dirname(path), { recursive: true })
  await page.context().storageState({ path })
})
