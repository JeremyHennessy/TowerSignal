import { expect, test } from './fixtures'

test('authenticated Home and Account pages are linkable and signout returns to the public landing', async ({ page }) => {
  // The authenticated fixture already finishes on #/home. Avoid an immediate
  // document reload here: Safari blocks the cross-site Neon Auth cookie on
  // github.io even though the tab has just authenticated successfully.
  await expect(page).toHaveURL(/#\/home$/)
  await expect(page.getByRole('heading', { name: /Good morning, E2E/ })).toBeVisible()
  await expect(page.getByLabel('TowerSignal Home summary')).toBeVisible()
  await expect(page.getByRole('button', { name: 'My account', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Prospect', exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'My account', exact: true }).click()
  await expect(page).toHaveURL(/#\/my-account$/)
  await expect(page.getByRole('heading', { name: 'E2E Verification', exact: true })).toBeVisible()
  await expect(page.getByText('Authenticated', { exact: true })).toBeVisible()
  await expect(page.getByText('Login required', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page.getByRole('heading', { name: /Find the buildings that need you next/i })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Log in', exact: true }).first()).toHaveAttribute('href', '#/login')

  await page.goto('./#/prospect', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'Sign in to TowerSignal', exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toHaveCount(0)
})
