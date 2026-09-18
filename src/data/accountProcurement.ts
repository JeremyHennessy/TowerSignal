import type { ProcurementRecord } from '../types/procurement'

export interface AccountProcurementPageRef { path: string; sha256: string; bytes: number; record_count: number }
export interface AccountProcurementManifest {
  schema_version: 1
  domain: 'TOWERSIGNAL_ACCOUNT_PROCUREMENT'
  system_id: string
  generated_at: string
  record_count: number
  sources: Array<{ file: string; name: string; status: string; generated_at: string | null; sha256: string | null; record_count: number | null; reason: string | null; source_health: unknown }>
  pages: AccountProcurementPageRef[]
}
const domain = 'TOWERSIGNAL_ACCOUNT_PROCUREMENT'
const sourceFiles = ['procurement-city-record.json', 'procurement-checkbook.json', 'procurement-nys-authorities.json', 'procurement-openbook-water.json', 'procurement-nycha-water.json']
const idPattern = /^[A-Za-z0-9_-]{1,64}$/
const base = import.meta.env.BASE_URL
function requireValid(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(`Account procurement unavailable: ${message}`)
}
function object(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value) }
function integer(value: unknown): value is number { return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 }

async function read(path: string, budget: number, signal?: AbortSignal): Promise<Uint8Array> {
  const response = await fetch(`${base}data/${path}`, { cache: 'no-store', signal })
  requireValid(response.ok, `HTTP ${response.status}; no global procurement fallback is used`)
  const reader = response.body?.getReader()
  if (!reader) {
    const bytes = new TextEncoder().encode(await response.text())
    requireValid(bytes.length <= budget, 'response exceeds the bounded payload contract')
    return bytes
  }
  const chunks: Uint8Array[] = []; let size = 0
  try {
    while (true) {
      const chunk = await reader.read()
      if (chunk.done) break
      size += chunk.value.byteLength
      if (size > budget) { await reader.cancel(); throw new Error('Account procurement unavailable: response exceeds the bounded payload contract') }
      chunks.push(chunk.value)
    }
  } finally { reader.releaseLock() }
  const bytes = new Uint8Array(size); let offset = 0
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length }
  return bytes
}

export async function loadAccountProcurementManifest(systemId: string, generatedAt: string, signal?: AbortSignal): Promise<AccountProcurementManifest> {
  requireValid(idPattern.test(systemId), 'invalid account identity')
  const raw = await read(`account-procurement/${systemId.slice(0, 2).toLowerCase()}/${systemId}/index.json`, 64 * 1024, signal)
  const value: unknown = JSON.parse(new TextDecoder().decode(raw))
  requireValid(object(value) && value.domain === domain && value.schema_version === 1 && value.system_id === systemId, 'manifest identity/schema mismatch')
  requireValid(value.generated_at === generatedAt && Number.isFinite(Date.parse(generatedAt)), 'projection is not from the displayed account snapshot')
  requireValid(Date.now() - Date.parse(generatedAt) <= 7 * 86400000, 'projection is stale; refresh source data')
  requireValid(integer(value.record_count) && Array.isArray(value.pages) && Array.isArray(value.sources), 'invalid manifest inventory')
  const sources = value.sources
  requireValid(sources.length === sourceFiles.length && sourceFiles.every(file => sources.filter((s: unknown) => object(s) && s.file === file).length === 1), 'source coverage inventory missing or duplicated')
  for (const source of value.sources) requireValid(object(source) && typeof source.name === 'string' && ['LOADED', 'UNAVAILABLE', 'MALFORMED', 'INCOMPLETE', 'STALE', 'UNVERIFIED'].includes(String(source.status)) && (source.record_count === null || integer(source.record_count)) && (source.status !== 'LOADED' || (integer(source.record_count) && typeof source.sha256 === 'string' && /^[a-f0-9]{64}$/.test(source.sha256))), 'invalid source coverage state')
  let count = 0
  for (const [index, page] of value.pages.entries()) {
    requireValid(object(page) && typeof page.sha256 === 'string' && /^[a-f0-9]{64}$/.test(page.sha256), 'invalid page digest')
    requireValid(page.path === `account-procurement/${systemId.slice(0, 2).toLowerCase()}/${systemId}/${String(index).padStart(4, '0')}-${page.sha256}.json`, 'unsafe or unordered page path')
    requireValid(integer(page.bytes) && page.bytes > 0 && page.bytes <= 256 * 1024 && integer(page.record_count) && page.record_count > 0 && page.record_count <= 20, 'invalid page budget')
    count += page.record_count
  }
  requireValid(count === value.record_count, 'page counts disagree with the manifest')
  return value as unknown as AccountProcurementManifest
}

export async function loadAccountProcurementPage(manifest: AccountProcurementManifest, index: number, signal?: AbortSignal): Promise<ProcurementRecord[]> {
  const reference = manifest.pages[index]
  requireValid(reference, 'requested page is absent')
  const bytes = await read(reference.path, 256 * 1024, signal)
  requireValid(bytes.length === reference.bytes, 'page size differs from manifest')
  const hash = await crypto.subtle.digest('SHA-256', bytes)
  const digest = Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('')
  requireValid(digest === reference.sha256, 'page checksum differs from manifest')
  const value: unknown = JSON.parse(new TextDecoder().decode(bytes))
  requireValid(object(value) && value.domain === domain + '_PAGE' && value.schema_version === 1 && value.system_id === manifest.system_id && value.generated_at === manifest.generated_at, 'page identity/snapshot mismatch')
  requireValid(Array.isArray(value.records) && value.records.length === reference.record_count, 'page record count mismatch')
  for (const record of value.records) requireValid(object(record) && Array.isArray(record.tower_account_system_ids) && record.tower_account_system_ids.includes(manifest.system_id) && ['CONFIRMED', 'STRONG'].includes(String(record.tower_link_confidence)) && typeof record.procurement_id === 'string' && typeof record.source === 'string', 'record lacks an exact confirmed/strong account link')
  return value.records as ProcurementRecord[]
}
