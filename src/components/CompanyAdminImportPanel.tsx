import { useRef, useState } from 'react'
import {
  applyCompanyAdminImport,
  parseCompanyAdminImport,
  type CompanyAdminImportBundle,
} from '../companyAdmin/import'
import type { KnownFirmSummaryRecord } from '../types/firm'

export function CompanyAdminImportPanel({
  firms,
  onImported,
}: {
  firms: KnownFirmSummaryRecord[]
  onImported: () => Promise<void>
}) {
  const input = useRef<HTMLInputElement>(null)
  const [bundle, setBundle] = useState<CompanyAdminImportBundle | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const chooseFile = async (file: File | null) => {
    setBundle(null)
    setStatus(null)
    setError(null)
    setFileName(file?.name ?? null)
    if (!file) return
    try {
      const parsed = parseCompanyAdminImport(await file.text(), firms)
      setBundle(parsed)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to parse private company import')
    }
  }

  const apply = async () => {
    if (!bundle) return
    setBusy(true)
    setError(null)
    setStatus(null)
    try {
      const result = await applyCompanyAdminImport(bundle)
      await onImported()
      setStatus(`Imported ${result.companies} compan${result.companies === 1 ? 'y' : 'ies'} and ${result.contacts} contact${result.contacts === 1 ? '' : 's'}.`)
      setBundle(null)
      setFileName(null)
      if (input.current) input.current.value = ''
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to import private company enrichment')
    } finally {
      setBusy(false)
    }
  }

  const contactCount = bundle?.companies.reduce((sum, company) => sum + (company.contacts?.length ?? 0), 0) ?? 0

  return <section className="company-admin-import-card" aria-label="Private company import">
    <div>
      <span className="page-kicker">Admin only · local file</span>
      <strong>Import sourced company enrichment</strong>
      <p>The file is validated against exact TowerSignal firm IDs and canonical names before any private record is written. Import files are not uploaded to the public dataset.</p>
    </div>
    <div className="company-admin-import-actions">
      <input
        ref={input}
        aria-label="Private company import file"
        type="file"
        accept="application/json,.json"
        onChange={event => void chooseFile(event.target.files?.[0] ?? null)}
        disabled={busy}
      />
      {bundle && <button onClick={() => void apply()} disabled={busy}>
        {busy ? 'Importing…' : `Import ${bundle.companies.length} companies`}
      </button>}
    </div>
    {fileName && bundle && <span className="company-admin-import-preview">{fileName} · {bundle.companies.length} companies · {contactCount} contacts · exact-ID validation passed</span>}
    {status && <span className="company-admin-import-success">{status}</span>}
    {error && <span className="company-admin-import-error">{error}</span>}
  </section>
}
