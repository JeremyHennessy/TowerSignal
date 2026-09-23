import { useEffect, useMemo, useState } from 'react'
import { loadCompanyAdminAccess, loadCompanyAdminDirectory } from '../companyAdmin/client'
import { loadKnownFirms } from '../data/api'
import type { CompanyAdminProfile } from '../types/companyAdmin'
import type { KnownFirmSummaryRecord } from '../types/firm'
import { knownFirmKey, type SalesKnownFirm } from './salesKnownFirms'

export function AccountCompanyLinks({ firms }: { firms: SalesKnownFirm[] }) {
  const [known, setKnown] = useState<KnownFirmSummaryRecord[]>([])
  const [profiles, setProfiles] = useState<CompanyAdminProfile[]>([])
  const [admin, setAdmin] = useState(false)

  useEffect(() => {
    let cancelled = false
    Promise.all([loadKnownFirms(), loadCompanyAdminAccess().catch(() => false)]).then(async ([payload, isAdmin]) => {
      if (cancelled) return
      setKnown(payload.firms)
      setAdmin(isAdmin)
      if (isAdmin) {
        const next = await loadCompanyAdminDirectory()
        if (!cancelled) setProfiles(next)
      }
    }).catch(() => {})
    return () => { cancelled = true }
  }, [])

  const resolved = useMemo(() => {
    const buckets = new Map<string, KnownFirmSummaryRecord[]>()
    known.forEach(firm => buckets.set(knownFirmKey(firm.canonical_name), [...(buckets.get(knownFirmKey(firm.canonical_name)) ?? []), firm]))
    return firms.flatMap(source => {
      const matches = buckets.get(source.key) ?? []
      const exact = matches.find(firm => firm.canonical_name.trim().toLowerCase() === source.name.trim().toLowerCase())
      if (exact) return [{ source, firm: exact, resolution: 'exact label' }]
      if (matches.length === 1) return [{ source, firm: matches[0], resolution: 'unique normalized label' }]
      return []
    })
  }, [firms, known])

  if (!resolved.length) return null
  const profileById = new Map(profiles.map(profile => [profile.company_id, profile]))
  return <div className="account-company-links">
    <strong>Open connected company intelligence</strong>
    <div>{resolved.map(item => {
      const privateProfile = profileById.get(item.firm.firm_id)
      const masterId = privateProfile?.rollup_company_id
      const master = masterId ? profileById.get(masterId) : null
      return <article key={item.source.key}>
        <a href={`#/company/${encodeURIComponent(item.firm.firm_id)}`}>{item.firm.canonical_name}</a>
        <span>{item.source.relationship === 'OBSERVED_SERVICE' ? 'Observed service/testing relationship' : 'Recorded project role'} · {item.resolution}</span>
        {admin && masterId && <small>Private family → <a href={`#/company/${encodeURIComponent(masterId)}`}>{master?.rollup_name || master?.legal_name || master?.canonical_name || masterId}</a></small>}
      </article>
    })}</div>
  </div>
}
