import { afterEach, beforeEach, expect, test, vi } from 'vitest'

const mocks = vi.hoisted(() => ({ rpc: vi.fn(), signOut: vi.fn() }))
vi.mock('@neondatabase/neon-js', () => ({ createClient: vi.fn(() => ({ rpc: mocks.rpc, auth: { signOut: mocks.signOut } })) }))
import { createClient } from '@neondatabase/neon-js'
import { loadAdminAccess, resetAdminAccess } from '../../src/auth/adminAccess'
import { loadServiceReportingAccess } from '../../src/serviceReporting/client'
import { signOutWorkflow } from '../../src/workflow/remoteClient'

beforeEach(() => { resetAdminAccess(); mocks.rpc.mockReset(); mocks.signOut.mockReset(); vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })

test('CRM and service checks share one authenticated client and recover together', async () => {
  mocks.rpc.mockResolvedValueOnce({ data: null, error: { message: 'session starting' } })
    .mockResolvedValueOnce({ data: true, error: null })
  const crm = loadAdminAccess()
  const service = loadServiceReportingAccess()
  await vi.runAllTimersAsync()
  expect(await crm).toBe(true)
  expect(await service).toBe(true)
  expect(mocks.rpc).toHaveBeenCalledTimes(2)
  expect(createClient).toHaveBeenCalledTimes(1)
})

test('a transient negative role can recover without a page refresh', async () => {
  mocks.rpc.mockResolvedValueOnce({ data: false, error: null }).mockResolvedValueOnce({ data: true, error: null })
  const access = loadAdminAccess()
  await vi.runAllTimersAsync()
  expect(await access).toBe(true)
})

test('standard users stay denied and completed permissions are not cached', async () => {
  mocks.rpc.mockResolvedValue({ data: false, error: null })
  const denied = loadAdminAccess()
  await vi.runAllTimersAsync()
  expect(await denied).toBe(false)
  expect(mocks.rpc).toHaveBeenCalledTimes(3)
  mocks.rpc.mockResolvedValue({ data: true, error: null })
  expect(await loadAdminAccess()).toBe(true)
})

test('repeated transport failures remain errors, not a standard user role', async () => {
  mocks.rpc.mockRejectedValue(new Error('Network unavailable'))
  const assertion = expect(loadAdminAccess()).rejects.toThrow('Network unavailable')
  await vi.runAllTimersAsync()
  await assertion
  expect(mocks.rpc).toHaveBeenCalledTimes(3)
})

test('sign-out rejects an earlier in-flight admin result', async () => {
  let finish!: (value: { data: boolean; error: null }) => void
  mocks.rpc.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  mocks.signOut.mockResolvedValue({ error: null })
  const assertion = expect(loadAdminAccess()).rejects.toThrow('session changed')
  await signOutWorkflow()
  finish({ data: true, error: null })
  await assertion
  mocks.rpc.mockResolvedValue({ data: false, error: null })
  const next = loadAdminAccess()
  await vi.runAllTimersAsync()
  expect(await next).toBe(false)
})
