import { expect, test } from '@playwright/test'

test('isolated NYS changes shell paints on iPhone', async ({ page }) => {
  test.setTimeout(60_000)
  await page.goto('./', { waitUntil: 'networkidle' })
  const started = Date.now()
  await page.getByRole('button', { name: 'NYS Changes', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'New York State registry changes' })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByLabel('TowerSignal NYS changes')).toContainText('retained NYS changes')
  console.log(JSON.stringify({ metric: 'isolated_nys_changes_ms', value: Date.now() - started }))
})
