import type { Metadata, SystemSummary } from '../types/data'
import type { WorkflowAccountState, WorkflowMembership, WorkflowWatchlist } from '../types/workflow'

function cell(value: unknown): string {
  const text = value == null ? '' : String(value)
  return `"${text.replaceAll('"', '""')}"`
}

export function exportWorkflowCsv(
  rows: SystemSummary[],
  metadata: Metadata,
  accounts: WorkflowAccountState[],
  memberships: WorkflowMembership[],
  watchlists: WorkflowWatchlist[],
): void {
  const accountMap = new Map(accounts.map(account => [account.system_id, account]))
  const watchlistMap = new Map(watchlists.map(watchlist => [watchlist.id, watchlist.name]))
  const watchlistsBySystem = new Map<string, string[]>()
  memberships.forEach(item => {
    const names = watchlistsBySystem.get(item.system_id) ?? []
    const name = watchlistMap.get(item.watchlist_id)
    if (name) names.push(name)
    watchlistsBySystem.set(item.system_id, names)
  })

  const headers = [
    'address','borough','zip','system_id','bin','bbl','priority_score','primary_signal','evidence_confidence',
    'workflow_status','workflow_note','workflow_next_action_date','workflow_watchlists','source_snapshot_timestamp',
  ]
  const lines = [headers.map(cell).join(',')]
  rows.forEach(row => {
    const workflow = accountMap.get(row.system_id)
    lines.push([
      row.address,row.borough,row.zip,row.system_id,row.bin,row.bbl,row.priority_score,row.primary_signal,row.evidence_confidence,
      workflow?.status ?? 'new',workflow?.note ?? '',workflow?.next_action_date ?? '',(watchlistsBySystem.get(row.system_id) ?? []).join(' | '),metadata.generated_at,
    ].map(cell).join(','))
  })

  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `towersignal-workflow-${metadata.snapshot_date}.csv`
  anchor.click()
  URL.revokeObjectURL(url)
}
