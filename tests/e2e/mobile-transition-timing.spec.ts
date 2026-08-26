import { expect, test } from '@playwright/test'

const now = () => Date.now()

async function loadHome(page: import('@playwright/test').Page) {
  const started = now()
  await page.goto('./', { waitUntil: 'networkidle' })
  await expect(page.getByRole('button', { name: 'NYS Market', exact: true })).toBeVisible()
  console.log(JSON.stringify({ metric: 'home_ready_ms', value: now() - started }))
}

test('measure iPhone NYS transition costs independently', async ({ page }) => {
  test.setTimeout(240_000)

  await loadHome(page)
  let started = now()
  await page.getByRole('button', { name: 'NYS Changes', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'New York State registry changes' })).toBeVisible()
  console.log(JSON.stringify({ metric: 'prospect_to_nys_changes_ms', value: now() - started }))

  await loadHome(page)
  started = now()
  await page.getByRole('button', { name: 'NYS Market', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'New York State registry intelligence' })).toBeVisible()
  await expect(page.locator('.nys-table tbody tr').first()).toBeVisible()
  await expect(page.getByLabel('Filtered New York State cooling tower registry map')).toBeVisible()
  console.log(JSON.stringify({ metric: 'nys_market_ready_ms', value: now() - started }))

  started = now()
  await page.getByRole('button', { name: 'NYS Changes', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'New York State registry changes' })).toBeVisible()
  console.log(JSON.stringify({ metric: 'nys_market_to_changes_ms', value: now() - started }))
})
