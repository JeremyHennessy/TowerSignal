import { createClient } from '@neondatabase/neon-js'
import type {
  WorkflowAccountPatch,
  WorkflowAccountState,
  WorkflowSavedView,
  WorkflowSnapshot,
  WorkflowUser,
  WorkflowWatchlist,
} from '../types/workflow'
import {
  bridgeAccessToken,
  bridgeGetSession,
  bridgeSignIn,
  bridgeSignOut,
  bridgeSignUp,
} from './bridgeSession'

const DEFAULT_AUTH_URL = 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech/neondb/auth'
const DEFAULT_DATA_API_URL = 'https://ep-silent-moon-au2icaki.apirest.c-10.us-east-1.aws.neon.tech/neondb/rest/v1'

const authUrl = import.meta.env.VITE_NEON_AUTH_URL || DEFAULT_AUTH_URL
const dataApiUrl = import.meta.env.VITE_NEON_DATA_API_URL || DEFAULT_DATA_API_URL
const bridgeUrl = String(import.meta.env.VITE_WORKFLOW_AUTH_BRIDGE_URL || '').trim()
const bridgeMode = Boolean(bridgeUrl)

export const workflowRuntimeEnabled = import.meta.env.MODE !== 'test'

const client = createClient({
  auth: { url: authUrl },
  dataApi: { url: dataApiUrl },
})

function message(error: unknown): string {
  if (error && typeof error === 'object' && 'message' in error) return String((error as { message?: unknown }).message ?? 'Unknown workflow error')
  return String(error || 'Unknown workflow error')
}

function throwIfError(context: string, error: unknown): void {
  if (error) throw new Error(`${context}: ${message(error)}`)
}

function userFrom(value: unknown): WorkflowUser | null {
  if (!value || typeof value !== 'object') return null
  const row = value as { id?: unknown; email?: unknown; name?: unknown }
  if (!row.id || !row.email) return null
  return {
    id: String(row.id),
    email: String(row.email),
    name: row.name == null ? null : String(row.name),
  }
}

async function dataApiRequest<T>(path: string, init: RequestInit = {}, retryAuth = true): Promise<T> {
  const token = await bridgeAccessToken(bridgeUrl)
  const response = await fetch(`${dataApiUrl.replace(/\/$/, '')}/${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${token}`,
      'content-type': 'application/json',
      ...(init.headers || {}),
    },
    cache: 'no-store',
  })
  if (response.status === 401 && retryAuth) {
    await bridgeAccessToken(bridgeUrl, true)
    return dataApiRequest<T>(path, init, false)
  }
  const text = await response.text()
  if (!response.ok) throw new Error(`Workflow Data API ${init.method || 'GET'} ${path} failed (HTTP ${response.status})${text ? `: ${text}` : ''}`)
  if (!text) return undefined as T
  return JSON.parse(text) as T
}

function eq(value: string): string {
  return encodeURIComponent(value)
}

export async function getWorkflowSession(): Promise<WorkflowUser | null> {
  if (!workflowRuntimeEnabled) return null
  if (bridgeMode) return bridgeGetSession(bridgeUrl)
  const result = await client.auth.getSession()
  throwIfError('Unable to load workflow session', result.error)
  if (!result.data?.session) return null
  return userFrom(result.data.user)
}

export async function signInWorkflow(email: string, password: string): Promise<WorkflowUser> {
  if (bridgeMode) return bridgeSignIn(bridgeUrl, email, password)
  const result = await client.auth.signIn.email({ email, password, rememberMe: true })
  throwIfError('Unable to sign in', result.error)
  const user = userFrom(result.data?.user)
  if (!user) throw new Error('Unable to sign in: session user was not returned')
  return user
}

export async function signUpWorkflow(email: string, password: string, name?: string): Promise<WorkflowUser> {
  if (bridgeMode) return bridgeSignUp(bridgeUrl, email, password, name)
  const result = await client.auth.signUp.email({
    email,
    password,
    name: name?.trim() || email.split('@')[0] || 'TowerSignal user',
  })
  throwIfError('Unable to create account', result.error)
  const user = userFrom(result.data?.user)
  if (!user) throw new Error('Unable to create account: session user was not returned')
  return user
}

export async function signOutWorkflow(): Promise<void> {
  if (bridgeMode) return bridgeSignOut(bridgeUrl)
  const result = await client.auth.signOut()
  throwIfError('Unable to sign out', result.error)
}

export async function loadWorkflowSnapshot(): Promise<WorkflowSnapshot> {
  if (!bridgeMode) {
    const [savedViewsResult, watchlistsResult, accountsResult, membershipsResult] = await Promise.all([
      client.from('workflow_saved_views').select('view_id,name,filters,created_at,updated_at').order('updated_at', { ascending: false }),
      client.from('workflow_watchlists').select('watchlist_id,name,created_at,updated_at').order('created_at', { ascending: true }),
      client.from('workflow_accounts').select('system_id,status,note,next_action_date,created_at,updated_at').order('updated_at', { ascending: false }),
      client.from('workflow_watchlist_members').select('watchlist_id,system_id,added_at').order('added_at', { ascending: true }),
    ])
    throwIfError('Unable to load saved views', savedViewsResult.error)
    throwIfError('Unable to load watchlists', watchlistsResult.error)
    throwIfError('Unable to load account workflow state', accountsResult.error)
    throwIfError('Unable to load watchlist membership', membershipsResult.error)
    return normalizeSnapshot(
      savedViewsResult.data as Array<Record<string, unknown>> | null,
      watchlistsResult.data as Array<Record<string, unknown>> | null,
      accountsResult.data as Array<Record<string, unknown>> | null,
      membershipsResult.data as Array<Record<string, unknown>> | null,
    )
  }

  const [savedViews, watchlists, accounts, memberships] = await Promise.all([
    dataApiRequest<Array<Record<string, unknown>>>('workflow_saved_views?select=view_id,name,filters,created_at,updated_at&order=updated_at.desc'),
    dataApiRequest<Array<Record<string, unknown>>>('workflow_watchlists?select=watchlist_id,name,created_at,updated_at&order=created_at.asc'),
    dataApiRequest<Array<Record<string, unknown>>>('workflow_accounts?select=system_id,status,note,next_action_date,created_at,updated_at&order=updated_at.desc'),
    dataApiRequest<Array<Record<string, unknown>>>('workflow_watchlist_members?select=watchlist_id,system_id,added_at&order=added_at.asc'),
  ])
  return normalizeSnapshot(savedViews, watchlists, accounts, memberships)
}

function normalizeSnapshot(
  savedViewRows: Array<Record<string, unknown>> | null | undefined,
  watchlistRows: Array<Record<string, unknown>> | null | undefined,
  accountRows: Array<Record<string, unknown>> | null | undefined,
  membershipRows: Array<Record<string, unknown>> | null | undefined,
): WorkflowSnapshot {
  const savedViews = (savedViewRows ?? []).map(row => ({
    id: String(row.view_id),
    name: String(row.name),
    filters: (row.filters ?? {}) as WorkflowSavedView['filters'],
    created_at: row.created_at == null ? undefined : String(row.created_at),
    updated_at: row.updated_at == null ? undefined : String(row.updated_at),
  }))
  const watchlists = (watchlistRows ?? []).map(row => ({
    id: String(row.watchlist_id),
    name: String(row.name),
    created_at: row.created_at == null ? undefined : String(row.created_at),
    updated_at: row.updated_at == null ? undefined : String(row.updated_at),
  }))
  const accounts = (accountRows ?? []).map(row => ({
    system_id: String(row.system_id),
    status: String(row.status) as WorkflowAccountState['status'],
    note: String(row.note ?? ''),
    next_action_date: row.next_action_date == null ? null : String(row.next_action_date),
    created_at: row.created_at == null ? undefined : String(row.created_at),
    updated_at: row.updated_at == null ? undefined : String(row.updated_at),
  }))
  const memberships = (membershipRows ?? []).map(row => ({
    watchlist_id: String(row.watchlist_id),
    system_id: String(row.system_id),
    added_at: row.added_at == null ? undefined : String(row.added_at),
  }))
  return { savedViews, watchlists, accounts, memberships }
}

export async function saveRemoteView(view: WorkflowSavedView): Promise<void> {
  const now = new Date().toISOString()
  if (!bridgeMode) {
    const update = await client.from('workflow_saved_views').update({ name: view.name, filters: view.filters, updated_at: now }).eq('view_id', view.id).select('view_id')
    throwIfError('Unable to update saved view', update.error)
    if ((update.data ?? []).length > 0) return
    const insert = await client.from('workflow_saved_views').insert({ view_id: view.id, name: view.name, filters: view.filters, updated_at: now }).select('view_id')
    throwIfError('Unable to save view', insert.error)
    return
  }
  const rows = await dataApiRequest<Array<{ view_id: string }>>(`workflow_saved_views?view_id=eq.${eq(view.id)}&select=view_id`, {
    method: 'PATCH', headers: { prefer: 'return=representation' }, body: JSON.stringify({ name: view.name, filters: view.filters, updated_at: now }),
  })
  if (rows.length) return
  await dataApiRequest('workflow_saved_views', {
    method: 'POST', headers: { prefer: 'return=representation' }, body: JSON.stringify({ view_id: view.id, name: view.name, filters: view.filters, updated_at: now }),
  })
}

export async function deleteRemoteView(viewId: string): Promise<void> {
  if (!bridgeMode) {
    const result = await client.from('workflow_saved_views').delete().eq('view_id', viewId)
    throwIfError('Unable to delete saved view', result.error)
    return
  }
  await dataApiRequest(`workflow_saved_views?view_id=eq.${eq(viewId)}`, { method: 'DELETE' })
}

export async function createRemoteWatchlist(watchlist: WorkflowWatchlist): Promise<void> {
  if (!bridgeMode) {
    const result = await client.from('workflow_watchlists').insert({ watchlist_id: watchlist.id, name: watchlist.name }).select('watchlist_id')
    throwIfError('Unable to create watchlist', result.error)
    return
  }
  await dataApiRequest('workflow_watchlists', {
    method: 'POST', headers: { prefer: 'return=representation' }, body: JSON.stringify({ watchlist_id: watchlist.id, name: watchlist.name }),
  })
}

export async function deleteRemoteWatchlist(watchlistId: string): Promise<void> {
  if (!bridgeMode) {
    const result = await client.from('workflow_watchlists').delete().eq('watchlist_id', watchlistId)
    throwIfError('Unable to delete watchlist', result.error)
    return
  }
  await dataApiRequest(`workflow_watchlists?watchlist_id=eq.${eq(watchlistId)}`, { method: 'DELETE' })
}

export async function saveRemoteAccount(systemId: string, patch: WorkflowAccountPatch): Promise<void> {
  const now = new Date().toISOString()
  const values = { ...patch, next_action_date: patch.next_action_date || null, updated_at: now }
  if (!bridgeMode) {
    const update = await client.from('workflow_accounts').update(values).eq('system_id', systemId).select('system_id')
    throwIfError('Unable to update account workflow state', update.error)
    if ((update.data ?? []).length > 0) return
    const insert = await client.from('workflow_accounts').insert({ system_id: systemId, ...values }).select('system_id')
    throwIfError('Unable to save account workflow state', insert.error)
    if ((insert.data ?? []).length <= 0) throw new Error('Unable to save account workflow state: inserted row was not returned')
    return
  }
  const rows = await dataApiRequest<Array<{ system_id: string }>>(`workflow_accounts?system_id=eq.${eq(systemId)}&select=system_id`, {
    method: 'PATCH', headers: { prefer: 'return=representation' }, body: JSON.stringify(values),
  })
  if (rows.length) return
  const inserted = await dataApiRequest<Array<{ system_id: string }>>('workflow_accounts', {
    method: 'POST', headers: { prefer: 'return=representation' }, body: JSON.stringify({ system_id: systemId, ...values }),
  })
  if (!inserted.length) throw new Error('Unable to save account workflow state: inserted row was not returned')
}

async function ensureRemoteAccount(systemId: string): Promise<void> {
  if (!bridgeMode) {
    const existing = await client.from('workflow_accounts').select('system_id').eq('system_id', systemId).limit(1)
    throwIfError('Unable to check account workflow state', existing.error)
    if ((existing.data ?? []).length > 0) return
    const insert = await client.from('workflow_accounts').insert({ system_id: systemId }).select('system_id')
    throwIfError('Unable to initialize account workflow state', insert.error)
    if ((insert.data ?? []).length <= 0) throw new Error('Unable to initialize account workflow state: inserted row was not returned')
    return
  }
  const existing = await dataApiRequest<Array<{ system_id: string }>>(`workflow_accounts?system_id=eq.${eq(systemId)}&select=system_id&limit=1`)
  if (existing.length) return
  const inserted = await dataApiRequest<Array<{ system_id: string }>>('workflow_accounts', {
    method: 'POST', headers: { prefer: 'return=representation' }, body: JSON.stringify({ system_id: systemId }),
  })
  if (!inserted.length) throw new Error('Unable to initialize account workflow state: inserted row was not returned')
}

export async function setRemoteMembership(systemId: string, watchlistId: string, enabled: boolean): Promise<void> {
  if (!bridgeMode) {
    if (!enabled) {
      const remove = await client.from('workflow_watchlist_members').delete().eq('system_id', systemId).eq('watchlist_id', watchlistId)
      throwIfError('Unable to remove account from watchlist', remove.error)
      return
    }
    await ensureRemoteAccount(systemId)
    const existing = await client.from('workflow_watchlist_members').select('system_id').eq('system_id', systemId).eq('watchlist_id', watchlistId).limit(1)
    throwIfError('Unable to check watchlist membership', existing.error)
    if ((existing.data ?? []).length > 0) return
    const insert = await client.from('workflow_watchlist_members').insert({ system_id: systemId, watchlist_id: watchlistId }).select('system_id')
    throwIfError('Unable to add account to watchlist', insert.error)
    return
  }
  if (!enabled) {
    await dataApiRequest(`workflow_watchlist_members?system_id=eq.${eq(systemId)}&watchlist_id=eq.${eq(watchlistId)}`, { method: 'DELETE' })
    return
  }
  await ensureRemoteAccount(systemId)
  const existing = await dataApiRequest<Array<{ system_id: string }>>(`workflow_watchlist_members?system_id=eq.${eq(systemId)}&watchlist_id=eq.${eq(watchlistId)}&select=system_id&limit=1`)
  if (existing.length) return
  await dataApiRequest('workflow_watchlist_members', {
    method: 'POST', headers: { prefer: 'return=representation' }, body: JSON.stringify({ system_id: systemId, watchlist_id: watchlistId }),
  })
}
