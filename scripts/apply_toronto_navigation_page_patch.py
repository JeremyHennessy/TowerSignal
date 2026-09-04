from pathlib import Path

path = Path('src/components/TorontoMarketPage.tsx')
text = path.read_text(encoding='utf-8')

text = text.replace("import { TorontoParityShell } from './TorontoParityShell'", "import { TorontoUnifiedWorkspace } from './TorontoUnifiedWorkspace'", 1)

old = """function currentPropertyId(): string | null {
  const parts = window.location.hash.replace(/^#\\/?/, '').split('?')[0].split('/').filter(Boolean)
  return parts[0] === 'toronto' && parts[1] ? decodeURIComponent(parts[1]) : null
}"""
new = """function currentPropertyId(): string | null {
  const parts = window.location.hash.replace(/^#\\/?/, '').split('?')[0].split('/').filter(Boolean)
  if (parts[0] !== 'toronto') return null
  if (parts[1] === 'market' && parts[2]) return decodeURIComponent(parts[2])
  const knownRoutes = new Set(['home', 'prospect', 'monitor', 'map', 'market', 'changes', 'opportunities', 'companies', 'portfolios', 'workflow', 'source-health', 'benchmarking', 'property', 'company', 'portfolio'])
  return parts[1] && !knownRoutes.has(parts[1]) ? decodeURIComponent(parts[1]) : null
}"""
if old not in text:
    raise SystemExit('currentPropertyId anchor changed')
text = text.replace(old, new, 1)

text = text.replace("function TorontoMarketExplorer() {", "function TorontoMarketExplorer({ initialView = 'table' }: { initialView?: 'table' | 'map' }) {", 1)
text = text.replace("const [view, setView] = useState<'table' | 'map'>('table')", "const [view, setView] = useState<'table' | 'map'>(initialView)", 1)
text = text.replace("window.location.hash = `#/toronto/${encodeURIComponent(property.property_id)}`", "window.location.hash = `#/toronto/market/${encodeURIComponent(property.property_id)}`", 1)
text = text.replace("window.location.hash = '#/toronto'", "window.location.hash = '#/toronto/market'", 1)

old = """export function TorontoMarketPage() {
  return <TorontoParityShell explorer={<TorontoMarketExplorer />} />
}"""
new = """export function TorontoMarketPage() {
  return <TorontoUnifiedWorkspace explorer={<TorontoMarketExplorer />} mapExplorer={<TorontoMarketExplorer initialView=\"map\" />} />
}"""
if old not in text:
    raise SystemExit('TorontoMarketPage export anchor changed')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')

css_path = Path('src/styles/toronto-parity.css')
css = css_path.read_text(encoding='utf-8')
addition = '''
.toronto-home-actions{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:16px}.toronto-home-actions button{display:grid;gap:5px;text-align:left;border:1px solid #dfe6ee;background:#fff;border-radius:14px;padding:16px;color:#223044}.toronto-home-actions button:hover{border-color:#99b6d1;background:#f7fbff}.toronto-home-actions button strong{font-size:15px}.toronto-home-actions button span{font-size:12px;color:#66758a}.toronto-drillthrough-page .account-profile-toolbar{margin-bottom:16px}.toronto-drillthrough-page .page-actions{display:flex;gap:8px;flex-wrap:wrap}.toronto-drillthrough-page .page-actions button,.toronto-drill-link{border:1px solid #cbd7e4;background:#fff;border-radius:9px;padding:9px 11px;font-size:12px;font-weight:700;color:#155fa0}.toronto-drill-link{display:grid;width:100%;gap:3px;text-align:left;margin-bottom:7px}.toronto-drill-link span{font-weight:500;color:#657488}.toronto-drill-link:disabled{cursor:default;color:#4d5968;background:#f7f8fa}.toronto-drillthrough-page .company-identity-card{min-width:210px}.toronto-drillthrough-page .reference-table tbody tr{cursor:pointer}
@media(max-width:1100px){.toronto-home-actions{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:600px){.toronto-home-actions{grid-template-columns:1fr}.toronto-drillthrough-page .product-page-heading{display:block}.toronto-drillthrough-page .company-identity-card{margin-top:12px;min-width:0}.toronto-drillthrough-page .page-actions{width:100%}.toronto-drillthrough-page .page-actions button{flex:1 1 auto}}
'''
if '.toronto-home-actions' not in css:
    css_path.write_text(css.rstrip() + '\n' + addition, encoding='utf-8')
