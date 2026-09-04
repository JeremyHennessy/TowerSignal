from pathlib import Path

# Shared header: the state initializer already resolves the current Toronto route.
# The effect only needs to listen for future hash changes.
nav_path = Path('src/components/TopNavigation.tsx')
nav = nav_path.read_text(encoding='utf-8')
old_effect = """  useEffect(() => {
    if (!TORONTO_PREVIEW) return
    const sync = () => setTorontoRoute(currentTorontoPreviewRoute())
    sync()
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])"""
new_effect = """  useEffect(() => {
    if (!TORONTO_PREVIEW) return
    const sync = () => setTorontoRoute(currentTorontoPreviewRoute())
    window.addEventListener('hashchange', sync)
    return () => window.removeEventListener('hashchange', sync)
  }, [])"""
if old_effect not in nav:
    raise SystemExit('TopNavigation route effect anchor changed')
nav_path.write_text(nav.replace(old_effect, new_effect, 1), encoding='utf-8')

workspace_path = Path('src/components/TorontoUnifiedWorkspace.tsx')
workspace = workspace_path.read_text(encoding='utf-8')

# The route patch may already have removed this legacy prop; make the repair idempotent.
workspace = workspace.replace(
    "function PropertyActions({ row, watched, onOpen, onCopyLead, onToggleWatch }: { row: ProspectRow; watched: boolean; onOpen: () => void; onCopyLead: () => void; onToggleWatch: () => void }) {",
    "function PropertyActions({ watched, onOpen, onCopyLead, onToggleWatch }: { watched: boolean; onOpen: () => void; onCopyLead: () => void; onToggleWatch: () => void }) {",
    1,
)
workspace = workspace.replace('<PropertyActions row={row}', '<PropertyActions')

marker = "  if (route.view === 'source-health')"
if marker not in workspace:
    raise SystemExit('Toronto source-health route anchor changed')
prefix = workspace.split(marker, 1)[0]

tail = r'''  if (route.view === 'source-health') {
    const sourceCoverageRows = Object.entries(payload.source_coverage)
      .filter(([, summary]) => summary.source_records != null || summary.matched_records != null)
      .sort(([, left], [, right]) => (right.matched_canonical_properties ?? 0) - (left.matched_canonical_properties ?? 0))

    return (
      <section className="product-page toronto-page toronto-parity-page">
        <div className="product-page-heading">
          <div>
            <span className="page-kicker">Toronto · evidence operations</span>
            <h1>Source health &amp; coverage</h1>
            <p>Inspect source-level record counts, deterministic match results and known identity limitations before relying on a prospect or portfolio conclusion.</p>
          </div>
        </div>
        <div className="reference-metric-grid toronto-parity-metrics">
          <article><span className="reference-metric-icon success">✓</span><div><small>Official source families</small><strong>{payload.counts.official_source_families.toLocaleString()}</strong><span>Published in current app payload</span></div></article>
          <article><span className="reference-metric-icon">↔</span><div><small>Source links</small><strong>{payload.counts.source_links.toLocaleString()}</strong><span>Property-to-source links</span></div></article>
          <article><span className="reference-metric-icon">⌁</span><div><small>Record-level links</small><strong>{payload.counts.record_level_source_links.toLocaleString()}</strong><span>Durable row-level where available</span></div></article>
        </div>
        <div className="toronto-table-wrap">
          <table className="toronto-table toronto-source-health-table">
            <thead><tr><th>Source</th><th>Status</th><th>Records</th><th>Matched</th><th>Properties</th><th>Match rate</th><th>Limitation</th><th>Official</th></tr></thead>
            <tbody>
              {sourceCoverageRows.map(([key, summary]) => {
                const rate = summary.source_records && summary.matched_records != null
                  ? `${Math.round(summary.matched_records / summary.source_records * 100)}%`
                  : '—'
                return (
                  <tr key={key}>
                    <td><strong>{sourceLabel(key)}</strong></td>
                    <td>{summary.status ? humanize(summary.status) : '—'}</td>
                    <td>{summary.source_records?.toLocaleString() ?? '—'}</td>
                    <td>{summary.matched_records?.toLocaleString() ?? '—'}</td>
                    <td>{summary.matched_canonical_properties?.toLocaleString() ?? '—'}</td>
                    <td>{rate}</td>
                    <td><small>{summary.identity_limitation || summary.scope_limitation || 'Deterministic join contract'}</small></td>
                    <td>{payload.source_catalog[key]?.dataset_url ? <a href={payload.source_catalog[key].dataset_url} target="_blank" rel="noreferrer">Open ↗</a> : '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <section className="toronto-parity-limitations">
          <h2>Known limitations</h2>
          <ul>{payload.limitations.map(item => <li key={item}>{item}</li>)}</ul>
        </section>
      </section>
    )
  }

  return (
    <section className="product-page toronto-page">
      <div className="reference-empty-state">
        <strong>{viewLabel(route.view)} is unavailable.</strong>
        <span>The route is recognized but no Toronto surface is currently rendered.</span>
      </div>
    </section>
  )
}
'''
workspace_path.write_text(prefix + tail, encoding='utf-8')
