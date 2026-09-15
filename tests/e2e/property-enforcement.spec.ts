import { expect, test } from './fixtures'

test('NYC Prospect exposes property enforcement filters and official Legionnaires intelligence', async ({ page }) => {
  await page.evaluate(() => { window.location.hash = '#/prospect' })
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible()

  const alerts = page.getByLabel('Legionnaires official intelligence')
  await expect(alerts).toBeVisible()
  await expect(alerts).toContainText('official channels')
  await expect(alerts.getByRole('link', { name: 'Open official source' }).first()).toBeVisible()

  const alertContract = await page.evaluate(async () => {
    const url = new URL('data/legionella-alerts.json', window.location.href)
    const response = await fetch(url, { cache: 'no-store' })
    if (!response.ok) throw new Error(`Legionella cache HTTP ${response.status}`)
    return response.json() as Promise<{ domain: string; summary: { source_channel_count: number; discovered_relevant_item_count: number; retrieval_error_count: number } }>
  })
  expect(alertContract.domain).toBe('LEGIONELLA_PUBLIC_HEALTH_ALERTS')
  expect(alertContract.summary.source_channel_count).toBeGreaterThanOrEqual(10)
  expect(alertContract.summary.discovered_relevant_item_count).toBeGreaterThan(0)
  expect(alertContract.summary.retrieval_error_count).toBe(0)

  const hpd = page.getByLabel('HPD open violations')
  await hpd.selectOption('true')
  await expect(page.getByLabel('Active filters')).toContainText('HPD open violations: Yes')
  const hpdRow = page.locator('.account-table tbody tr').first()
  await expect(hpdRow).toBeVisible()
  await expect(hpdRow).toContainText(/HPD open · [1-9]/)

  await hpd.selectOption('')
  const swo = page.getByLabel('Stop Work Order evidence')
  await swo.selectOption('true')
  await expect(page.getByLabel('Active filters')).toContainText('SWO evidence: Yes')
  const swoRow = page.locator('.account-table tbody tr').first()
  await expect(swoRow).toBeVisible()
  await expect(swoRow).toContainText(/SWO evidence · [1-9]/)

  await expect(page.getByLabel('FISP / Local Law 11 status').locator('option')).not.toHaveCount(1)
})
