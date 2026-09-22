import { useMemo, useState, type ReactNode } from 'react'
import type { SystemsPayload } from '../types/data'
import type { ProcurementBundle } from '../types/procurement'
import { safeSourceUrl } from '../domain/sourceHealthExpansion'

export interface SourceHealthLink {
  label?: string
  url?: unknown
  artifact?: string
}

function linkHref(link: SourceHealthLink): string | null {
  if (link.artifact) {
    // Only published JSON paths, never arbitrary schemes or traversal paths.
    if (!/^[a-zA-Z0-9][a-zA-Z0-9_./-]*\.json$/.test(link.artifact) || link.artifact.split('/').some(part => part === '.' || part === '..')) return null
    return `${import.meta.env.BASE_URL}data/${link.artifact}`
  }
  return safeSourceUrl(link.url)
}

export function SourceHealthLinks({ links, empty = 'Source link not reported' }: { links: SourceHealthLink[]; empty?: string }) {
  const seen = new Set<string>()
  const valid = links.flatMap(link => {
    const href = linkHref(link)
    if (!href || seen.has(href)) return []
    seen.add(href)
    return [{ ...link, href }]
  })
  return <div className="source-health-links">
    {valid.length ? valid.map(link => <a className="source-health-link" key={link.href} href={link.href} target="_blank" rel="noopener noreferrer" title={`${link.artifact ? 'Published TowerSignal dataset' : 'Publisher source'} · ${link.href}`}>
      {link.artifact && <span className="source-health-link-kind" aria-hidden="true">JSON</span>}
      <span>{link.label || 'Official source'}</span><span aria-hidden="true">↗</span>
    </a>) : <span className="source-health-link-missing">{empty}</span>}
  </div>
}

export function SourceHealthSource({ name, detail, links }: { name: string; detail?: ReactNode; links: SourceHealthLink[] }) {
  return <div className="source-health-source"><strong>{name}</strong>{detail && <small>{detail}</small>}<SourceHealthLinks links={links} /></div>
}

export function SourceHealthDirectory({ payload, procurement }: { payload: SystemsPayload; procurement: ProcurementBundle | null }) {
  const [query, setQuery] = useState('')
  const entries = useMemo(() => {
    const items = payload.metadata.sources.map(source => ({ name: source.name, id: source.dataset_id, url: safeSourceUrl(source.url) }))
    if (procurement) {
      items.push({ name: 'NYC City Record', id: 'City Record procurement', url: safeSourceUrl(procurement.cityRecord.source.dataset_page) })
      items.push({ name: 'Checkbook NYC documentation', id: 'Checkbook contract/vendor evidence', url: safeSourceUrl(procurement.checkbook.source.documentation_url) })
      items.push({ name: 'Checkbook NYC API', id: 'Checkbook contract/vendor evidence', url: safeSourceUrl(procurement.checkbook.source.api_url) })
      if (procurement.nysAuthorities) {
        const root = safeSourceUrl(procurement.nysAuthorities.source.api_root)
        for (const source of procurement.nysAuthorities.source_health) {
          if (root && /^[a-z0-9]{4}-[a-z0-9]{4}$/.test(source.dataset_id)) items.push({ name: source.dataset_name, id: source.dataset_id, url: new URL(`/d/${source.dataset_id}`, root).href })
        }
      }
      for (const [name, source] of [['Open Book NY', procurement.openBookWater?.source], ['NYCHA procurement', procurement.nychaWater?.source]] as const) {
        for (const key of ['source_page', 'search_page', 'source_url', 'export_url', 'contract_api_url', 'api_url']) {
          const url = safeSourceUrl(source?.[key])
          if (url) items.push({ name, id: key.replaceAll('_', ' '), url })
        }
      }
    }
    const unique = new Map<string, typeof items[number]>()
    for (const item of items) unique.set(`${item.id}|${item.url}`, item)
    return [...unique.values()].sort((a, b) => a.name.localeCompare(b.name))
  }, [payload, procurement])
  const visible = entries.filter(item => `${item.name} ${item.id} ${item.url || ''}`.toLowerCase().includes(query.trim().toLowerCase()))
  return <details className="reference-table-card source-health-directory" id="source-health-directory" tabIndex={-1}>
    <summary><span><strong>Publisher link directory</strong><small>{entries.length} source-metadata entries and procurement references. Public-health channels are listed in Monitoring below.</small></span><span aria-hidden="true">Browse links +</span></summary>
    <div className="source-health-directory-search"><label htmlFor="source-health-source-search">Find a publisher or dataset</label><input id="source-health-source-search" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search by name, dataset ID or website" /><span role="status">{visible.length} of {entries.length} entries</span></div>
    <div className="reference-table-scroll" tabIndex={0} role="region" aria-label="Publisher link directory table"><table className="reference-table source-linked-table"><thead><tr><th>Source &amp; links</th><th>Dataset / reference</th><th>Publisher website</th></tr></thead><tbody>{visible.map(item => <tr key={`${item.id}|${item.url}`}><td><SourceHealthSource name={item.name} links={[{ url: item.url }]} /></td><td>{item.id}</td><td>{item.url ? new URL(item.url).hostname : 'Not reported'}</td></tr>)}</tbody></table></div>
    {visible.length === 0 && <p className="source-health-no-results">No matching sources. Clear the search to see every entry.</p>}
  </details>
}
