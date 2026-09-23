import { useEffect, useState } from 'react'
import { loadCompanyAdminAccess, loadCompanyAuditLog } from '../companyAdmin/client'
import type { CompanyAuditEntry } from '../types/companyAdmin'

const valueText = (value: unknown) => value == null ? '—' : typeof value === 'string' ? value : JSON.stringify(value)

export function CompanyAuditHistory({ companyId }: { companyId: string }) {
  const [rows, setRows] = useState<CompanyAuditEntry[]>([])
  const [allowed, setAllowed] = useState(false)
  useEffect(() => {
    let cancelled = false
    loadCompanyAdminAccess().then(async isAdmin => {
      if (!isAdmin || cancelled) return
      const next = await loadCompanyAuditLog(companyId, 60)
      if (!cancelled) { setAllowed(true); setRows(next) }
    }).catch(() => { if (!cancelled) setAllowed(false) })
    return () => { cancelled = true }
  }, [companyId])
  if (!allowed) return null
  return <details className="company-audit-panel">
    <summary><strong>Private change history</strong><span>{rows.length} recent field changes</span></summary>
    {rows.length ? <div className="company-audit-list">{rows.map(row => <article key={row.change_id}>
      <time>{new Date(row.changed_at).toLocaleString()}</time>
      <strong>{row.entity_type} · {row.field_name}</strong>
      <span>{valueText(row.old_value)} → {valueText(row.new_value)}</span>
      <small>{row.change_source}{row.import_batch_id ? ` · batch ${row.import_batch_id}` : ''}</small>
    </article>)}</div> : <p className="company-admin-empty">No post-audit-migration changes have been recorded yet.</p>}
  </details>
}
