import { beforeEach, expect, test, vi } from 'vitest'
import { readAllPages } from '../../src/companyAdmin/pagedRows'

const mocks = vi.hoisted(() => ({ from: vi.fn(), rpc: vi.fn() }))
vi.mock('../../src/auth/client', () => ({ neonClient: mocks }))
import { loadCompanyAdminOverview, loadCompanyAdminDirectory } from '../../src/companyAdmin/client'

beforeEach(() => vi.clearAllMocks())

test('a directory larger than 10 MB and 1,000 firms is fully read with bounded responses, including short server pages', async () => {
  const source = Array.from({ length: 2501 }, (_, i) => ({ company_id: `firm-${i}`, notes: 'x'.repeat(5000) }))
  expect(JSON.stringify(source).length).toBeGreaterThan(10 * 1024 * 1024)
  const fetchPage = vi.fn(async (from: number, to: number) => {
    expect(to - from + 1).toBe(100)
    const data = source.slice(from, Math.min(to + 1, from + 73))
    expect(JSON.stringify(data).length).toBeLessThan(1024 * 1024)
    return { data, count: source.length, error: null }
  })
  expect(await readAllPages(fetchPage, 'company_id')).toEqual(source)
  expect(fetchPage).toHaveBeenCalledTimes(35)
})

test.each([
  { data: null, count: 1, error: null },
  { data: [], count: null, error: null },
  { data: [], count: 1, error: null },
  { data: [{ id: 'a' }, { id: 'a' }], count: 2, error: null },
  { data: [{}], count: 1, error: null },
  { data: [{ id: 'a' }], count: 0, error: null },
  { data: [], count: 0, error: { message: 'permission denied' } },
])('an incomplete or failed page never becomes a successful directory: %j', async page => {
  await expect(readAllPages(async () => page, 'id')).rejects.toThrow()
})

test('a changing count fails without returning a partially loaded directory', async () => {
  const fetchPage = vi.fn().mockResolvedValueOnce({ data: [{ id: 'a' }], count: 2, error: null })
    .mockResolvedValueOnce({ data: [{ id: 'b' }], count: 3, error: null })
  await expect(readAllPages(fetchPage, 'id')).rejects.toThrow('changed')
})

function serveTables(tables: Record<string, Record<string, unknown>[]>) {
  const requests: { table: string; from: number; to: number }[] = []
  mocks.rpc.mockResolvedValue({ data: true, error: null })
  mocks.from.mockImplementation((table: string) => {
    let activeOnly = false
    const order: string[] = []
    const builder = {
      select: vi.fn((_columns: string, options: { count: string }) => {
        expect(options.count).toBe('exact')
        return builder
      }),
      eq: vi.fn((key: string, value: string) => {
        expect([table, key, value]).toEqual(['company_sales_accounts', 'record_status', 'active'])
        activeOnly = true
        return builder
      }),
      order: vi.fn((key: string) => { order.push(key); return builder }),
      range: vi.fn(async (from: number, to: number) => {
        expect(order.length).toBe(2) // stable ID tie-breaker after display/date ordering
        const data = (tables[table] ?? []).filter(row => !activeOnly || row.record_status === 'active')
        requests.push({ table, from, to })
        return { data: data.slice(from, to + 1), count: data.length, error: null }
      }),
    }
    return builder
  })
  return requests
}

test('overview preserves every mapped identity beyond API row caps and excludes merged accounts', async () => {
  const profiles = Array.from({ length: 1201 }, (_, i) => ({ company_id: `firm-${i}`, canonical_name: `Firm ${i}` }))
  const accounts = profiles.map(p => ({ sales_account_id: `account-${p.company_id}`, primary_company_id: p.company_id, record_status: 'active' }))
  const members = accounts.map(a => ({ company_id: a.primary_company_id, sales_account_id: a.sales_account_id, is_primary: true }))
  const requests = serveTables({ company_private_profiles: profiles, company_sales_accounts: [...accounts, { sales_account_id: 'merged', record_status: 'merged' }], company_sales_account_members: members })
  const overview = await loadCompanyAdminOverview()
  expect(overview.profiles).toHaveLength(1201)
  expect(overview.accounts).toHaveLength(1201)
  expect(overview.members).toHaveLength(1201)
  expect(requests.filter(r => r.table === 'company_private_profiles')).toHaveLength(13)
  expect(mocks.rpc).toHaveBeenCalledWith('towersignal_is_admin')
  expect(mocks.rpc).not.toHaveBeenCalledWith('towersignal_company_admin_snapshot')
  expect(await loadCompanyAdminDirectory()).toHaveLength(1201)
})

test('a mapping changed between table reads fails closed instead of displaying disconnected firms', async () => {
  serveTables({ company_private_profiles: [{ company_id: 'orphan', canonical_name: 'Firm' }] })
  await expect(loadCompanyAdminOverview()).rejects.toThrow('mappings could not be loaded completely')
})
