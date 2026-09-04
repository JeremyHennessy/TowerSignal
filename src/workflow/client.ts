import type { WorkflowAccountPatch, WorkflowSavedView, WorkflowUser, WorkflowWatchlist } from '../types/workflow'

export const workflowRuntimeEnabled = import.meta.env.MODE !== 'test' && import.meta.env.VITE_TORONTO_PREVIEW !== 'true'

const loadRemote = () => import('./remoteClient')

export async function getWorkflowSession() {
  return (await loadRemote()).getWorkflowSession()
}

export async function signInWorkflow(email: string, password: string): Promise<WorkflowUser> {
  return (await loadRemote()).signInWorkflow(email, password)
}

export async function signUpWorkflow(email: string, password: string, name?: string): Promise<WorkflowUser> {
  return (await loadRemote()).signUpWorkflow(email, password, name)
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
