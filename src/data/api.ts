import type { SystemDetail, SystemsPayload } from '../types/data'
import type { ChangesPayload } from '../types/history'
import type { NysChangesPayload, NysSystemsPayload } from '../types/nys'

const base = import.meta.env.BASE_URL

export async function loadSystems(): Promise<SystemsPayload> {
  const response = await fetch(`${base}data/systems.json`, { cache: 'no-store' })
  if (!response.ok) throw new Error(`TowerSignal dataset request failed: HTTP ${response.status}`)
  const payload = await response.json() as SystemsPayload
  if (!payload?.metadata || !Array.isArray(payload?.systems)) throw new Error('TowerSignal dataset is malformed')
  return payload
}

export async function loadChanges(): Promise<ChangesPayload> {
  const response = await fetch(`${base}data/changes.json`, { cache: 'no-store' })
  if (!response.ok) throw new Error(`TowerSignal history request failed: HTTP ${response.status}`)
  const payload = await response.json() as ChangesPayload
  if (!payload?.history_started_at || !Array.isArray(payload?.events)) throw new Error('TowerSignal history dataset is malformed')
  return payload
}

export async function loadNysSystems(): Promise<NysSystemsPayload> {
  const response = await fetch(`${base}data/nys-systems.json`, { cache: 'no-store' })
  if (!response.ok) throw new Error(`TowerSignal NYS registry request failed: HTTP ${response.status}`)
  const payload = await response.json() as NysSystemsPayload
  if (!payload?.metadata || !Array.isArray(payload?.systems)) throw new Error('TowerSignal NYS registry dataset is malformed')
  return payload
}

export async function loadNysChanges(): Promise<NysChangesPayload> {
  const response = await fetch(`${base}data/nys-changes.json`, { cache: 'no-store' })
  if (!response.ok) throw new Error(`TowerSignal NYS history request failed: HTTP ${response.status}`)
  const payload = await response.json() as NysChangesPayload
  if (!payload?.history_started_at || !Array.isArray(payload?.events)) throw new Error('TowerSignal NYS history dataset is malformed')
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