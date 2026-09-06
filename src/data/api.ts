import type { SystemDetail, SystemsPayload } from '../types/data'
import type { ChangesPayload } from '../types/history'
import type { NysChangesPayload, NysSystemsPayload } from '../types/nys'
import type { CheckbookProcurementPayload, CityRecordProcurementPayload, NysAuthorityProcurementPayload, NychaWaterPayload, OpenBookWaterPayload, ProcurementBundle } from '../types/procurement'
import type { CompanyIntelligencePayload } from '../types/company'
import type { DomesticWaterMarketPayload, ElapProbePayload, NysLsliDetailPayload, NysPublicWaterPayload, NysServiceLineInventorySummaryPayload, NycDistributionWaterPayload, NycWaterSignalsPayload, ProviderResolutionPayload } from '../types/water'

const base = import.meta.env.BASE_URL

async function loadJson<T>(path: string, label: string): Promise<T> {
  const response = await fetch(`${base}data/${path}`, { cache: 'no-store' })
  if (!response.ok) throw new Error(`${label} request failed: HTTP ${response.status}`)
  return response.json() as Promise<T>
}

async function loadOptionalJson<T>(path: string, label: string, valid: (payload: T) => boolean): Promise<T | null> {
  const response = await fetch(`${base}data/${path}`, { cache: 'no-store' })
  if (response.status === 404) return null
  if (!response.ok) throw new Error(`${label} request failed: HTTP ${response.status}`)
  const payload = await response.json() as T
  if (!valid(payload)) throw new Error(`${label} dataset is malformed`)
  return payload
}

async function optionalResult<T>(load: () => Promise<T | null>): Promise<{ payload: T | null; error?: string }> {
  try {
    return { payload: await load() }
  } catch (error) {
    return { payload: null, error: error instanceof Error ? error.message : 'Optional source cache is unavailable' }
  }
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

export async function loadNysAuthorityProcurement(): Promise<NysAuthorityProcurementPayload> {
  const payload = await loadJson<NysAuthorityProcurementPayload>('procurement-nys-authorities.json', 'NYS authority procurement')
  if (!Array.isArray(payload?.source_health) || !Array.isArray(payload?.contracts)) throw new Error('NYS authority procurement dataset is malformed')
  return payload
}

export async function loadOpenBookWater(): Promise<OpenBookWaterPayload | null> {
  return loadOptionalJson<OpenBookWaterPayload>(
    'procurement-openbook-water.json',
    'Open Book NY water procurement',
    payload => payload?.domain === 'NYS_OPEN_BOOK_WATER_CONTRACT_TRANSACTIONS' && Array.isArray(payload.contracts),
  )
}

export async function loadNychaWater(): Promise<NychaWaterPayload | null> {
  return loadOptionalJson<NychaWaterPayload>(
    'procurement-nycha-water.json',
    'NYCHA water procurement',
    payload => payload?.domain === 'NYCHA_WATER_CONTRACT_RELEASE_LINES' && Array.isArray(payload.records),
  )
}

export async function loadProcurement(): Promise<ProcurementBundle> {
  const [cityRecord, checkbook] = await Promise.all([loadCityRecordProcurement(), loadCheckbookProcurement()])
  const [nysAuthorities, openBookWater, nychaWater] = await Promise.all([
    optionalResult(loadNysAuthorityProcurement),
    optionalResult(loadOpenBookWater),
    optionalResult(loadNychaWater),
  ])
  return {
    cityRecord,
    checkbook,
    nysAuthorities: nysAuthorities.payload,
    openBookWater: openBookWater.payload,
    nychaWater: nychaWater.payload,
    sourceErrors: {
      ...(nysAuthorities.error ? { nysAuthorities: nysAuthorities.error } : {}),
      ...(openBookWater.error ? { openBookWater: openBookWater.error } : {}),
      ...(nychaWater.error ? { nychaWater: nychaWater.error } : {}),
    },
  }
}

export async function loadCompanies(): Promise<CompanyIntelligencePayload> {
  const payload = await loadJson<CompanyIntelligencePayload>('companies.json', 'TowerSignal company intelligence')
  if (!payload?.summary || !Array.isArray(payload?.companies) || !Array.isArray(payload?.unresolved_vendor_observations)) {
    throw new Error('TowerSignal company intelligence dataset is malformed')
  }
  return payload
}

export async function loadDomesticWaterMarket(): Promise<DomesticWaterMarketPayload | null> {
  return loadOptionalJson<DomesticWaterMarketPayload>(
    'domestic-water-market.json',
    'Domestic-water provider intelligence',
    payload => payload?.domain === 'NY_DOMESTIC_WATER_PROVIDER_INTELLIGENCE' && Array.isArray(payload.providers) && Array.isArray(payload.laboratories),
  )
}

export async function loadProviderResolution(): Promise<ProviderResolutionPayload | null> {
  return loadOptionalJson<ProviderResolutionPayload>(
    'provider-resolution-review.json',
    'Provider identity review',
    payload => payload?.domain === 'PROVIDER_IDENTITY_REVIEW' && Array.isArray(payload.alias_review_candidates) && Array.isArray(payload.dec_name_matches),
  )
}

export async function loadNysPublicWater(): Promise<NysPublicWaterPayload | null> {
  return loadOptionalJson<NysPublicWaterPayload>(
    'nys-public-water.json',
    'NYS public-water systems',
    payload => payload?.domain === 'NYS_PUBLIC_WATER_SYSTEMS' && Array.isArray(payload.pws_systems),
  )
}

export async function loadNysLsliDetails(): Promise<NysLsliDetailPayload | null> {
  return loadOptionalJson<NysLsliDetailPayload>(
    'nys-lsli-details.json',
    'NYS LSLI detail',
    payload => payload?.domain === 'NYS_LEAD_SERVICE_LINE_INVENTORY_DETAILS' && Array.isArray(payload.details),
  )
}

export async function loadNysServiceLineSummary(): Promise<NysServiceLineInventorySummaryPayload | null> {
  return loadOptionalJson<NysServiceLineInventorySummaryPayload>(
    'nys-service-line-inventory-summary.json',
    'NYS address service-line inventory',
    payload => payload?.domain === 'NYS_ADDRESS_LEVEL_SERVICE_LINE_INVENTORY' && typeof payload.summary === 'object',
  )
}

export async function loadNycDistributionWater(): Promise<NycDistributionWaterPayload | null> {
  return loadOptionalJson<NycDistributionWaterPayload>(
    'nyc-distribution-water.json',
    'NYC distribution water quality',
    payload => payload?.domain === 'NYC_DISTRIBUTION_DRINKING_WATER_QUALITY' && Array.isArray(payload.sites),
  )
}

export async function loadNycWaterSignals(): Promise<NycWaterSignalsPayload | null> {
  return loadOptionalJson<NycWaterSignalsPayload>(
    'nyc-water-signals.json',
    'NYC building-water signals',
    payload => payload?.domain === 'NYC_BUILDING_WATER_SIGNALS' && typeof payload.summary === 'object',
  )
}

export async function loadElapProbe(): Promise<ElapProbePayload | null> {
  return loadOptionalJson<ElapProbePayload>(
    'elap-source-probe.json',
    'ELAP source probe',
    payload => typeof payload?.search_url === 'string' && typeof payload?.lab_selector === 'object',
  )
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
