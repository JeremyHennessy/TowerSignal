import { expect, test } from '@playwright/test'

test('diagnostic: WebKit Changes switch when App does not set hidden on Leads subtree', async ({ page }) => {
  await page.goto('./', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'TowerSignal' })).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()

  const leadsWrapper = page.locator('[data-diagnostic-leads-mode]')
  await expect(leadsWrapper).toHaveAttribute('data-diagnostic-leads-mode', 'leads')
  expect(await leadsWrapper.getAttribute('hidden')).toBeNull()

  const startedAt = Date.now()
  await page.getByRole('button', { name: 'Changes' }).click()
  await expect(page.getByRole('heading', { name: 'What changed?' })).toBeVisible({ timeout: 15_000 })
  const elapsedMs = Date.now() - startedAt

  await expect(leadsWrapper).toHaveAttribute('data-diagnostic-leads-mode', 'changes')
  expect(await leadsWrapper.getAttribute('hidden')).toBeNull()
  console.log(JSON.stringify({ changesSwitchElapsedMs: elapsedMs }))
  expect(elapsedMs).toBeLessThan(15_000)
})
