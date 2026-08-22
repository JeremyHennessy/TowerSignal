import { expect, test } from '@playwright/test'

const DIAGNOSTIC_SYSTEM_LIMIT = 100

test('diagnostic: WebKit Changes switch with reduced systems workspace', async ({ page }) => {
  let sourceSystemCount = 0
  let servedSystemCount = 0

  await page.route('**/data/systems.json', async route => {
    const response = await route.fetch()
    const payload = await response.json()
    sourceSystemCount = Array.isArray(payload.systems) ? payload.systems.length : 0
    payload.systems = (payload.systems ?? []).slice(0, DIAGNOSTIC_SYSTEM_LIMIT)
    servedSystemCount = payload.systems.length
    payload.summary = {
      ...(payload.summary ?? {}),
      registered_systems: servedSystemCount,
    }
    await route.fulfill({ response, json: payload })
  })

  await page.goto('./', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'TowerSignal' })).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()

  const beforeNodes = await page.locator('*').count()
  const startedAt = Date.now()
  await page.getByRole('button', { name: 'Changes' }).click()
  await expect(page.getByRole('heading', { name: 'What changed?' })).toBeVisible({ timeout: 15_000 })
  const elapsedMs = Date.now() - startedAt
  const afterNodes = await page.locator('*').count()

  console.log(JSON.stringify({
    sourceSystemCount,
    servedSystemCount,
    beforeNodes,
    afterNodes,
    changesSwitchElapsedMs: elapsedMs,
  }))

  expect(sourceSystemCount).toBeGreaterThan(DIAGNOSTIC_SYSTEM_LIMIT)
  expect(servedSystemCount).toBe(DIAGNOSTIC_SYSTEM_LIMIT)
  expect(elapsedMs).toBeLessThan(15_000)
})
