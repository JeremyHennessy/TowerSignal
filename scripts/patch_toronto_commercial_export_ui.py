from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / 'src/components/TorontoParityShell.tsx'
CSS = ROOT / 'src/styles/toronto-parity.css'


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise RuntimeError(f'{label} anchor changed')
    return text.replace(old, new, 1)


def main() -> None:
    text = COMPONENT.read_text(encoding='utf-8')
    anchor = "import { TorontoBenchmarkingPage } from './TorontoBenchmarkingPage'\n"
    import_line = "import { buildTorontoCompanyCsv, buildTorontoLeadSummary, buildTorontoProspectCsv, copyText, downloadCsv } from '../utils/torontoCommercialExport'\n"
    if import_line not in text:
        if anchor not in text:
            raise RuntimeError('benchmarking import anchor changed')
        text = text.replace(anchor, anchor + import_line, 1)

    text = replace_once(
        text,
        "function PropertyAction({ watched, onToggleWatch, onOpen }: { watched: boolean; onToggleWatch: () => void; onOpen: () => void }) {\n  return <div className=\"toronto-parity-actions\"><button className=\"primary\" onClick={onOpen}>Open evidence</button><button className={watched ? 'active-control' : ''} onClick={onToggleWatch}>{watched ? 'Watching' : 'Watch'}</button></div>\n}",
        "function PropertyAction({ watched, onToggleWatch, onOpen, onCopyLead }: { watched: boolean; onToggleWatch: () => void; onOpen: () => void; onCopyLead?: () => void }) {\n  return <div className=\"toronto-parity-actions\"><button className=\"primary\" onClick={onOpen}>Open evidence</button>{onCopyLead && <button onClick={onCopyLead}>Copy lead</button>}<button className={watched ? 'active-control' : ''} onClick={onToggleWatch}>{watched ? 'Watching' : 'Watch'}</button></div>\n}",
        'PropertyAction',
    )
    text = replace_once(
        text,
        "function ProspectTable({ rows, watchedIds, onToggleWatch, onOpen }: { rows: ProspectRow[]; watchedIds: Set<string>; onToggleWatch: (id: string) => void; onOpen: (property: TorontoProperty) => void }) {",
        "function ProspectTable({ rows, watchedIds, onToggleWatch, onOpen, onCopyLead }: { rows: ProspectRow[]; watchedIds: Set<string>; onToggleWatch: (id: string) => void; onOpen: (property: TorontoProperty) => void; onCopyLead?: (row: ProspectRow) => void }) {",
        'ProspectTable signature',
    )
    text = text.replace(
        "<PropertyAction watched={watchedIds.has(row.property.property_id)} onToggleWatch={() => onToggleWatch(row.property.property_id)} onOpen={() => onOpen(row.property)} />",
        "<PropertyAction watched={watchedIds.has(row.property.property_id)} onToggleWatch={() => onToggleWatch(row.property.property_id)} onOpen={() => onOpen(row.property)} onCopyLead={onCopyLead ? () => onCopyLead(row) : undefined} />",
    )

    state_anchor = "  const [companyRole, setCompanyRole] = useState('')\n"
    if "const [copyFeedback, setCopyFeedback]" not in text:
        if state_anchor not in text:
            raise RuntimeError('state anchor changed')
        text = text.replace(state_anchor, state_anchor + "  const [copyFeedback, setCopyFeedback] = useState('')\n", 1)

    action_anchor = "  const openProperty = (property: TorontoProperty) => openInMarket(property, setView)\n"
    actions = """  const copyLead = async (row: ProspectRow) => {\n    try {\n      await copyText(buildTorontoLeadSummary(row))\n      setCopyFeedback(`Copied ${row.property.display_address}`)\n    } catch {\n      setCopyFeedback('Clipboard unavailable')\n    }\n    window.setTimeout(() => setCopyFeedback(''), 2200)\n  }\n  const exportProspects = (rows: ProspectRow[], filename: string) => downloadCsv(filename, buildTorontoProspectCsv(rows))\n  const exportCompanies = (rows: CompanyRow[], filename: string) => downloadCsv(filename, buildTorontoCompanyCsv(rows))\n"""
    if "const copyLead = async" not in text:
        if action_anchor not in text:
            raise RuntimeError('action anchor changed')
        text = text.replace(action_anchor, action_anchor + actions, 1)

    text = replace_once(
        text,
        '<div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search address, company, source or signal" /><strong>{highProspects.length.toLocaleString()} high-attention matches</strong></div>',
        '<div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search address, company, source or signal" /><div className="toronto-parity-toolbar-actions"><button onClick={() => exportProspects(filteredProspects, \'towersignal-toronto-prospects.csv\')}>Export CSV</button>{copyFeedback && <small role="status">{copyFeedback}</small>}</div><strong>{highProspects.length.toLocaleString()} high-attention matches</strong></div>',
        'prospect toolbar',
    )
    text = replace_once(
        text,
        '<ProspectTable rows={filteredProspects} watchedIds={watchedIds} onToggleWatch={toggleWatch} onOpen={openProperty} />',
        '<ProspectTable rows={filteredProspects} watchedIds={watchedIds} onToggleWatch={toggleWatch} onOpen={openProperty} onCopyLead={copyLead} />',
        'prospect table',
    )
    text = replace_once(
        text,
        '<div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search opportunity accounts" /><select value={opportunityFilter} onChange={event => setOpportunityFilter(event.target.value)}><option value="all">All opportunity signals</option><option value="confirmed-permit">Confirmed tower + mechanical permit</option><option value="mechanical">Mechanical / cooling-system permit</option><option value="planning">Planning / development</option><option value="relationship-gap">Relationship research gap</option><option value="multi-source">Multi-source context</option><option value="environment">Environmental / health context</option></select><strong>{opportunityRows.length.toLocaleString()} matches</strong></div>',
        '<div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search opportunity accounts" /><select value={opportunityFilter} onChange={event => setOpportunityFilter(event.target.value)}><option value="all">All opportunity signals</option><option value="confirmed-permit">Confirmed tower + mechanical permit</option><option value="mechanical">Mechanical / cooling-system permit</option><option value="planning">Planning / development</option><option value="relationship-gap">Relationship research gap</option><option value="multi-source">Multi-source context</option><option value="environment">Environmental / health context</option></select><div className="toronto-parity-toolbar-actions"><button onClick={() => exportProspects(opportunityRows, \'towersignal-toronto-opportunities.csv\')}>Export CSV</button>{copyFeedback && <small role="status">{copyFeedback}</small>}</div><strong>{opportunityRows.length.toLocaleString()} matches</strong></div>',
        'opportunity toolbar',
    )
    text = replace_once(
        text,
        '<PropertyAction watched={watchedIds.has(row.property.property_id)} onToggleWatch={() => toggleWatch(row.property.property_id)} onOpen={() => openProperty(row.property)} />',
        '<PropertyAction watched={watchedIds.has(row.property.property_id)} onToggleWatch={() => toggleWatch(row.property.property_id)} onOpen={() => openProperty(row.property)} onCopyLead={() => copyLead(row)} />',
        'opportunity action',
    )
    text = replace_once(
        text,
        '<div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search organization or role" /><select value={companyRole} onChange={event => setCompanyRole(event.target.value)}><option value="">All relationship roles</option>{roles.map(role => <option key={role} value={role}>{humanize(role)}</option>)}</select><strong>{filteredCompanies.length.toLocaleString()} organizations</strong></div>',
        '<div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search organization or role" /><select value={companyRole} onChange={event => setCompanyRole(event.target.value)}><option value="">All relationship roles</option>{roles.map(role => <option key={role} value={role}>{humanize(role)}</option>)}</select><div className="toronto-parity-toolbar-actions"><button onClick={() => exportCompanies(filteredCompanies, \'towersignal-toronto-companies.csv\')}>Export CSV</button></div><strong>{filteredCompanies.length.toLocaleString()} organizations</strong></div>',
        'companies toolbar',
    )
    text = replace_once(
        text,
        '<div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search portfolio organization" /><select value={companyRole} onChange={event => setCompanyRole(event.target.value)}><option value="">All portfolio roles</option>{roles.filter(role => portfolioRoles.has(role)).map(role => <option key={role} value={role}>{humanize(role)}</option>)}</select><strong>{portfolioCompanies.length.toLocaleString()} portfolios</strong></div>',
        '<div className="toronto-parity-toolbar"><input value={search} onChange={event => setSearch(event.target.value)} placeholder="Search portfolio organization" /><select value={companyRole} onChange={event => setCompanyRole(event.target.value)}><option value="">All portfolio roles</option>{roles.filter(role => portfolioRoles.has(role)).map(role => <option key={role} value={role}>{humanize(role)}</option>)}</select><div className="toronto-parity-toolbar-actions"><button onClick={() => exportCompanies(portfolioCompanies, \'towersignal-toronto-portfolios.csv\')}>Export CSV</button></div><strong>{portfolioCompanies.length.toLocaleString()} portfolios</strong></div>',
        'portfolios toolbar',
    )
    text = replace_once(
        text,
        '{watchRows.length ? <ProspectTable rows={watchRows} watchedIds={watchedIds} onToggleWatch={toggleWatch} onOpen={openProperty} /> : <div className="reference-empty-state">',
        '{watchRows.length ? <><div className="toronto-parity-toolbar toronto-watchlist-toolbar"><div className="toronto-parity-toolbar-actions"><button onClick={() => exportProspects(watchRows, \'towersignal-toronto-watchlist.csv\')}>Export watchlist CSV</button>{copyFeedback && <small role="status">{copyFeedback}</small>}</div><strong>{watchRows.length.toLocaleString()} watched properties</strong></div><ProspectTable rows={watchRows} watchedIds={watchedIds} onToggleWatch={toggleWatch} onOpen={openProperty} onCopyLead={copyLead} /></> : <div className="reference-empty-state">',
        'watchlist',
    )
    COMPONENT.write_text(text, encoding='utf-8')

    style = CSS.read_text(encoding='utf-8')
    if '.toronto-parity-toolbar-actions' not in style:
        style = style.rstrip() + """\n.toronto-parity-toolbar-actions{display:flex;gap:8px;align-items:center;justify-content:flex-end;min-width:0}.toronto-parity-toolbar-actions button{border:1px solid #cbd7e4;background:#fff;color:#155fa0;border-radius:9px;padding:9px 11px;font-size:12px;font-weight:750;white-space:nowrap}.toronto-parity-toolbar-actions button:hover{background:#f3f8fd}.toronto-parity-toolbar-actions small{font-size:11px;color:#5f6d7d;white-space:nowrap}.toronto-watchlist-toolbar{grid-template-columns:1fr auto}.toronto-watchlist-toolbar .toronto-parity-toolbar-actions{justify-content:flex-start}\n@media(max-width:980px){.toronto-parity-toolbar-actions{justify-content:flex-start;flex-wrap:wrap}.toronto-watchlist-toolbar{grid-template-columns:1fr 1fr}}\n@media(max-width:600px){.toronto-watchlist-toolbar{grid-template-columns:1fr}.toronto-parity-toolbar-actions button{width:100%}}\n"""
        CSS.write_text(style, encoding='utf-8')

    print('TORONTO_COMMERCIAL_EXPORT_UI_PATCH=APPLIED')


if __name__ == '__main__':
    main()
