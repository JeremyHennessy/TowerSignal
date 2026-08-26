import { createClient } from '@neondatabase/neon-js'
import type {
  WorkflowAccountPatch,
  WorkflowAccountState,
  WorkflowSavedView,
  WorkflowSnapshot,
  WorkflowUser,
  WorkflowWatchlist,
} from '../types/workflow'

const DEFAULT_AUTH_URL = 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech/neondb/auth'
const DEFAULT_DATA_API_URL = 'https://ep-silent-moon-au2icaki.apirest.c-10.us-east-1.aws.neon.tech/neondb/rest/v1'

const authUrl = import.meta.env.VITE_NEON_AUTH_URL || DEFAULT_AUTH_URL
const dataApiUrl = import.meta.env.VITE_NEON_DATA_API_URL || DEFAULT_DATA_API_URL

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

export async function getWorkflowSession(): Promise<WorkflowUser | null> {
  if (!workflowRuntimeEnabled) return null
  const result = await client.auth.getSession()
  throwIfError('Unable to load workflow session', result.error)
  if (!result.data?.session) return null
  return userFrom(result.data.user)
}

export async function signInWorkflow(email: string, password: string): Promise<WorkflowUser> {
  const result = await client.auth.signIn.email({ email, password, rememberMe: true })
  throwIfError('Unable to sign in', result.error)
  const user = userFrom(result.data?.user)
  if (!user) throw new Error('Unable to sign in: session user was not returned')
  return user
}

export async function signUpWorkflow(email: string, password: string): Promise<WorkflowUser> {
  const result = await client.auth.signUp.email({
    email,
    password,
    name: email.split('@')[0] || 'TowerSignal user',
  })
  throwIfError('Unable to create account', result.error)
  const user = userFrom(result.data?.user)
  if (!user) throw new Error('Unable to create account: session user was not returned')
  return user
}

export async function signOutWorkflow(): Promise<void> {
  const result = await client.auth.signOut()
  throwIfError('Unable to sign out', result.error)
}

export async function loadWorkflowSnapshot(): Promise<WorkflowSnapshot> {
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

  const savedViews = ((savedViewsResult.data ?? []) as Array<Record<string, unknown>>).map(row => ({
    id: String(row.view_id),
    name: String(row.name),
    filters: (row.filters ?? {}) as WorkflowSavedView['filters'],
    created_at: row.created_at == null ? undefined : String(row.created_at),
    updated_at: row.updated_at == null ? undefined : String(row.updated_at),
  }))
  const watchlists = ((watchlistsResult.data ?? []) as Array<Record<string, unknown>>).map(row => ({
    id: String(row.watchlist_id),
    name: String(row.name),
    created_at: row.created_at == null ? undefined : String(row.created_at),
    updated_at: row.updated_at == null ? undefined : String(row.updated_at),
  }))
  const accounts = ((accountsResult.data ?? []) as Array<Record<string, unknown>>).map(row => ({
    system_id: String(row.system_id),
    status: String(row.status) as WorkflowAccountState['status'],
    note: String(row.note ?? ''),
    next_action_date: row.next_action_date == null ? null : String(row.next_action_date),
    created_at: row.created_at == null ? undefined : String(row.created_at),
    updated_at: row.updated_at == null ? undefined : String(row.updated_at),
  }))
  const memberships = ((membershipsResult.data ?? []) as Array<Record<string, unknown>>).map(row => ({
    watchlist_id: String(row.watchlist_id),
    system_id: String(row.system_id),
    added_at: row.added_at == null ? undefined : String(row.added_at),
  }))
  return { savedViews, watchlists, accounts, memberships }
}

export async function saveRemoteView(view: WorkflowSavedView): Promise<void> {
  const now = new Date().toISOString()
  const update = await client.from('workflow_saved_views')
    .update({ name: view.name, filters: view.filters, updated_at: now })
    .eq('view_id', view.id)
    .select('view_id')
  throwIfError('Unable to update saved view', update.error)
  if ((update.data ?? []).length > 0) return
  const insert = await client.from('workflow_saved_views').insert({ view_id: view.id, name: view.name, filters: view.filters, updated_at: now })
  throwIfError('Unable to save view', insert.error)
}

export async function deleteRemoteView(viewId: string): Promise<void> {
  const result = await client.from('workflow_saved_views').delete().eq('view_id', viewId)
  throwIfError('Unable to delete saved view', result.error)
}

export async function createRemoteWatchlist(watchlist: WorkflowWatchlist): Promise<void> {
  const result = await client.from('workflow_watchlists').insert({ watchlist_id: watchlist.id, name: watchlist.name })
  throwIfError('Unable to create watchlist', result.error)
}

export async function deleteRemoteWatchlist(watchlistId: string): Promise<void> {
  const result = await client.from('workflow_watchlists').delete().eq('watchlist_id', watchlistId)
  throwIfError('Unable to delete watchlist', result.error)
}

export async function saveRemoteAccount(systemId: string, patch: WorkflowAccountPatch): Promise<void> {
  const now = new Date().toISOString()
  const values = { ...patch, next_action_date: patch.next_action_date || null, updated_at: now }
  const update = await client.from('workflow_accounts').update(values).eq('system_id', systemId).select('system_id')
  throwIfError('Unable to update account workflow state', update.error)
  if ((update.data ?? []).length > 0) return
  const insert = await client.from('workflow_accounts').insert({ system_id: systemId, ...values })
  throwIfError('Unable to save account workflow state', insert.error)
}

async function ensureRemoteAccount(systemId: string): Promise<void> {
  const existing = await client.from('workflow_accounts').select('system_id').eq('system_id', systemId).limit(1)
  throwIfError('Unable to check account workflow state', existing.error)
  if ((existing.data ?? []).length > 0) return
  const insert = await client.from('workflow_accounts').insert({ system_id: systemId })
  throwIfError('Unable to initialize account workflow state', insert.error)
}

export async function setRemoteMembership(systemId: string, watchlistId: string, enabled: boolean): Promise<void> {
  if (!enabled) {
    const remove = await client.from('workflow_watchlist_members').delete().eq('system_id', systemId).eq('watchlist_id', watchlistId)
    throwIfError('Unable to remove account from watchlist', remove.error)
    return
  }
  await ensureRemoteAccount(systemId)
  const existing = await client.from('workflow_watchlist_members').select('system_id').eq('system_id', systemId).eq('watchlist_id', watchlistId).limit(1)
  throwIfError('Unable to check watchlist membership', existing.error)
  if ((existing.data ?? []).length > 0) return
  const insert = await client.from('workflow_watchlist_members').insert({ system_id: systemId, watchlist_id: watchlistId })
  throwIfError('Unable to add account to watchlist', insert.error)
}
