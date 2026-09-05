import type { FilterState } from '../components/Filters'

export type AccountDisposition = 'new' | 'investigate' | 'contacted' | 'follow-up' | 'monitor' | 'dismissed'

export interface WorkflowUser {
  id: string
  email: string
  name: string | null
  workflow_sync_mode?: 'remote' | 'local'
  workflow_sync_warning?: string | null
}

export interface WorkflowSavedView {
  id: string
  name: string
  filters: FilterState
  created_at?: string
  updated_at?: string
}

export interface WorkflowWatchlist {
  id: string
  name: string
  created_at?: string
  updated_at?: string
}

export interface WorkflowAccountState {
  system_id: string
  status: AccountDisposition
  note: string
  next_action_date: string | null
  created_at?: string
  updated_at?: string
}

export interface WorkflowMembership {
  watchlist_id: string
  system_id: string
  added_at?: string
}

export interface WorkflowSnapshot {
  savedViews: WorkflowSavedView[]
  watchlists: WorkflowWatchlist[]
  accounts: WorkflowAccountState[]
  memberships: WorkflowMembership[]
}

export interface WorkflowAccountPatch {
  status: AccountDisposition
  note: string
  next_action_date: string | null
}
