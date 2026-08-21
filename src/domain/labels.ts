export const signalLabels: Record<string, string> = {
  CONFIRMED_RECENT_VIOLATION: 'Confirmed violation',
  POTENTIAL_SAMPLING_GAP: 'Potential sampling gap',
  NO_PUBLIC_SAMPLE_DATE: 'No public sample date',
  MULTIPLE_ACTIVE_EQUIPMENT: 'Multiple active equipment',
  RECENT_NYC_HEALTH_INSPECTION: 'Recent NYC Health inspection',
  NO_CURRENT_SIGNAL: 'No current priority signal',
}

export function signalLabel(value: string): string { return signalLabels[value] ?? value.replaceAll('_', ' ') }
export function formatDate(value: string | null): string { return value ? new Date(`${value}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Not available' }
export function formatTimestamp(value: string): string { return new Date(value).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' }) }
