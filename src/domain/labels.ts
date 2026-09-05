export const signalLabels: Record<string, string> = {
  CONFIRMED_RECENT_VIOLATION: 'Confirmed violation',
  POTENTIAL_SAMPLING_GAP: 'Potential sampling gap',
  NO_PUBLIC_SAMPLE_DATE: 'No public sample date',
  MULTIPLE_ACTIVE_EQUIPMENT: 'Multiple active equipment',
  RECENT_NYC_HEALTH_INSPECTION: 'Recent NYC Health inspection',
  NO_CURRENT_SIGNAL: 'No current priority signal',
}

export function signalLabel(value: string): string { return signalLabels[value] ?? value.replaceAll('_', ' ') }

function parseDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const trimmed = value.trim()
  if (!trimmed) return null
  const parsed = /^\d{4}-\d{2}-\d{2}$/.test(trimmed) ? new Date(`${trimmed}T00:00:00`) : new Date(trimmed)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

export function formatDate(value: string | null | undefined): string {
  const parsed = parseDate(value)
  return parsed ? parsed.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Not available'
}

export function formatTimestamp(value: string | null | undefined): string {
  const parsed = parseDate(value)
  return parsed ? parsed.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' }) : 'Not available'
}
