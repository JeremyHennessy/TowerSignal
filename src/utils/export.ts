import type { Metadata, SystemDetail, SystemSummary } from '../types/data'
import { signalLabel } from '../domain/labels'

function csvCell(value: unknown): string {
  const text = value == null ? '' : String(value)
  return `"${text.replaceAll('"', '""')}"`
}

export function exportCsv(rows: SystemSummary[], metadata: Metadata): void {
  const headers = ['address','borough','zip','system_id','bin','bbl','active_equipment','registration_date','reported_sample_count','inspection_count','violation_citation_count','latest_violation_date','oath_balance_due_total','latest_public_sample_date','days_since_sample','signal_type','confirmed_violation','latest_inspection_date','oath_exact_match_count','pluto_exact_bbl_match','dob_job_filing_count','dob_recent_activity_count_365d','dob_explicit_cooling_tower_count','dob_mechanical_or_boiler_count','latest_dob_activity_date','hpd_registered_contact_count','priority_score','evidence_confidence','source_snapshot_timestamp']
  const lines = [headers.map(csvCell).join(',')]
  for (const row of rows) {
    lines.push([
      row.address,row.borough,row.zip,row.system_id,row.bin,row.bbl,row.active_equipment,row.registration_date,row.sample_count ?? 0,row.inspection_count ?? 0,row.violation_citation_count ?? 0,row.latest_violation_date,row.oath_balance_due_total ?? 0,row.latest_sample_date,row.days_since_latest_sample,
      signalLabel(row.primary_signal),row.confirmed_violation,row.latest_inspection_date,row.oath_case_count ?? 0,row.pluto_match ?? false,row.dob_activity_count ?? 0,row.dob_recent_activity_count ?? 0,row.dob_explicit_cooling_tower_count ?? 0,row.dob_mechanical_or_boiler_count ?? 0,row.latest_dob_activity_date,row.hpd_contact_count ?? 0,row.priority_score,row.evidence_confidence,metadata.generated_at,
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

export function leadSummary(row: SystemSummary, metadata: Metadata, detail?: SystemDetail): string {
  const violations = row.confirmed_violation ? 'Official inspection history contains one or more recorded violations.' : 'None identified in the published inspection history.'
  const oath = (row.oath_case_count ?? 0) > 0 ? `${row.oath_case_count} exact summons/ticket match${row.oath_case_count === 1 ? '' : 'es'} in OATH case-status data.` : 'No exact OATH summons/ticket match identified.'
  const signal = row.primary_signal === 'POTENTIAL_SAMPLING_GAP'
    ? `Potential sampling gap — latest publicly reported Legionella sample: ${row.latest_sample_date ?? 'not available'} (${row.days_since_latest_sample ?? 'unknown'} days ago). Operating status must be verified.`
    : signalLabel(row.primary_signal)

  const lines = [
    'TowerSignal lead',
    `Address: ${row.address ?? 'Not available'}`,
    `System ID: ${row.system_id}`,
    `BBL: ${row.bbl ?? 'Not available'}`,
    `Active equipment: ${row.active_equipment}`,
    `Signal: ${signal}`,
    `Confirmed violations: ${violations}`,
    `OATH lifecycle: ${oath}`,
  ]

  if (detail?.historical_profile) {
    const history = detail.historical_profile
    lines.push('', 'Historical profile')
    lines.push(`Registration date: ${history.registration_date ?? 'Not published'}`)
    lines.push(`Reported sample history: ${history.sample.reported_sample_count} samples${history.sample.first_reported_date ? ` from ${history.sample.first_reported_date} to ${history.sample.latest_reported_date}` : ''}`)
    lines.push(`NYC Health inspection history: ${history.inspection.inspection_count} inspections; ${history.inspection.inspections_with_violations} with cited violations; ${history.inspection.violation_citation_count} cited violation rows`)
    lines.push(`OATH totals: $${history.oath.penalty_imposed_total.toFixed(2)} imposed; $${history.oath.paid_amount_total.toFixed(2)} paid; $${history.oath.balance_due_total.toFixed(2)} balance due`)
  }

  if (detail) {
    lines.push('', 'Property / contact context')
    lines.push(`PLUTO owner: ${detail.building_context?.owner_name ?? 'No exact PLUTO owner match'}`)
    if (!detail.hpd_registration) {
      lines.push('HPD registration: No exact BBL match in Multiple Dwelling Registrations')
    } else if (detail.hpd_registration.contacts.length === 0) {
      lines.push(`HPD registration: ${detail.hpd_registration.registration_id ?? 'matched'}; no contact rows returned`)
    } else {
      lines.push(`HPD registration: ${detail.hpd_registration.registration_id ?? 'matched'}${detail.hpd_registration.last_registration_date ? `; processed ${detail.hpd_registration.last_registration_date}` : ''}`)
      detail.hpd_registration.contacts.forEach((contact, index) => {
        const name = contact.corporation_name ?? contact.person_name ?? contact.description ?? 'Name not published'
        const parts = [
          `${index + 1}. ${contact.type ?? 'HPD contact'}: ${name}`,
          contact.person_name ? `person ${contact.person_name}` : null,
          contact.title ? `title ${contact.title}` : null,
          contact.business_address ? `business address ${contact.business_address}` : null,
        ].filter(Boolean)
        lines.push(parts.join(' · '))
      })
    }
    lines.push('Contact context is from public NYC PLUTO/HPD records and does not establish who procures or is responsible for cooling-tower service.')

    lines.push('', 'DOB NOW project activity')
    const dobActivity = detail.dob_activity_history ?? []
    if (dobActivity.length === 0) {
      lines.push('No exact-BBL DOB NOW Job Application Filing match identified.')
    } else {
      const explicitCount = dobActivity.filter(item => item.explicit_cooling_tower_mention).length
      const mechanicalCount = dobActivity.filter(item => item.mechanical_systems || item.boiler_equipment).length
      const latest = dobActivity.find(item => item.activity_date)?.activity_date ?? 'not published'
      lines.push(`${dobActivity.length} exact-BBL job filings; ${explicitCount} descriptions explicitly name cooling-tower work; ${mechanicalCount} carry mechanical or boiler work-type flags; latest published lifecycle activity ${latest}.`)
      const notable = dobActivity.filter(item => item.explicit_cooling_tower_mention || item.mechanical_systems || item.boiler_equipment).slice(0, 3)
      notable.forEach((item, index) => {
        const classification = item.explicit_cooling_tower_mention ? 'explicit cooling-tower description' : 'mechanical/boiler flag'
        const parts = [
          `${index + 1}. ${item.job_filing_number ?? 'DOB filing'} (${classification})`,
          item.activity_date ?? null,
          item.filing_status ?? null,
          item.job_description ?? null,
          item.owner_business_name ? `owner ${item.owner_business_name}` : null,
          item.applicant_business_name ? `applicant ${item.applicant_business_name}` : null,
        ].filter(Boolean)
        lines.push(parts.join(' · '))
      })
    }
    lines.push('DOB NOW activity is exact-BBL property context only; mechanical/boiler flags are not cooling-tower claims, and this source does not affect TowerSignal priority scoring.')
  }

  lines.push('', 'Evidence: NYC Cooling Tower Registrations; NYC Cooling Tower System Inspection Results; OATH Hearings Division Case Status (exact ticket matches only); NYC DCP PLUTO (exact BBL); DOB NOW Job Application Filings (exact BBL); NYC HPD Multiple Dwelling Registrations and Registration Contacts (exact BBL / registration ID where available)')
  lines.push(`Generated: ${metadata.generated_at}`)
  lines.push('TowerSignal signals are derived from public records and are not regulatory compliance determinations.')
  return lines.join('\n')
}
