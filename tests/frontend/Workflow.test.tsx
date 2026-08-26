import { act, render, renderHook, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'
import { WorkflowAccountSection } from '../../src/components/WorkflowAccountSection'
import { initialFilters } from '../../src/components/Filters'
import { workflowCsvText } from '../../src/utils/workflowExport'

const remote = vi.hoisted(() => ({
  getWorkflowSession: vi.fn(),
  loadWorkflowSnapshot: vi.fn(),
  saveRemoteView: vi.fn(),
  deleteRemoteView: vi.fn(),
  createRemoteWatchlist: vi.fn(),
  deleteRemoteWatchlist: vi.fn(),
  saveRemoteAccount: vi.fn(),
  setRemoteMembership: vi.fn(),
  signInWorkflow: vi.fn(),
  signOutWorkflow: vi.fn(),
  signUpWorkflow: vi.fn(),
}))

vi.mock('../../src/workflow/client', () => ({
  workflowRuntimeEnabled: true,
  ...remote,
}))

import { useWorkflow } from '../../src/workflow/useWorkflow'

const user = { id: 'user-1', email: 'sales@example.test', name: 'Sales User' }
const remoteSnapshot = {
  savedViews: [{ id: 'view-1', name: 'Manhattan', filters: { ...initialFilters, borough: 'Manhattan' } }],
  watchlists: [{ id: 'default', name: 'My watchlist' }],
  accounts: [{ system_id: 'SYS-1', status: 'investigate' as const, note: 'Call facilities', next_action_date: '2026-09-01' }],
  memberships: [{ watchlist_id: 'default', system_id: 'SYS-1' }],
}

beforeEach(() => {
  window.localStorage.clear()
  Object.values(remote).forEach(mock => mock.mockReset())
  remote.getWorkflowSession.mockResolvedValue(user)
  remote.loadWorkflowSnapshot.mockResolvedValue(remoteSnapshot)
  remote.saveRemoteView.mockResolvedValue(undefined)
  remote.deleteRemoteView.mockResolvedValue(undefined)
  remote.createRemoteWatchlist.mockResolvedValue(undefined)
  remote.deleteRemoteWatchlist.mockResolvedValue(undefined)
  remote.saveRemoteAccount.mockResolvedValue(undefined)
  remote.setRemoteMembership.mockResolvedValue(undefined)
  remote.signInWorkflow.mockResolvedValue(user)
  remote.signUpWorkflow.mockResolvedValue(user)
  remote.signOutWorkflow.mockResolvedValue(undefined)
})

test('hydrates signed-in private workflow state without changing public filters', async () => {
  const { result } = renderHook(() => useWorkflow())
  await waitFor(() => expect(result.current.loading).toBe(false))
  expect(result.current.user?.email).toBe('sales@example.test')
  expect(result.current.savedViews[0].filters.borough).toBe('Manhattan')
  expect(result.current.watchedSystemIds.has('SYS-1')).toBe(true)
  expect(result.current.accountBySystemId.get('SYS-1')?.status).toBe('investigate')
  expect(result.current.watchlistIdsBySystemId.get('SYS-1')?.has('default')).toBe(true)
})

test('migrates existing browser-local saved views when first signing into an empty remote workspace', async () => {
  const localView = { id: 'local-1', name: 'Queens follow-up', filters: { ...initialFilters, borough: 'Queens' } }
  window.localStorage.setItem('towersignal.savedViews.v1', JSON.stringify([localView]))
  remote.loadWorkflowSnapshot
    .mockResolvedValueOnce({ savedViews: [], watchlists: [], accounts: [], memberships: [] })
    .mockResolvedValueOnce({ savedViews: [localView], watchlists: [], accounts: [], memberships: [] })
    .mockResolvedValueOnce({ savedViews: [localView], watchlists: [{ id: 'default', name: 'My watchlist' }], accounts: [], memberships: [] })

  const { result } = renderHook(() => useWorkflow())
  await waitFor(() => expect(result.current.loading).toBe(false))
  expect(remote.saveRemoteView).toHaveBeenCalledWith(localView)
  expect(remote.createRemoteWatchlist).toHaveBeenCalledWith({ id: 'default', name: 'My watchlist' })
  expect(result.current.savedViews.map(view => view.name)).toContain('Queens follow-up')
})

test('adds a local-only saved view to an existing remote workspace without overwriting either side', async () => {
  const localView = { id: 'local-2', name: 'Queens local', filters: { ...initialFilters, borough: 'Queens' } }
  window.localStorage.setItem('towersignal.savedViews.v1', JSON.stringify([localView]))
  remote.loadWorkflowSnapshot
    .mockResolvedValueOnce(remoteSnapshot)
    .mockResolvedValueOnce({ ...remoteSnapshot, savedViews: [...remoteSnapshot.savedViews, localView] })

  const { result } = renderHook(() => useWorkflow())
  await waitFor(() => expect(result.current.loading).toBe(false))
  expect(remote.saveRemoteView).toHaveBeenCalledWith(localView)
  expect(result.current.savedViews.map(view => view.name)).toEqual(expect.arrayContaining(['Manhattan', 'Queens local']))
  const persisted = JSON.parse(window.localStorage.getItem('towersignal.savedViews.v1') ?? '[]') as Array<{ name: string }>
  expect(persisted.map(view => view.name)).toEqual(['Queens local'])
})

test('does not overwrite signed-out local saved views with signed-in private views', async () => {
  const localView = { id: 'local-1', name: 'Local fallback', filters: { ...initialFilters, borough: 'Queens' } }
  window.localStorage.setItem('towersignal.savedViews.v1', JSON.stringify([localView]))

  const { result } = renderHook(() => useWorkflow())
  await waitFor(() => expect(result.current.loading).toBe(false))
  expect(result.current.savedViews[0].name).toBe('Manhattan')

  const persisted = JSON.parse(window.localStorage.getItem('towersignal.savedViews.v1') ?? '[]') as Array<{ name: string }>
  expect(persisted.map(view => view.name)).toEqual(['Local fallback'])
})

test('keeps signed-in saved-view changes private from the signed-out local fallback', async () => {
  const localView = { id: 'local-1', name: 'Local fallback', filters: { ...initialFilters, borough: 'Queens' } }
  window.localStorage.setItem('towersignal.savedViews.v1', JSON.stringify([localView]))

  const { result } = renderHook(() => useWorkflow())
  await waitFor(() => expect(result.current.loading).toBe(false))
  await act(async () => {
    await result.current.saveView('Private follow-up', { ...initialFilters, borough: 'Brooklyn' })
  })

  expect(remote.saveRemoteView).toHaveBeenCalledWith(expect.objectContaining({ name: 'Private follow-up' }))
  const persisted = JSON.parse(window.localStorage.getItem('towersignal.savedViews.v1') ?? '[]') as Array<{ name: string }>
  expect(persisted.map(view => view.name)).toEqual(['Local fallback'])

  await act(async () => {
    await result.current.signOut()
  })
  expect(result.current.savedViews.map(view => view.name)).toEqual(['Local fallback'])
})

test('saves private account disposition without treating it as source evidence', async () => {
  const { result } = renderHook(() => useWorkflow())
  await waitFor(() => expect(result.current.loading).toBe(false))
  await act(async () => {
    await result.current.saveAccount('SYS-2', { status: 'follow-up', note: 'Asked for proposal timing', next_action_date: '2026-09-15' })
  })
  expect(remote.saveRemoteAccount).toHaveBeenCalledWith('SYS-2', { status: 'follow-up', note: 'Asked for proposal timing', next_action_date: '2026-09-15' })
  expect(result.current.accountBySystemId.get('SYS-2')?.status).toBe('follow-up')
})

test('first watchlist membership does not synthesize local account state that can overwrite an unsaved draft', async () => {
  remote.loadWorkflowSnapshot.mockResolvedValue({
    savedViews: [],
    watchlists: [{ id: 'default', name: 'My watchlist' }],
    accounts: [],
    memberships: [],
  })

  const { result } = renderHook(() => useWorkflow())
  await waitFor(() => expect(result.current.loading).toBe(false))
  await act(async () => {
    await result.current.toggleMembership('SYS-NEW', 'default', true)
  })

  expect(remote.setRemoteMembership).toHaveBeenCalledWith('SYS-NEW', 'default', true)
  expect(result.current.watchedSystemIds.has('SYS-NEW')).toBe(true)
  expect(result.current.watchlistIdsBySystemId.get('SYS-NEW')?.has('default')).toBe(true)
  expect(result.current.accountBySystemId.has('SYS-NEW')).toBe(false)
})

test('includes an annotated non-watchlisted account in CRM workflow export', () => {
  const metadata = { generated_at: '2026-08-25T00:00:00Z', snapshot_date: '2026-08-25' } as Parameters<typeof workflowCsvText>[1]
  const text = workflowCsvText([], metadata, [{ system_id: 'SYS-2', status: 'follow-up', note: 'Proposal timing', next_action_date: '2026-09-15' }], [], [])
  expect(text).toContain('"SYS-2"')
  expect(text).toContain('"follow-up"')
  expect(text).toContain('"Proposal timing"')
  expect(text).toContain('"2026-09-15"')
})

test('labels account workflow as user-entered private context', () => {
  render(<WorkflowAccountSection signedIn={false} account={undefined} watchlists={[]} membershipIds={new Set()} busy={false} onSave={vi.fn()} onToggleMembership={vi.fn()} />)
  expect(screen.getByText('User workflow')).toBeInTheDocument()
  expect(screen.getByText(/never treated as public-source evidence or scoring input/i)).toBeInTheDocument()
})
