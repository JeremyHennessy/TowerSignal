import type { WorkflowAccountPatch, WorkflowSavedView, WorkflowUser, WorkflowWatchlist } from '../types/workflow'

export const workflowRuntimeEnabled = import.meta.env.MODE !== 'test'

const loadClient = () => import('./client')

export async function getWorkflowSession() {
  return (await loadClient()).getWorkflowSession()
}

export async function signInWorkflow(email: string, password: string): Promise<WorkflowUser> {
  return (await loadClient()).signInWorkflow(email, password)
}

export async function signUpWorkflow(email: string, password: string): Promise<WorkflowUser> {
  return (await loadClient()).signUpWorkflow(email, password)
}

export async function signOutWorkflow(): Promise<void> {
  return (await loadClient()).signOutWorkflow()
}

export async function loadWorkflowSnapshot() {
  return (await loadClient()).loadWorkflowSnapshot()
}

export async function saveRemoteView(view: WorkflowSavedView): Promise<void> {
  return (await loadClient()).saveRemoteView(view)
}

export async function deleteRemoteView(viewId: string): Promise<void> {
  return (await loadClient()).deleteRemoteView(viewId)
}

export async function createRemoteWatchlist(watchlist: WorkflowWatchlist): Promise<void> {
  return (await loadClient()).createRemoteWatchlist(watchlist)
}

export async function deleteRemoteWatchlist(watchlistId: string): Promise<void> {
  return (await loadClient()).deleteRemoteWatchlist(watchlistId)
}

export async function saveRemoteAccount(systemId: string, patch: WorkflowAccountPatch): Promise<void> {
  return (await loadClient()).saveRemoteAccount(systemId, patch)
}

export async function setRemoteMembership(systemId: string, watchlistId: string, enabled: boolean): Promise<void> {
  return (await loadClient()).setRemoteMembership(systemId, watchlistId, enabled)
}
