import type { SystemDetail, SystemsPayload } from '../types/data'

const base = import.meta.env.BASE_URL

export async function loadSystems(): Promise<SystemsPayload> {
  const response = await fetch(`${base}data/systems.json`, { cache: 'no-store' })
  if (!response.ok) throw new Error(`TowerSignal dataset request failed: HTTP ${response.status}`)
  const payload = await response.json() as SystemsPayload
  if (!payload?.metadata || !Array.isArray(payload?.systems)) throw new Error('TowerSignal dataset is malformed')
  return payload
}

export function systemDetailUrl(systemId: string): string {
  const safe = [...systemId].filter((ch) => /[A-Za-z0-9_-]/.test(ch)).join('')
  const prefix = (safe.slice(0, 2) || 'xx').toLowerCase()
  return `${base}data/details/${prefix}/${encodeURIComponent(safe)}.json`
}

export async function loadSystemDetail(systemId: string): Promise<SystemDetail> {
  const response = await fetch(systemDetailUrl(systemId), { cache: 'no-store' })
  if (!response.ok) throw new Error(`System detail request failed: HTTP ${response.status}`)
  return response.json() as Promise<SystemDetail>
}
