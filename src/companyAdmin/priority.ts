import type { CompanyAdminProfile } from '../types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../types/firm'

export type CompanyResearchCandidate = {
  company_id: string
  canonical_name: string
  priority_score: number
  priority_reason: string
  missing_fields: string[]
  member_ids: string[]
}

const roleWeights: Record<string, number> = {
  DWT_INSPECTION_PROVIDER: 15,
  DWT_LABORATORY: 15,
  DEC_7G_REGISTERED_BUSINESS: 12,
  PROCUREMENT_VENDOR: 10,
  DOB_NOW_APPLICANT_BUSINESS: 4,
  DOB_NOW_OWNER_BUSINESS: 0,
  LEGACY_DOB_OWNER_BUSINESS: 0,
}

const saturatedLog = (value: number, cap: number) =>
  Math.min(1, Math.log1p(Math.max(0, value || 0)) / Math.log1p(cap))

export function companyResearchPriority(firm: KnownFirmSummaryRecord): number {
  const role = Math.max(0, ...firm.roles.map(value => roleWeights[value] ?? 2))
  const score =
    25 * saturatedLog(firm.serviced_site_count, 500) +
    20 * saturatedLog(firm.tower_account_count, 250) +
    10 * saturatedLog(firm.observed_site_count, 500) +
    10 * saturatedLog(firm.observed_contract_count, 50) +
    5 * saturatedLog(Math.max(0, firm.observed_contract_value), 10_000_000) +
    5 * Math.min(1, firm.observed_customer_count / 5) +
    5 * Math.min(1, firm.active_qualification_count) +
    (firm.active_last_12m ? 5 : 0) +
    role
  return Math.max(0, Math.min(100, Math.round(score)))
}

function reasonFor(firm: KnownFirmSummaryRecord, familySize: number): string {
  const parts: string[] = []
  if (firm.serviced_site_count) parts.push(`${firm.serviced_site_count.toLocaleString()} serviced sites`)
  if (firm.tower_account_count) parts.push(`${firm.tower_account_count.toLocaleString()} tower accounts`)
  if (firm.observed_contract_count) parts.push(`${firm.observed_contract_count.toLocaleString()} public contracts`)
  if (firm.observed_customer_count) parts.push(`${firm.observed_customer_count.toLocaleString()} public buyers`)
  if (firm.active_qualification_count) parts.push(`${firm.active_qualification_count.toLocaleString()} active 7G registration${firm.active_qualification_count === 1 ? '' : 's'}`)
  if (firm.active_last_12m) parts.push('observed in last 12 months')
  if (familySize > 1) parts.push(`${familySize} reviewed source identities in private family`)
  return parts.slice(0, 4).join(' · ') || 'TowerSignal public-record company evidence'
}

function missingFields(profile?: CompanyAdminProfile): string[] {
  if (!profile) return ['website','headquarters','company type','parent / ownership','revenue','contact']
  const missing: string[] = []
  if (!profile.website) missing.push('website')
  if (!profile.headquarters_address && !profile.headquarters_city) missing.push('headquarters')
  if (!profile.company_type) missing.push('company type')
  if (!profile.parent_company_id && !profile.parent_company_name) missing.push('parent / ownership')
  if (profile.revenue_amount == null && profile.revenue_low == null && profile.revenue_high == null) missing.push('revenue')
  return missing
}

export function buildCompanyResearchCandidates(
  firms: KnownFirmSummaryRecord[],
  profiles: CompanyAdminProfile[],
  limit = 100,
): CompanyResearchCandidate[] {
  const profileById = new Map(profiles.map(profile => [profile.company_id, profile]))
  const firmById = new Map(firms.map(firm => [firm.firm_id, firm]))
  const groups = new Map<string, KnownFirmSummaryRecord[]>()

  firms.forEach(firm => {
    const canonical = firm.canonical_name.trim()
    if (!canonical || ['N/A','NA','NONE','UNKNOWN'].includes(canonical.toUpperCase())) return
    const masterId = profileById.get(firm.firm_id)?.rollup_company_id || firm.firm_id
    groups.set(masterId, [...(groups.get(masterId) ?? []), firm])
  })

  return [...groups.entries()].map(([masterId, members]) => {
    const ranked = [...members].sort((a,b) =>
      companyResearchPriority(b) - companyResearchPriority(a) ||
      b.observation_count - a.observation_count ||
      a.canonical_name.localeCompare(b.canonical_name))
    const best = ranked[0]
    const masterFirm = firmById.get(masterId)
    return {
      company_id: masterId,
      canonical_name: masterFirm?.canonical_name ?? profileById.get(masterId)?.canonical_name ?? best.canonical_name,
      priority_score: Math.min(100, companyResearchPriority(best) + Math.min(5, Math.max(0, members.length - 1))),
      priority_reason: reasonFor(best, members.length),
      missing_fields: missingFields(profileById.get(masterId)),
      member_ids: members.map(member => member.firm_id).sort(),
    }
  }).sort((a,b) => b.priority_score - a.priority_score || a.canonical_name.localeCompare(b.canonical_name)).slice(0, limit)
}
