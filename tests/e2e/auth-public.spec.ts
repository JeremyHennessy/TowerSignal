import { expect, test } from '@playwright/test'

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
