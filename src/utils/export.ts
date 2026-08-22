import type { Metadata, SystemSummary } from '../types/data'
import { signalLabel } from '../domain/labels'

function csvCell(value: unknown): string {
  const text = value == null ? '' : String(value)
  return `"${text.replaceAll('"', '""')}"`
}

export function exportCsv(rows: SystemSummary[], metadata: Metadata): void {
  const headers = ['address','borough','zip','system_id','bin','bbl','active_equipment','latest_public_sample_date','days_since_sample','signal_type','confirmed_violation','latest_inspection_date','oath_exact_match_count','pluto_exact_bbl_match','hpd_registered_contact_count','priority_score','evidence_confidence','source_snapshot_timestamp']
  const lines = [headers.map(csvCell).join(',')]
  for (const row of rows) {
    lines.push([
      row.address,row.borough,row.zip,row.system_id,row.bin,row.bbl,row.active_equipment,row.latest_sample_date,row.days_since_latest_sample,
      signalLabel(row.primary_signal),row.confirmed_violation,row.latest_inspection_date,row.oath_case_count ?? 0,row.pluto_match ?? false,row.hpd_contact_count ?? 0,row.priority_score,row.evidence_confidence,metadata.generated_at,
    ].map(csvCell).join(','))
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `towersignal-leads-${metadata.snapshot_date}.csv`
  anchor.click()
  URL.revokeObjectURL(url)
}

export function leadSummary(row: SystemSummary, metadata: Metadata): string {
  const violations = row.confirmed_violation ? 'Official inspection history contains one or more recorded violations.' : 'None identified in the published inspection history.'
  const oath = (row.oath_case_count ?? 0) > 0 ? `${row.oath_case_count} exact summons/ticket match${row.oath_case_count === 1 ? '' : 'es'} in OATH case-status data.` : 'No exact OATH summons/ticket match identified.'
  const signal = row.primary_signal === 'POTENTIAL_SAMPLING_GAP'
    ? `Potential sampling gap — latest publicly reported Legionella sample: ${row.latest_sample_date ?? 'not available'} (${row.days_since_latest_sample ?? 'unknown'} days ago). Operating status must be verified.`
    : signalLabel(row.primary_signal)
  return `TowerSignal lead\nAddress: ${row.address ?? 'Not available'}\nSystem ID: ${row.system_id}\nActive equipment: ${row.active_equipment}\nSignal: ${signal}\nConfirmed violations: ${violations}\nOATH lifecycle: ${oath}\nEvidence: NYC Cooling Tower Registrations; NYC Cooling Tower System Inspection Results; OATH Hearings Division Case Status (exact ticket matches only)\nGenerated: ${metadata.generated_at}\nTowerSignal signals are derived from public records and are not regulatory compliance determinations.`
}
