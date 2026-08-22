import { expect, test } from '@playwright/test'

test('diagnostic: WebKit Changes switch when hidden does not apply display none', async ({ page }) => {
  await page.goto('./', { waitUntil: 'networkidle' })
  await expect(page.getByRole('heading', { name: 'TowerSignal' })).toBeVisible()
  await expect(page.locator('.leaflet-container')).toBeVisible()

  await page.addStyleTag({ content: '.app-shell > div[hidden] { display: block !important; }' })

  const leadsWrapper = page.locator('.workspace').locator('..')
  const beforeDisplay = await leadsWrapper.evaluate(element => getComputedStyle(element).display)
  const startedAt = Date.now()
  await page.getByRole('button', { name: 'Changes' }).click()
  await expect(page.getByRole('heading', { name: 'What changed?' })).toBeVisible({ timeout: 15_000 })
  const elapsedMs = Date.now() - startedAt
  const afterDisplay = await leadsWrapper.evaluate(element => getComputedStyle(element).display)
  const hiddenAttribute = await leadsWrapper.getAttribute('hidden')

  console.log(JSON.stringify({ beforeDisplay, afterDisplay, hiddenAttribute, changesSwitchElapsedMs: elapsedMs }))

  expect(beforeDisplay).not.toBe('none')
  expect(afterDisplay).not.toBe('none')
  expect(hiddenAttribute).not.toBeNull()
  expect(elapsedMs).toBeLessThan(15_000)
})
