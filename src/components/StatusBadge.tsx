import type { EvidenceConfidence } from '../types/data'

export function StatusBadge({ value }: { value: EvidenceConfidence }) {
  return <span className={`badge badge-${value.toLowerCase()}`}>{value.replace('_', ' ')}</span>
}
