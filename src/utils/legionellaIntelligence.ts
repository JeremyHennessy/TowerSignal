import type { LegionellaAlertItem } from '../types/enforcement'
import type { LegionellaPropertyMatches } from '../types/legionellaIntelligence'

export function officialDate(value: string | null | undefined): string {
  if (!value || !/^\d{4}-\d{2}-\d{2}/.test(value)) return 'Not published'
  const date = new Date(value.slice(0, 10) + 'T12:00:00Z')
  return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }).format(date) : 'Not published'
}

export function displayHeadline(item: LegionellaAlertItem): string {
  let title = (item.title || '').replace(/\s+-\s+NYC (Health|Mayor['’]s Office)$/i, '').trim()
  if (!title) title = new URL(item.url).pathname.split('/').pop()?.replace(/\.(page|pdf)$/i, '') || 'Official Legionnaires update'
  if (!title.includes(' ') && title.includes('-')) {
    title = title.replaceAll('-', ' ').replace(/\b\w/g, letter => letter.toUpperCase())
      .replace(/\b(Nyc|Nys|Pcr|Ues|Doh|Pdf)\b/g, word => word.toUpperCase())
  }
  return title
}

export function publicationKind(item: LegionellaAlertItem): string {
  const url = item.url.toLowerCase()
  if (url.endsWith('.pdf')) return 'Source document'
  if (url.includes('/about/press/') || url.includes('/mayors-office/')) return 'Official release'
  if (item.document_type === 'NOTIFY_NYC_ALERT') return 'Emergency notice'
  return 'Guidance & reference'
}

export function relatedEvidence(item: LegionellaAlertItem, matches: LegionellaPropertyMatches | null) {
  const records = matches?.matched_observations.filter(record => record.source_url === item.url || record.related_article_urls.includes(item.url)) ?? []
  const unresolved = matches?.unresolved.filter(record => record.source_url === item.url || record.related_article_urls.includes(item.url)) ?? []
  const groups = new Map<string, typeof records>()
  for (const record of records) {
    const key = `${record.cluster_id}:${record.bin}`
    groups.set(key, [...(groups.get(key) ?? []), record])
  }
  return {
    records, unresolved, buildings: [...groups.values()].sort((a, b) => a[0].address.localeCompare(b[0].address)),
    systems: new Set(records.flatMap(record => record.system_ids)).size,
    direct: records.some(record => record.source_url === item.url),
    historical: records.length > 0 && records.every(record => record.cluster_status === 'CLOSED_REPORTED'),
  }
}

export function resultLabel(value: string): string {
  const names: Record<string, string> = { PCR_POSITIVE: 'PCR positive', PCR_NEGATIVE: 'PCR negative', CULTURE_POSITIVE: 'Culture positive', CULTURE_NEGATIVE: 'Culture negative', CULTURE_PENDING: 'Culture pending' }
  return names[value] || 'Source finding'
}
