import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { webcrypto } from 'node:crypto'
import { TextEncoder, TextDecoder } from 'node:util'
import { loadAccountProcurementManifest, loadAccountProcurementPage, type AccountProcurementManifest } from '../../src/data/accountProcurement'

const files = ['procurement-city-record.json', 'procurement-checkbook.json', 'procurement-nys-authorities.json', 'procurement-openbook-water.json', 'procurement-nycha-water.json']
const generated = '2026-09-18T10:00:00Z'
function manifest(): AccountProcurementManifest {
  return { domain: 'TOWERSIGNAL_ACCOUNT_PROCUREMENT', schema_version: 1, system_id: '2001', generated_at: generated,
    record_count: 0, pages: [], sources: files.map(file => ({ file, name: file, status: 'LOADED', generated_at: generated, sha256: 'a'.repeat(64), record_count: 0, reason: null, source_health: null })) }
}
const fetcher = vi.fn()
beforeEach(() => {
  vi.stubGlobal('fetch', fetcher); vi.stubGlobal('crypto', webcrypto)
  vi.stubGlobal('TextEncoder', TextEncoder); vi.stubGlobal('TextDecoder', TextDecoder)
  vi.spyOn(Date, 'now').mockReturnValue(Date.parse('2026-09-18T16:00:00Z'))
  fetcher.mockReset()
})
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })
function respond(body: unknown, status = 200) {
  fetcher.mockResolvedValue({ ok: status === 200, status, body: null, text: async () => JSON.stringify(body) })
}

test('an empty verified Account index requires one bounded request and no global source downloads', async () => {
  respond(manifest())
  expect((await loadAccountProcurementManifest('2001', generated)).record_count).toBe(0)
  expect(fetcher).toHaveBeenCalledTimes(1)
  expect(fetcher.mock.calls[0][0]).toMatch(/data\/account-procurement\/20\/2001\/index.json$/)
})

test('404, stale, malformed, wrong snapshot and missing coverage fail closed without bulk fallback', async () => {
  for (const [value, status] of [[{}, 404], [{ ...manifest(), generated_at: '2020-01-01' }, 200], [{ ...manifest(), pages: null }, 200], [{ ...manifest(), sources: [] }, 200]] as const) {
    respond(value, status)
    await expect(loadAccountProcurementManifest('2001', generated)).rejects.toThrow()
  }
  respond({ ...manifest(), generated_at: '2020-01-01T00:00:00Z' })
  await expect(loadAccountProcurementManifest('2001', '2020-01-01T00:00:00Z')).rejects.toThrow('stale')
  expect(fetcher.mock.calls.every(([url]) => String(url).includes('/account-procurement/'))).toBe(true)
})

test('partial source state is returned as partial rather than converted to a complete zero', async () => {
  const value = manifest(); value.sources[1] = { ...value.sources[1], status: 'UNAVAILABLE', record_count: null, sha256: null, reason: 'Missing cache' }
  respond(value)
  expect((await loadAccountProcurementManifest('2001', generated)).sources[1].status).toBe('UNAVAILABLE')
})

test('out-of-scope paths and oversized responses are rejected', async () => {
  const value = manifest(); value.record_count = 1
  value.pages = [{ path: '../../other.json', sha256: 'b'.repeat(64), bytes: 100, record_count: 1 }]
  respond(value); await expect(loadAccountProcurementManifest('2001', generated)).rejects.toThrow('path')
  respond({ ...manifest(), padding: 'x'.repeat(65536) })
  await expect(loadAccountProcurementManifest('2001', generated)).rejects.toThrow('bounded')
})

test('page digest, account identity and exact-link filtering are mandatory', async () => {
  const value = manifest()
  const page = { domain: 'TOWERSIGNAL_ACCOUNT_PROCUREMENT_PAGE', schema_version: 1, system_id: '2001', generated_at: generated,
    records: [{ procurement_id: 'r1', source: 'FIXTURE', tower_account_system_ids: ['2001'], tower_link_confidence: 'STRONG' }] }
  const raw = JSON.stringify(page), bytes = new TextEncoder().encode(raw)
  const digest = Array.from(new Uint8Array(await webcrypto.subtle.digest('SHA-256', bytes)), byte => byte.toString(16).padStart(2, '0')).join('')
  value.record_count = 1; value.pages = [{ path: `account-procurement/20/2001/0000-${digest}.json`, sha256: digest, bytes: bytes.length, record_count: 1 }]
  respond(page)
  expect((await loadAccountProcurementPage(value, 0))[0].procurement_id).toBe('r1')
  value.pages[0].sha256 = 'c'.repeat(64)
  await expect(loadAccountProcurementPage(value, 0)).rejects.toThrow('checksum')
})
