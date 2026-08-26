import { expect, test } from '@playwright/test'

test('bounded NYS changes becomes visible directly on iPhone', async ({ page }) => {
  test.setTimeout(90_000)
  await page.goto('./', { waitUntil: 'networkidle' })
  await expect(page.getByRole('button', { name: 'NYS Changes', exact: true })).toBeVisible()
  const started = Date.now()
  await page.getByRole('button', { name: 'NYS Changes', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'New York State registry changes' })).toBeVisible({ timeout: 60_000 })
  console.log(JSON.stringify({ metric: 'bounded_direct_nys_changes_ms', value: Date.now() - started }))
  await expect(page.getByText(/NYS change[s]? in current view/)).toBeVisible()
})
