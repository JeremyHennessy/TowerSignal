import type { TorontoProperty } from '../types/toronto'

export type TorontoProspectExportRow = {
  property: TorontoProperty
  attention: number
  tier: 'HIGH' | 'MEDIUM' | 'CONTEXT'
  factors: string[]
  opportunities: string[]
}

export type TorontoCompanyExportRow = {
  name: string
  propertyIds: Set<string>
  confirmedPropertyIds: Set<string>
  roles: Set<string>
  sources: Set<string>
  highAttentionPropertyIds: Set<string>
}

function csvCell(value: unknown): string {
  const text = value == null ? '' : String(value)
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text
}

function csv(headers: string[], rows: unknown[][]): string {
  return [headers, ...rows].map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n'
}

export function buildTorontoProspectCsv(rows: TorontoProspectExportRow[]): string {
  return csv(
    ['Property ID', 'Address Point ID', 'Address', 'Attention', 'Tier', 'Tower evidence', 'Why now', 'Opportunities', 'Organizations', 'Relationship roles', 'Source families', 'Source count', 'Relationship count'],
    rows.map(row => {
      const organizations = [...new Set(row.property.relationships.map(item => item.organization))]
      const roles = [...new Set(row.property.relationships.map(item => item.relationship))]
      return [
        row.property.property_id,
        row.property.address_point_id,
        row.property.display_address,
        row.attention,
        row.tier,
        row.property.tower_evidence_status,
        row.factors.join(' | '),
        row.opportunities.join(' | '),
        organizations.join(' | '),
        roles.join(' | '),
        row.property.source_keys.join(' | '),
        row.property.source_keys.length,
        row.property.relationships.length,
      ]
    }),
  )
}

export function buildTorontoCompanyCsv(rows: TorontoCompanyExportRow[]): string {
  return csv(
    ['Organization', 'Linked properties', 'Confirmed tower properties', 'High-attention properties', 'Relationship roles', 'Source families'],
    rows.map(row => [
      row.name,
      row.propertyIds.size,
      row.confirmedPropertyIds.size,
      row.highAttentionPropertyIds.size,
      [...row.roles].join(' | '),
      [...row.sources].join(' | '),
    ]),
  )
}

export function buildTorontoLeadSummary(row: TorontoProspectExportRow): string {
  const property = row.property
  const relationships = property.relationships.length
    ? property.relationships.map(item => `${item.organization} — ${item.relationship.replaceAll('_', ' ')}`).join('; ')
    : 'No source-backed organization relationship currently linked.'
  const sources = property.source_keys.length ? property.source_keys.join(', ') : 'No source families linked.'
  const factors = row.factors.length ? row.factors.join('; ') : 'No commercial attention factors.'
  const opportunities = row.opportunities.length ? row.opportunities.join('; ') : 'No current opportunity queue signal.'

  return [
    `TowerSignal Toronto — ${property.display_address}`,
    `Commercial attention: ${row.attention}/100 (${row.tier}); this is not a regulatory or compliance score.`,
    `Tower evidence: ${property.tower_evidence_status.replaceAll('_', ' ')}.`,
    `Why now: ${factors}`,
    `Opportunity context: ${opportunities}`,
    `Organizations: ${relationships}`,
    `Source families: ${sources}`,
    `Canonical property: ${property.property_id}; Toronto Address Point ID ${property.address_point_id}.`,
    'Verify the cited source records in the property evidence drawer before outreach or operational decisions.',
  ].join('\n')
}

export function downloadCsv(filename: string, contents: string): void {
  const blob = new Blob([contents], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.style.display = 'none'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

export async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  textarea.remove()
  if (!copied) throw new Error('Clipboard copy is unavailable')
}
