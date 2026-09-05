import { useCallback, useEffect, useMemo, useState } from 'react'
import { initialFilters, type FilterState } from '../components/Filters'
import type {
  WorkflowAccountPatch,
  WorkflowAccountState,
  WorkflowMembership,
  WorkflowSavedView,
  WorkflowSnapshot,
  WorkflowUser,
  WorkflowWatchlist,
} from '../types/workflow'
import {
  createRemoteWatchlist,
  deleteRemoteView,
  deleteRemoteWatchlist,
  getWorkflowSession,
  loadWorkflowSnapshot,
  saveRemoteAccount,
  saveRemoteView,
  setRemoteMembership,
  signInWorkflow,
  signOutWorkflow,
  signUpWorkflow,
  workflowRuntimeEnabled,
} from './client'

const SAVED_VIEWS_KEY = 'towersignal.savedViews.v1'
const LOCAL_WORKFLOW_PREFIX = 'towersignal.workflow.local.v1'

export type WorkflowSyncMode = 'remote' | 'local' | 'signed-out'

type LocalPrivateSnapshot = Pick<WorkflowSnapshot, 'watchlists' | 'accounts' | 'memberships'>

function readLocalViews(): WorkflowSavedView[] {
  try {
    const raw = window.localStorage.getItem(SAVED_VIEWS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as Array<Partial<WorkflowSavedView>>
    if (!Array.isArray(parsed)) return []
    return parsed
      .filter(view => typeof view.id === 'string' && typeof view.name === 'string')
      .map(view => ({
        id: view.id as string,
        name: view.name as string,
        filters: { ...initialFilters, ...((view.filters ?? {}) as Partial<FilterState>) },
      }))
  } catch {
    return []
  }
}

function writeLocalViews(views: WorkflowSavedView[]): void {
  window.localStorage.setItem(SAVED_VIEWS_KEY, JSON.stringify(views.map(({ id, name, filters }) => ({ id, name, filters }))))
}

function localWorkflowKey(userId: string): string {
  return `${LOCAL_WORKFLOW_PREFIX}:${userId}`
}

function readLocalPrivateSnapshot(userId: string): LocalPrivateSnapshot {
  try {
    const raw = window.localStorage.getItem(localWorkflowKey(userId))
    if (!raw) return { watchlists: [], accounts: [], memberships: [] }
    const parsed = JSON.parse(raw) as Partial<LocalPrivateSnapshot>
    return {
      watchlists: Array.isArray(parsed.watchlists) ? parsed.watchlists : [],
      accounts: Array.isArray(parsed.accounts) ? parsed.accounts : [],
      memberships: Array.isArray(parsed.memberships) ? parsed.memberships : [],
    }
  } catch {
    return { watchlists: [], accounts: [], memberships: [] }
  }
}

function writeLocalPrivateSnapshot(userId: string, snapshot: LocalPrivateSnapshot): void {
  window.localStorage.setItem(localWorkflowKey(userId), JSON.stringify(snapshot))
}

function id(prefix: string): string {
  const random = globalThis.crypto?.randomUUID?.()
  return `${prefix}-${random ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`}`
}

function syncUnavailableMessage(error: unknown): string {
  const detail = error instanceof Error ? error.message : String(error || '')
  return detail
    ? `Remote workflow sync is unavailable in this browser (${detail}).`
    : 'Remote workflow sync is unavailable in this browser.'
}

export function useWorkflow(initialUser: WorkflowUser | null = null) {
  const [user, setUser] = useState<WorkflowUser | null>(initialUser)
  const [savedViews, setSavedViews] = useState<WorkflowSavedView[]>(readLocalViews)
  const [watchlists, setWatchlists] = useState<WorkflowWatchlist[]>([])
  const [accounts, setAccounts] = useState<WorkflowAccountState[]>([])
  const [memberships, setMemberships] = useState<WorkflowMembership[]>([])
  const [syncMode, setSyncMode] = useState<WorkflowSyncMode>(initialUser ? 'remote' : 'signed-out')
  const [syncWarning, setSyncWarning] = useState<string | null>(null)
  const [loading, setLoading] = useState(workflowRuntimeEnabled)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const hydrateLocal = useCallback((sessionUser: WorkflowUser, reason: unknown) => {
    const local = readLocalPrivateSnapshot(sessionUser.id)
    const normalizedWatchlists = local.watchlists.length > 0
      ? local.watchlists
      : [{ id: 'default', name: 'My watchlist' } satisfies WorkflowWatchlist]
    if (local.watchlists.length === 0) {
      writeLocalPrivateSnapshot(sessionUser.id, { ...local, watchlists: normalizedWatchlists })
    }
    setUser(sessionUser)
    setSavedViews(readLocalViews())
    setWatchlists(normalizedWatchlists)
    setAccounts(local.accounts)
    setMemberships(local.memberships)
    setSyncMode('local')
    setSyncWarning(syncUnavailableMessage(reason))
    setError(null)
  }, [])

  const hydrateRemote = useCallback(async (sessionUser: WorkflowUser) => {
    let snapshot = await loadWorkflowSnapshot()
    const localViews = readLocalViews()
    const remoteIds = new Set(snapshot.savedViews.map(view => view.id))
    const remoteNames = new Set(snapshot.savedViews.map(view => view.name.trim().toLowerCase()))
    const localOnlyViews = localViews.filter(view => !remoteIds.has(view.id) && !remoteNames.has(view.name.trim().toLowerCase()))
    if (localOnlyViews.length > 0) {
      for (const view of localOnlyViews) await saveRemoteView(view)
      snapshot = await loadWorkflowSnapshot()
    }
    if (snapshot.watchlists.length === 0) {
      await createRemoteWatchlist({ id: 'default', name: 'My watchlist' })
      snapshot = await loadWorkflowSnapshot()
    }
    const normalizedViews = snapshot.savedViews.map(view => ({ ...view, filters: { ...initialFilters, ...view.filters } }))
    setUser(sessionUser)
    setSavedViews(normalizedViews)
    setWatchlists(snapshot.watchlists)
    setAccounts(snapshot.accounts)
    setMemberships(snapshot.memberships)
    setSyncMode('remote')
    setSyncWarning(null)
    setError(null)
  }, [])

  const hydrateAuthenticated = useCallback(async (sessionUser: WorkflowUser) => {
    try {
      await hydrateRemote(sessionUser)
    } catch (err) {
      // AuthGate has already authenticated this tab. On Safari/WebKit, the
      // cross-site Managed Better Auth cookie can still be unavailable to the
      // Neon Data API. Keep private workflow usable without weakening RLS by
      // falling back to user-keyed on-device storage for this browser only.
      hydrateLocal(sessionUser, err)
    }
  }, [hydrateLocal, hydrateRemote])

  useEffect(() => {
    if (!workflowRuntimeEnabled) {
      setLoading(false)
      return
    }
    const initialize = async () => {
      try {
        const sessionUser = initialUser ?? await getWorkflowSession()
        if (sessionUser) await hydrateAuthenticated(sessionUser)
        else {
          setUser(null)
          setSyncMode('signed-out')
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to initialize workflow sync')
      } finally {
        setLoading(false)
      }
    }
    void initialize()
  }, [hydrateAuthenticated, initialUser])

  const signIn = useCallback(async (email: string, password: string) => {
    setBusy(true); setError(null)
    try {
      const sessionUser = await signInWorkflow(email, password)
      await hydrateAuthenticated(sessionUser)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in')
      throw err
    } finally {
      setBusy(false)
    }
  }, [hydrateAuthenticated])

  const signUp = useCallback(async (email: string, password: string) => {
    setBusy(true); setError(null)
    try {
      const sessionUser = await signUpWorkflow(email, password)
      await hydrateAuthenticated(sessionUser)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create account')
      throw err
    } finally {
      setBusy(false)
    }
  }, [hydrateAuthenticated])

  const signOut = useCallback(async () => {
    setBusy(true); setError(null)
    try {
      await signOutWorkflow()
    } catch (err) {
      if (syncMode === 'remote') setError(err instanceof Error ? err.message : 'Unable to sign out remotely')
    } finally {
      setUser(null)
      setWatchlists([])
      setAccounts([])
      setMemberships([])
      setSavedViews(readLocalViews())
      setSyncMode('signed-out')
      setSyncWarning(null)
      setBusy(false)
    }
  }, [syncMode])

  const saveView = useCallback(async (nameValue: string, filters: FilterState) => {
    const name = nameValue.trim()
    if (!name) return
    const existing = savedViews.find(view => view.name.toLowerCase() === name.toLowerCase())
    const view: WorkflowSavedView = { id: existing?.id ?? id('view'), name, filters: { ...filters } }
    const next = [...savedViews.filter(item => item.id !== view.id && item.name.toLowerCase() !== name.toLowerCase()), view]
    setSavedViews(next)
    if (!user || syncMode === 'local') {
      writeLocalViews(next)
      return
    }
    setBusy(true); setError(null)
    try { await saveRemoteView(view) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to sync saved view'); throw err }
    finally { setBusy(false) }
  }, [savedViews, syncMode, user])

  const deleteView = useCallback(async (viewId: string) => {
    const next = savedViews.filter(view => view.id !== viewId)
    setSavedViews(next)
    if (!user || syncMode === 'local') {
      writeLocalViews(next)
      return
    }
    setBusy(true); setError(null)
    try { await deleteRemoteView(viewId) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to delete saved view'); throw err }
    finally { setBusy(false) }
  }, [savedViews, syncMode, user])

  const createWatchlist = useCallback(async (nameValue: string) => {
    const name = nameValue.trim()
    if (!name || !user) return
    const watchlist: WorkflowWatchlist = { id: id('watchlist'), name }
    if (syncMode === 'local') {
      const next = [...watchlists, watchlist]
      setWatchlists(next)
      writeLocalPrivateSnapshot(user.id, { watchlists: next, accounts, memberships })
      return
    }
    setBusy(true); setError(null)
    try {
      await createRemoteWatchlist(watchlist)
      setWatchlists(current => [...current, watchlist])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create watchlist')
      throw err
    } finally { setBusy(false) }
  }, [accounts, memberships, syncMode, user, watchlists])

  const deleteWatchlist = useCallback(async (watchlistId: string) => {
    if (!user) return
    if (syncMode === 'local') {
      const nextWatchlists = watchlists.filter(item => item.id !== watchlistId)
      const nextMemberships = memberships.filter(item => item.watchlist_id !== watchlistId)
      setWatchlists(nextWatchlists)
      setMemberships(nextMemberships)
      writeLocalPrivateSnapshot(user.id, { watchlists: nextWatchlists, accounts, memberships: nextMemberships })
      return
    }
    setBusy(true); setError(null)
    try {
      await deleteRemoteWatchlist(watchlistId)
      setWatchlists(current => current.filter(item => item.id !== watchlistId))
      setMemberships(current => current.filter(item => item.watchlist_id !== watchlistId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to delete watchlist')
      throw err
    } finally { setBusy(false) }
  }, [accounts, memberships, syncMode, user, watchlists])

  const saveAccount = useCallback(async (systemId: string, patch: WorkflowAccountPatch) => {
    if (!user) return
    const nextAccount: WorkflowAccountState = { system_id: systemId, ...patch, updated_at: new Date().toISOString() }
    if (syncMode === 'local') {
      const nextAccounts = [...accounts.filter(item => item.system_id !== systemId), nextAccount]
      setAccounts(nextAccounts)
      writeLocalPrivateSnapshot(user.id, { watchlists, accounts: nextAccounts, memberships })
      return
    }
    setBusy(true); setError(null)
    try {
      await saveRemoteAccount(systemId, patch)
      setAccounts(current => [...current.filter(item => item.system_id !== systemId), nextAccount])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save account workflow state')
      throw err
    } finally { setBusy(false) }
  }, [accounts, memberships, syncMode, user, watchlists])

  const toggleMembership = useCallback(async (systemId: string, watchlistId: string, enabled: boolean) => {
    if (!user) return
    const nextMemberships = enabled
      ? memberships.some(item => item.system_id === systemId && item.watchlist_id === watchlistId)
        ? memberships
        : [...memberships, { system_id: systemId, watchlist_id: watchlistId, added_at: new Date().toISOString() }]
      : memberships.filter(item => !(item.system_id === systemId && item.watchlist_id === watchlistId))
    if (syncMode === 'local') {
      setMemberships(nextMemberships)
      writeLocalPrivateSnapshot(user.id, { watchlists, accounts, memberships: nextMemberships })
      return
    }
    setBusy(true); setError(null)
    try {
      await setRemoteMembership(systemId, watchlistId, enabled)
      setMemberships(nextMemberships)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update watchlist')
      throw err
    } finally { setBusy(false) }
  }, [accounts, memberships, syncMode, user, watchlists])

  const accountBySystemId = useMemo(() => new Map(accounts.map(account => [account.system_id, account])), [accounts])
  const watchedSystemIds = useMemo(() => new Set(memberships.map(item => item.system_id)), [memberships])
  const watchlistIdsBySystemId = useMemo(() => {
    const map = new Map<string, Set<string>>()
    memberships.forEach(item => {
      const ids = map.get(item.system_id) ?? new Set<string>()
      ids.add(item.watchlist_id)
      map.set(item.system_id, ids)
    })
    return map
  }, [memberships])

  return {
    runtimeEnabled: workflowRuntimeEnabled,
    user,
    loading,
    busy,
    error,
    syncMode,
    syncWarning,
    savedViews,
    watchlists,
    accounts,
    memberships,
    accountBySystemId,
    watchedSystemIds,
    watchlistIdsBySystemId,
    signIn,
    signUp,
    signOut,
    saveView,
    deleteView,
    createWatchlist,
    deleteWatchlist,
    saveAccount,
    toggleMembership,
  }
}
