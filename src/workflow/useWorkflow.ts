import { useCallback, useEffect, useMemo, useState } from 'react'
import { initialFilters, type FilterState } from '../components/Filters'
import type {
  WorkflowAccountPatch,
  WorkflowAccountState,
  WorkflowMembership,
  WorkflowSavedView,
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

function id(prefix: string): string {
  const random = globalThis.crypto?.randomUUID?.()
  return `${prefix}-${random ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`}`
}

export function useWorkflow() {
  const [user, setUser] = useState<WorkflowUser | null>(null)
  const [savedViews, setSavedViews] = useState<WorkflowSavedView[]>(readLocalViews)
  const [watchlists, setWatchlists] = useState<WorkflowWatchlist[]>([])
  const [accounts, setAccounts] = useState<WorkflowAccountState[]>([])
  const [memberships, setMemberships] = useState<WorkflowMembership[]>([])
  const [loading, setLoading] = useState(workflowRuntimeEnabled)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
  }, [])

  useEffect(() => {
    if (!workflowRuntimeEnabled) {
      setLoading(false)
      return
    }
    getWorkflowSession()
      .then(async sessionUser => {
        if (sessionUser) await hydrateRemote(sessionUser)
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Unable to initialize workflow sync'))
      .finally(() => setLoading(false))
  }, [hydrateRemote])

  const signIn = useCallback(async (email: string, password: string) => {
    setBusy(true); setError(null)
    try {
      const sessionUser = await signInWorkflow(email, password)
      await hydrateRemote(sessionUser)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign in')
      throw err
    } finally {
      setBusy(false)
    }
  }, [hydrateRemote])

  const signUp = useCallback(async (email: string, password: string) => {
    setBusy(true); setError(null)
    try {
      const sessionUser = await signUpWorkflow(email, password)
      await hydrateRemote(sessionUser)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create account')
      throw err
    } finally {
      setBusy(false)
    }
  }, [hydrateRemote])

  const signOut = useCallback(async () => {
    setBusy(true); setError(null)
    try {
      await signOutWorkflow()
      setUser(null)
      setWatchlists([])
      setAccounts([])
      setMemberships([])
      setSavedViews(readLocalViews())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to sign out')
    } finally {
      setBusy(false)
    }
  }, [])

  const saveView = useCallback(async (nameValue: string, filters: FilterState) => {
    const name = nameValue.trim()
    if (!name) return
    const existing = savedViews.find(view => view.name.toLowerCase() === name.toLowerCase())
    const view: WorkflowSavedView = { id: existing?.id ?? id('view'), name, filters: { ...filters } }
    const next = [...savedViews.filter(item => item.id !== view.id && item.name.toLowerCase() !== name.toLowerCase()), view]
    setSavedViews(next)
    if (!user) {
      writeLocalViews(next)
      return
    }
    setBusy(true); setError(null)
    try { await saveRemoteView(view) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to sync saved view') }
    finally { setBusy(false) }
  }, [savedViews, user])

  const deleteView = useCallback(async (viewId: string) => {
    const next = savedViews.filter(view => view.id !== viewId)
    setSavedViews(next)
    if (!user) {
      writeLocalViews(next)
      return
    }
    setBusy(true); setError(null)
    try { await deleteRemoteView(viewId) }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to delete saved view') }
    finally { setBusy(false) }
  }, [savedViews, user])

  const createWatchlist = useCallback(async (nameValue: string) => {
    const name = nameValue.trim()
    if (!name || !user) return
    const watchlist: WorkflowWatchlist = { id: id('watchlist'), name }
    setBusy(true); setError(null)
    try {
      await createRemoteWatchlist(watchlist)
      setWatchlists(current => [...current, watchlist])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to create watchlist')
    } finally { setBusy(false) }
  }, [user])

  const deleteWatchlist = useCallback(async (watchlistId: string) => {
    if (!user) return
    setBusy(true); setError(null)
    try {
      await deleteRemoteWatchlist(watchlistId)
      setWatchlists(current => current.filter(item => item.id !== watchlistId))
      setMemberships(current => current.filter(item => item.watchlist_id !== watchlistId))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to delete watchlist')
    } finally { setBusy(false) }
  }, [user])

  const saveAccount = useCallback(async (systemId: string, patch: WorkflowAccountPatch) => {
    if (!user) return
    setBusy(true); setError(null)
    try {
      await saveRemoteAccount(systemId, patch)
      setAccounts(current => {
        const next: WorkflowAccountState = { system_id: systemId, ...patch, updated_at: new Date().toISOString() }
        return [...current.filter(item => item.system_id !== systemId), next]
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to save account workflow state')
    } finally { setBusy(false) }
  }, [user])

  const toggleMembership = useCallback(async (systemId: string, watchlistId: string, enabled: boolean) => {
    if (!user) return
    setBusy(true); setError(null)
    try {
      await setRemoteMembership(systemId, watchlistId, enabled)
      setMemberships(current => enabled
        ? current.some(item => item.system_id === systemId && item.watchlist_id === watchlistId)
          ? current
          : [...current, { system_id: systemId, watchlist_id: watchlistId, added_at: new Date().toISOString() }]
        : current.filter(item => !(item.system_id === systemId && item.watchlist_id === watchlistId)))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to update watchlist')
    } finally { setBusy(false) }
  }, [user])

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
