import { expect, test } from './fixtures'

test('NYC Prospect exposes property enforcement and maps official Legionnaires intelligence to towers', async ({ page }) => {
  await page.evaluate(() => { window.location.hash = '#/prospect' })
  await expect(page.getByRole('heading', { name: 'Prospect workspace', exact: true })).toBeVisible()

  const alerts = page.getByLabel('Legionnaires official intelligence')
  await expect(alerts).toBeVisible()
  await expect(alerts).toContainText('official channels')
  await expect(alerts).toContainText(/TowerSignal system/)
  await expect(alerts).toContainText(/affected ZIP-code area/)
  await expect(alerts.getByRole('link', { name: 'Open official source' }).first()).toBeVisible()

  const contract = await page.evaluate(async () => {
    const [alertsResponse, systemsResponse] = await Promise.all([
      fetch(new URL('data/legionella-alerts.json', window.location.href), { cache: 'no-store' }),
      fetch(new URL('data/systems.json', window.location.href), { cache: 'no-store' }),
    ])
    if (!alertsResponse.ok || !systemsResponse.ok) throw new Error('Legionella/system contract unavailable')
    return { alerts: await alertsResponse.json(), systems: await systemsResponse.json() }
  }) as { alerts: { domain: string; summary: { source_channel_count: number; discovered_relevant_item_count: number; retrieval_error_count: number }; tower_matching: { explicit_pcr_positive_system_count: number; affected_area_system_count: number; published_positive_address_count: number; unmatched_published_address_count: number }; clusters: Array<{ affected_zip_codes: string[]; tower_matches: { explicit_pcr_positive: Array<{ system_id: string }> } }> }; systems: { systems: Array<{ system_id: string; legionella_pcr_positive_match?: boolean; legionella_cluster_match?: boolean }> } }
  expect(contract.alerts.domain).toBe('LEGIONELLA_PUBLIC_HEALTH_ALERTS')
  expect(contract.alerts.summary.source_channel_count).toBeGreaterThanOrEqual(10)
  expect(contract.alerts.summary.discovered_relevant_item_count).toBeGreaterThan(0)
  expect(contract.alerts.summary.retrieval_error_count).toBe(0)
  expect(contract.alerts.tower_matching.published_positive_address_count).toBeGreaterThanOrEqual(10)
  expect(contract.alerts.tower_matching.explicit_pcr_positive_system_count).toBeGreaterThan(0)
  expect(contract.alerts.tower_matching.affected_area_system_count).toBeGreaterThan(contract.alerts.tower_matching.explicit_pcr_positive_system_count)
  expect(contract.alerts.clusters[0].affected_zip_codes).toEqual(expect.arrayContaining(['10451', '10456']))
  const explicitIds = new Set(contract.alerts.clusters[0].tower_matches.explicit_pcr_positive.map(row => row.system_id))
  expect(contract.systems.systems.filter(row => row.legionella_pcr_positive_match).every(row => explicitIds.has(row.system_id))).toBe(true)
  expect(contract.systems.systems.some(row => row.legionella_cluster_match)).toBe(true)

  const hpd = page.getByLabel('HPD open violations')
  await hpd.selectOption('true')
  await expect(page.getByLabel('Active filters')).toContainText('HPD open violations: Yes')
  await expect(page.locator('.account-table tbody tr').first()).toContainText(/HPD open · [1-9]/)
  await hpd.selectOption('')
  const swo = page.getByLabel('Stop Work Order evidence')
  await swo.selectOption('true')
  await expect(page.getByLabel('Active filters')).toContainText('SWO evidence: Yes')
  await expect(page.locator('.account-table tbody tr').first()).toContainText(/SWO evidence · [1-9]/)
  await expect(page.getByLabel('FISP / Local Law 11 status').locator('option')).not.toHaveCount(1)
})
