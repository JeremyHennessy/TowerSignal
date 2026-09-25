import { expect, test } from '@playwright/test'

test('password setup is available without a signed-in session', async ({ page }) => {
  await page.goto('./#/password-setup', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Set up or reset your password', exact: true })).toBeVisible()
  await expect(page.getByLabel('Email', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Send setup email', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Known companies & firms', exact: true })).toHaveCount(0)
})

test('password callback opens the form and removes its token from the URL', async ({ page }) => {
  // A non-secret marker verifies callback routing without sending an email or redeeming a token.
  await page.goto('./?token=public-route-check#/password-setup', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Choose your password', exact: true })).toBeVisible()
  await expect(page.getByLabel('New password', { exact: true })).toBeVisible()
  await expect(page.getByLabel('Confirm password', { exact: true })).toBeVisible()
  await expect(page).toHaveURL(/\/#\/password-setup$/)
})

test('protected workspace exposes sign-in only and no self-registration', async ({ page }) => {
  await page.goto('./#/companies', { waitUntil: 'networkidle' })

  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
  await expect(page.getByText('Access is limited to administrator-provisioned accounts.', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Known companies & firms', exact: true })).toHaveCount(0)
  await expect(page.getByRole('tab', { name: 'Create account', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Create account', exact: true })).toHaveCount(0)
  await expect(page.getByLabel('Full name')).toHaveCount(0)
  await expect(page.getByLabel('Confirm password')).toHaveCount(0)
})
