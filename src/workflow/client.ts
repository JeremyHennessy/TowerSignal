import type { WorkflowAccountPatch, WorkflowAccountState, WorkflowMembership, WorkflowSavedView, WorkflowUser, WorkflowWatchlist } from '../types/workflow'

export const workflowRuntimeEnabled = true

const USER_KEY = 'towersignal.visual-proof.user'
const SNAPSHOT_KEY = 'towersignal.visual-proof.snapshot'

type Snapshot = {
  savedViews: WorkflowSavedView[]
  watchlists: WorkflowWatchlist[]
  accounts: WorkflowAccountState[]
  memberships: WorkflowMembership[]
}

function emptySnapshot(): Snapshot {
  return { savedViews: [], watchlists: [], accounts: [], memberships: [] }
}

function readSnapshot(): Snapshot {
  try {
    const raw = window.localStorage.getItem(SNAPSHOT_KEY)
    return raw ? { ...emptySnapshot(), ...JSON.parse(raw) } : emptySnapshot()
  } catch {
    return emptySnapshot()
  }
}

function writeSnapshot(snapshot: Snapshot) {
  window.localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(snapshot))
}

function visualUser(email = 'workflow-visual@example.com', name = 'Workflow Visual QA'): WorkflowUser {
  return { id: 'visual-user', email, name }
}

export async function getWorkflowSession(): Promise<WorkflowUser | null> {
  try {
    const raw = window.localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) as WorkflowUser : null
  } catch {
    return null
  }
}

export async function signInWorkflow(email: string, _password: string): Promise<WorkflowUser> {
  const user = visualUser(email)
  window.localStorage.setItem(USER_KEY, JSON.stringify(user))
  return user
}

export async function signUpWorkflow(email: string, _password: string, name?: string): Promise<WorkflowUser> {
  const user = visualUser(email, name || 'Workflow Visual QA')
  window.localStorage.setItem(USER_KEY, JSON.stringify(user))
  writeSnapshot(emptySnapshot())
  return user
}

export async function signOutWorkflow(): Promise<void> {
  window.localStorage.removeItem(USER_KEY)
}

export async function loadWorkflowSnapshot(): Promise<Snapshot> {
  return readSnapshot()
}

export async function saveRemoteView(view: WorkflowSavedView): Promise<void> {
  const snapshot = readSnapshot()
  snapshot.savedViews = [...snapshot.savedViews.filter(item => item.id !== view.id), view]
  writeSnapshot(snapshot)
}

export async function deleteRemoteView(viewId: string): Promise<void> {
  const snapshot = readSnapshot()
  snapshot.savedViews = snapshot.savedViews.filter(item => item.id !== viewId)
  writeSnapshot(snapshot)
}

export async function createRemoteWatchlist(watchlist: WorkflowWatchlist): Promise<void> {
  const snapshot = readSnapshot()
  snapshot.watchlists = [...snapshot.watchlists.filter(item => item.id !== watchlist.id), watchlist]
  writeSnapshot(snapshot)
}

export async function deleteRemoteWatchlist(watchlistId: string): Promise<void> {
  const snapshot = readSnapshot()
  snapshot.watchlists = snapshot.watchlists.filter(item => item.id !== watchlistId)
  snapshot.memberships = snapshot.memberships.filter(item => item.watchlist_id !== watchlistId)
  writeSnapshot(snapshot)
}

export async function saveRemoteAccount(systemId: string, patch: WorkflowAccountPatch): Promise<void> {
  const snapshot = readSnapshot()
  const next: WorkflowAccountState = { system_id: systemId, ...patch, updated_at: new Date().toISOString() }
  snapshot.accounts = [...snapshot.accounts.filter(item => item.system_id !== systemId), next]
  writeSnapshot(snapshot)
}

export async function setRemoteMembership(systemId: string, watchlistId: string, enabled: boolean): Promise<void> {
  const snapshot = readSnapshot()
  snapshot.memberships = enabled
    ? snapshot.memberships.some(item => item.system_id === systemId && item.watchlist_id === watchlistId)
      ? snapshot.memberships
      : [...snapshot.memberships, { system_id: systemId, watchlist_id: watchlistId, added_at: new Date().toISOString() }]
    : snapshot.memberships.filter(item => !(item.system_id === systemId && item.watchlist_id === watchlistId))
  writeSnapshot(snapshot)
}
