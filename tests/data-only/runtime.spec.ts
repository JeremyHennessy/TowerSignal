import { expect, test } from '@playwright/test'

// Reads real generated files over a local HTTP server. No mock records, fixture
// substitution, login bypass or changes to the deployed application's routes.
test('generated NYC/NYS data and detail paths are readable in the browser', async ({ page }) => {
  await page.goto('data/source-health.json')
  const result = await page.evaluate(async () => {
    async function load(name: string): Promise<Record<string, unknown>> {
      const response = await fetch(`/data/${name}`, { cache: 'no-store' })
      if (!response.ok) throw new Error(`Data HTTP ${response.status}: ${name}`)
      if (!response.headers.get('content-type')?.includes('json')) throw new Error(`Not JSON: ${name}`)
      return await response.json() as Record<string, unknown>
    }
    const systems = await load('systems.json')
    const nys = await load('nys-systems.json')
    const firms = await load('known-firms.json')
    const changes = await load('changes.json')
    const nysChanges = await load('nys-changes.json')
    const health = await load('source-health.json')
    const nycRows = systems.systems as Array<{ system_id: string }>
    const nysRows = nys.systems as Array<{ system_id: string }>
    const firmRows = firms.firms as Array<{ firm_id: string }>
    if (!Array.isArray(nycRows) || !Array.isArray(nysRows) || !Array.isArray(firmRows)) {
      throw new Error('Invalid core dataset arrays')
    }
    const details = []
    for (const row of nycRows.slice(0, 3)) {
      const id = String(row.system_id)
      const safe = [...id].filter(ch => /[A-Za-z0-9_-]/.test(ch)).join('')
      if (safe !== id) throw new Error('Unexpected system identifier')
      const detail = await load(`details/${safe.slice(0, 2).toLowerCase()}/${encodeURIComponent(safe)}.json`)
      details.push({ id, matches: (detail.identity as { system_id?: string })?.system_id === id })
    }
    const firmDetails = []
    for (const row of firmRows.slice(0, 2)) {
      const id = String(row.firm_id)
      const safe = [...id].filter(ch => /[A-Za-z0-9_-]/.test(ch)).join('')
      if (safe !== id) throw new Error('Unexpected firm identifier')
      const detail = await load(`firm-details/${safe.slice(0, 2).toLowerCase()}/${encodeURIComponent(safe)}.json`)
      firmDetails.push({ id: (detail.firm as { firm_id?: string })?.firm_id,
        matches: (detail.firm as { firm_id?: string })?.firm_id === id,
        domain: detail.domain, relationships: Array.isArray(detail.site_relationships) })
    }
    const absent = await fetch('/data/__missing_data_contract_check__.json')
    return { nycCount: nycRows.length, nysCount: nysRows.length, firmCount: firmRows.length,
      uniqueNyc: new Set(nycRows.map(row => row.system_id)).size,
      metadata: Boolean(systems.metadata && nys.metadata),
      history: Boolean(changes.history_started_at && nysChanges.history_started_at &&
        Array.isArray(changes.events) && Array.isArray(nysChanges.events)),
      health: Boolean(health.generated_at && Array.isArray(health.sources)),
      details, firmDetails, missingStatus: absent.status }
  })
  expect(result.nycCount).toBeGreaterThan(0)
  expect(result.nysCount).toBeGreaterThan(0)
  expect(result.firmCount).toBeGreaterThan(0)
  expect(result.uniqueNyc).toBe(result.nycCount)
  expect(result.metadata).toBe(true)
  expect(result.history).toBe(true)
  expect(result.health).toBe(true)
  expect(result.details).toHaveLength(3)
  expect(result.details.every(row => row.matches)).toBe(true)
  expect(result.firmDetails).toHaveLength(2)
  expect(result.firmDetails.every(row => row.matches && row.relationships &&
    row.domain === 'TOWERSIGNAL_KNOWN_FIRM_DETAIL')).toBe(true)
  expect(result.missingStatus).toBe(404)
})
