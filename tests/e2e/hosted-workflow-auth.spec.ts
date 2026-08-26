import { expect, test } from '@playwright/test'

test('hosted production workflow survives a fresh signed-in browser session', async ({ browser }) => {
  test.setTimeout(90_000)
  const nonce = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const email = `towersignal-hosted-${nonce}@example.com`
  const password = `Ts-${nonce}-Aa9!`
  const watchlistName = `Hosted proof ${nonce}`
  const note = `Hosted cross-session proof ${nonce}`
  const baseURL = 'https://jeremyhennessy.github.io/TowerSignal/'

  const context1 = await browser.newContext()
  const page1 = await context1.newPage()
  await page1.goto(baseURL, { waitUntil: 'networkidle' })
  await page1.getByRole('button', { name: 'Sync workflow' }).click()
  await page1.getByRole('button', { name: 'Need an account? Create one' }).click()
  await page1.getByLabel('Email').fill(email)
  await page1.getByLabel('Password').fill(password)
  await page1.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page1.getByText('Workflow synced', { exact: true })).toBeVisible()
  await expect(page1.getByText(email, { exact: true })).toBeVisible()
  await expect(page1.getByText('My watchlist', { exact: true })).toBeVisible()

  await page1.getByLabel('New watchlist name').fill(watchlistName)
  await page1.getByRole('button', { name: 'Add', exact: true }).click()
  await expect(page1.getByText(watchlistName, { exact: true })).toBeVisible()

  await page1.locator('.account-table tbody tr').first().click()
  await expect(page1.getByRole('heading', { name: 'Account workflow', exact: true })).toBeVisible()
  await page1.getByLabel('Status').selectOption('follow-up')
  await page1.getByLabel('Next action').fill('2026-09-15')
  await page1.getByLabel('Private note').fill(note)
  const membership1 = page1.getByLabel(watchlistName, { exact: true })
  await membership1.click()
  await expect(membership1).toBeChecked({ timeout: 15_000 })
  await page1.getByRole('button', { name: 'Save workflow state', exact: true }).click()
  await expect(page1.getByText('Saved', { exact: true })).toBeVisible()
  await page1.getByRole('button', { name: 'Close details' }).click()

  await page1.getByRole('button', { name: 'Sign out', exact: true }).click()
  await expect(page1.getByRole('button', { name: 'Sync workflow' })).toBeVisible()
  await context1.close()

  const context2 = await browser.newContext()
  const page2 = await context2.newPage()
  await page2.goto(baseURL, { waitUntil: 'networkidle' })
  await page2.getByRole('button', { name: 'Sync workflow' }).click()
  await page2.getByLabel('Email').fill(email)
  await page2.getByLabel('Password').fill(password)
  await page2.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page2.getByText('Workflow synced', { exact: true })).toBeVisible()
  await expect(page2.getByText(email, { exact: true })).toBeVisible()
  await expect(page2.getByText(watchlistName, { exact: true })).toBeVisible()

  await page2.getByRole('button', { name: 'Show watched accounts only', exact: true }).click()
  await expect(page2.locator('.account-table tbody tr').first()).toBeVisible()
  await page2.locator('.account-table tbody tr').first().click()
  await expect(page2.getByLabel('Status')).toHaveValue('follow-up')
  await expect(page2.getByLabel('Next action')).toHaveValue('2026-09-15')
  await expect(page2.getByLabel('Private note')).toHaveValue(note)
  const membership2 = page2.getByLabel(watchlistName, { exact: true })
  await expect(membership2).toBeChecked()

  // Remove meaningful diagnostic workflow state before leaving the disposable user behind.
  await membership2.click()
  await expect(membership2).not.toBeChecked({ timeout: 15_000 })
  await page2.getByLabel('Status').selectOption('new')
  await page2.getByLabel('Next action').fill('')
  await page2.getByLabel('Private note').fill('')
  await page2.getByRole('button', { name: 'Save workflow state', exact: true }).click()
  await expect(page2.getByText('Saved', { exact: true })).toBeVisible()
  await page2.getByRole('button', { name: 'Close details' }).click()
  await page2.getByRole('button', { name: `Delete ${watchlistName}` }).click()
  await expect(page2.getByText(watchlistName, { exact: true })).toHaveCount(0)
  await page2.getByRole('button', { name: 'Sign out', exact: true }).click()
  await context2.close()
})
