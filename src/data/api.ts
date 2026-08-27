import type { SystemDetail, SystemsPayload } from '../types/data'
import type { ChangesPayload } from '../types/history'
import type { NysChangesPayload, NysSystemsPayload } from '../types/nys'
import type { CheckbookProcurementPayload, CityRecordProcurementPayload, ProcurementBundle } from '../types/procurement'

const base = import.meta.env.BASE_URL

async function loadJson<T>(path: string, label: string): Promise<T> {
  const response = await fetch(`${base}data/${path}`, { cache: 'no-store' })
  if (!response.ok) throw new Error(`${label} request failed: HTTP ${response.status}`)
  return response.json() as Promise<T>
}

export async function loadSystems(): Promise<SystemsPayload> {
  const payload = await loadJson<SystemsPayload>('systems.json', 'TowerSignal dataset')
  if (!payload?.metadata || !Array.isArray(payload?.systems)) throw new Error('TowerSignal dataset is malformed')
  return payload
}

export async function loadChanges(): Promise<ChangesPayload> {
  const payload = await loadJson<ChangesPayload>('changes.json', 'TowerSignal history')
  if (!payload?.history_started_at || !Array.isArray(payload?.events)) throw new Error('TowerSignal history dataset is malformed')
  return payload
}

export async function loadNysSystems(): Promise<NysSystemsPayload> {
  const payload = await loadJson<NysSystemsPayload>('nys-systems.json', 'TowerSignal NYS registry')
  if (!payload?.metadata || !Array.isArray(payload?.systems)) throw new Error('TowerSignal NYS registry dataset is malformed')
  return payload
}

export async function loadNysChanges(): Promise<NysChangesPayload> {
  const payload = await loadJson<NysChangesPayload>('nys-changes.json', 'TowerSignal NYS history')
  if (!payload?.history_started_at || !Array.isArray(payload?.events)) throw new Error('TowerSignal NYS history dataset is malformed')
  return payload
}

export async function loadCityRecordProcurement(): Promise<CityRecordProcurementPayload> {
  const payload = await loadJson<CityRecordProcurementPayload>('procurement-city-record.json', 'NYC City Record procurement')
  if (!payload?.source_health || !Array.isArray(payload?.notices)) throw new Error('NYC City Record procurement dataset is malformed')
  return payload
}

export async function loadCheckbookProcurement(): Promise<CheckbookProcurementPayload> {
  const payload = await loadJson<CheckbookProcurementPayload>('procurement-checkbook.json', 'Verified Checkbook NYC procurement')
  if (!payload?.source_health || !Array.isArray(payload?.contracts)) throw new Error('Verified Checkbook NYC procurement dataset is malformed')
  return payload
}

export async function loadProcurement(): Promise<ProcurementBundle> {
  const [cityRecord, checkbook] = await Promise.all([loadCityRecordProcurement(), loadCheckbookProcurement()])
  return { cityRecord, checkbook }
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
