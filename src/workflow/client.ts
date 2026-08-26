import type { WorkflowAccountPatch, WorkflowSavedView, WorkflowUser, WorkflowWatchlist } from '../types/workflow'

const DEFAULT_AUTH_URL = 'https://ep-silent-moon-au2icaki.neonauth.c-10.us-east-1.aws.neon.tech/neondb/auth'
const authUrl = import.meta.env.VITE_NEON_AUTH_URL || DEFAULT_AUTH_URL

export const workflowRuntimeEnabled = import.meta.env.MODE !== 'test'

const loadRemote = () => import('./remoteClient')

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
  const response = await fetch(`${authUrl}/get-session`, {
    credentials: 'include',
    headers: { accept: 'application/json' },
  })
  if (!response.ok) throw new Error(`Unable to load workflow session: HTTP ${response.status}`)
  const value = await response.json() as { session?: unknown; user?: unknown } | null
  if (!value?.session) return null
  return userFrom(value.user)
}

export async function signInWorkflow(email: string, password: string): Promise<WorkflowUser> {
  return (await loadRemote()).signInWorkflow(email, password)
}

export async function signUpWorkflow(email: string, password: string): Promise<WorkflowUser> {
  return (await loadRemote()).signUpWorkflow(email, password)
}

export async function signOutWorkflow(): Promise<void> {
  return (await loadRemote()).signOutWorkflow()
}

export async function loadWorkflowSnapshot() {
  return (await loadRemote()).loadWorkflowSnapshot()
}

export async function saveRemoteView(view: WorkflowSavedView): Promise<void> {
  return (await loadRemote()).saveRemoteView(view)
}

export async function deleteRemoteView(viewId: string): Promise<void> {
  return (await loadRemote()).deleteRemoteView(viewId)
}

export async function createRemoteWatchlist(watchlist: WorkflowWatchlist): Promise<void> {
  return (await loadRemote()).createRemoteWatchlist(watchlist)
}

export async function deleteRemoteWatchlist(watchlistId: string): Promise<void> {
  return (await loadRemote()).deleteRemoteWatchlist(watchlistId)
}

export async function saveRemoteAccount(systemId: string, patch: WorkflowAccountPatch): Promise<void> {
  return (await loadRemote()).saveRemoteAccount(systemId, patch)
}

export async function setRemoteMembership(systemId: string, watchlistId: string, enabled: boolean): Promise<void> {
  return (await loadRemote()).setRemoteMembership(systemId, watchlistId, enabled)
}
