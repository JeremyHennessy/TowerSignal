import { useEffect, useState } from 'react'

type Patch = Record<string, string | null>

export function adminViewHref(hash: string, patch: Patch): string {
  const [path, query = ''] = hash.split('?')
  const params = new URLSearchParams(query)
  for (const [key, value] of Object.entries(patch)) {
    if (value === null || value === '') params.delete(key)
    else params.set(key, value)
  }
  return `${path || '#/admin-companies'}${params.size ? `?${params}` : ''}`
}

// Native links preserve copy/open-in-new-tab behavior and browser history.
export function useAdminNavigation() {
  const [hash, setHash] = useState(() => window.location.hash)
  useEffect(() => {
    const sync = () => setHash(window.location.hash)
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])
  const params = new URLSearchParams(hash.split('?')[1] ?? '')
  const href = (patch: Patch) => adminViewHref(hash, patch)
  const update = (patch: Patch, replace = false) => {
    const next = adminViewHref(window.location.hash, patch)
    if (replace) window.history.replaceState(null, '', next)
    else window.history.pushState(null, '', next)
    window.dispatchEvent(new HashChangeEvent('hashchange'))
  }
  const choice = <T extends string>(key: string, values: readonly T[], fallback: T): T => {
    const value = params.get(key) as T | null
    return value && values.includes(value) ? value : fallback
  }
  return { params, href, update, choice }
}
