import type { WorkflowAccountPatch, WorkflowSavedView, WorkflowUser, WorkflowWatchlist } from '../types/workflow'
import * as remote from './remoteClient'

export const workflowRuntimeEnabled = import.meta.env.MODE !== 'test'

export async function getWorkflowSession() {
  return remote.getWorkflowSession()
}

export async function signInWorkflow(email: string, password: string): Promise<WorkflowUser> {
  return remote.signInWorkflow(email, password)
}

export async function signUpWorkflow(email: string, password: string, name?: string): Promise<WorkflowUser> {
  return remote.signUpWorkflow(email, password, name)
}

export async function signOutWorkflow(): Promise<void> {
  return remote.signOutWorkflow()
}

export async function loadWorkflowSnapshot() {
  return remote.loadWorkflowSnapshot()
}

export async function saveRemoteView(view: WorkflowSavedView): Promise<void> {
  return remote.saveRemoteView(view)
}

export async function deleteRemoteView(viewId: string): Promise<void> {
  return remote.deleteRemoteView(viewId)
}

export async function createRemoteWatchlist(watchlist: WorkflowWatchlist): Promise<void> {
  return remote.createRemoteWatchlist(watchlist)
}

export async function deleteRemoteWatchlist(watchlistId: string): Promise<void> {
  return remote.deleteRemoteWatchlist(watchlistId)
}

export async function saveRemoteAccount(systemId: string, patch: WorkflowAccountPatch): Promise<void> {
  return remote.saveRemoteAccount(systemId, patch)
}

export async function setRemoteMembership(systemId: string, watchlistId: string, enabled: boolean): Promise<void> {
  return remote.setRemoteMembership(systemId, watchlistId, enabled)
}
