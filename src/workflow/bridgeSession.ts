import type { WorkflowUser } from '../types/workflow'

const REFRESH_KEY = 'towersignal.workflow.bridge-refresh.v1'
const EXPIRY_SKEW_SECONDS = 60

type BridgePayload = {
  user?: unknown
  token?: unknown
  refresh?: unknown
  error?: unknown
}

let accessToken: string | null = null
let accessTokenExpiresAt = 0
let currentUser: WorkflowUser | null = null
let refreshPromise: Promise<WorkflowUser | null> | null = null

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

function storage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.sessionStorage
  } catch {
    return null
  }
}

function readRefresh(): string | null {
  try {
    return storage()?.getItem(REFRESH_KEY) || null
  } catch {
    return null
  }
}

function writeRefresh(value: string | null): void {
  try {
    const target = storage()
    if (!target) return
    if (value) target.setItem(REFRESH_KEY, value)
    else target.removeItem(REFRESH_KEY)
  } catch {
    // A blocked storage surface means the session remains tab-memory only.
  }
}

function clearMemory(): void {
  accessToken = null
  accessTokenExpiresAt = 0
  currentUser = null
}

function jwtExpiry(token: string): number {
  try {
    const part = token.split('.')[1]
    if (!part) return 0
    const normalized = part.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized + '='.repeat((4 - normalized.length % 4) % 4)
    const payload = JSON.parse(atob(padded)) as { exp?: unknown }
    return Number(payload.exp || 0)
  } catch {
    return 0
  }
}

function errorMessage(payload: BridgePayload | null, fallback: string): string {
  const value = payload?.error
  if (typeof value === 'string' && value.trim()) return value
  if (value && typeof value === 'object' && 'message' in value) return String((value as { message?: unknown }).message || fallback)
  return fallback
}

async function bridgeRequest(bridgeUrl: string, path: string, init: { body?: Record<string, unknown>; refresh?: string } = {}): Promise<BridgePayload> {
  const response = await fetch(`${bridgeUrl.replace(/\/$/, '')}${path}`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      ...(init.refresh ? { authorization: `Bearer ${init.refresh}` } : {}),
    },
    body: JSON.stringify(init.body ?? {}),
    cache: 'no-store',
  })
  let payload: BridgePayload | null = null
  try {
    payload = await response.json() as BridgePayload
  } catch {
    payload = null
  }
  if (!response.ok) throw new Error(errorMessage(payload, `Workflow authentication failed (HTTP ${response.status})`))
  return payload ?? {}
}

function acceptPayload(payload: BridgePayload): WorkflowUser {
  const user = userFrom(payload.user)
  const token = typeof payload.token === 'string' ? payload.token : null
  const refresh = typeof payload.refresh === 'string' ? payload.refresh : null
  if (!user || !token || !refresh) throw new Error('Workflow authentication response was incomplete')
  accessToken = token
  accessTokenExpiresAt = jwtExpiry(token)
  currentUser = user
  writeRefresh(refresh)
  return user
}

export async function bridgeSignIn(bridgeUrl: string, email: string, password: string): Promise<WorkflowUser> {
  const payload = await bridgeRequest(bridgeUrl, '/sign-in', { body: { email, password } })
  return acceptPayload(payload)
}

export async function bridgeSignUp(bridgeUrl: string, email: string, password: string, name?: string): Promise<WorkflowUser> {
  const payload = await bridgeRequest(bridgeUrl, '/sign-up', {
    body: { email, password, name: name?.trim() || email.split('@')[0] || 'TowerSignal user' },
  })
  return acceptPayload(payload)
}

export async function bridgeGetSession(bridgeUrl: string, forceRefresh = false): Promise<WorkflowUser | null> {
  const now = Math.floor(Date.now() / 1000)
  if (!forceRefresh && currentUser && accessToken && accessTokenExpiresAt > now + EXPIRY_SKEW_SECONDS) return currentUser
  const refresh = readRefresh()
  if (!refresh) {
    clearMemory()
    return null
  }
  if (!refreshPromise) {
    refreshPromise = (async () => {
      try {
        const payload = await bridgeRequest(bridgeUrl, '/session', { refresh })
        return acceptPayload(payload)
      } catch (error) {
        writeRefresh(null)
        clearMemory()
        throw error
      } finally {
        refreshPromise = null
      }
    })()
  }
  return refreshPromise
}

export async function bridgeAccessToken(bridgeUrl: string, forceRefresh = false): Promise<string> {
  const user = await bridgeGetSession(bridgeUrl, forceRefresh)
  if (!user || !accessToken) throw new Error('Workflow session is not authenticated')
  return accessToken
}

export async function bridgeSignOut(bridgeUrl: string): Promise<void> {
  const refresh = readRefresh()
  try {
    if (refresh) await bridgeRequest(bridgeUrl, '/sign-out', { refresh })
  } finally {
    writeRefresh(null)
    clearMemory()
  }
}

export function clearBridgeSession(): void {
  writeRefresh(null)
  clearMemory()
}
