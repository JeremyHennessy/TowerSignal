"""Apply exact, bounded UI edits on the isolated branch, never main."""
from pathlib import Path
import hashlib

expected = {'src/components/SystemTable.tsx': 'c815293fc77d26c8df3f1713f816e1326334f22bd4f953c648a726dc8f27a12e', 'src/components/Filters.tsx': '2e43948e467e59ba6844b6e9f66d1b339cfce44d66e5b9de3464d0e25076595c', 'src/components/DetailPanel.tsx': 'b89790a7736cb2fc26b2d8f289a191656898956f35021804bba62d54fac9bc16', 'src/components/ChangesView.tsx': 'd50e6c0436415c43b6a0b73b5a0dd081d354af5fb4d2028ce051941e7113e895', '.github/workflows/pages.yml': '6282e8eacd198a04c3172b356f0d374f515d9e48a4be5c061eece2ea9f686afe', 'tests/e2e/property-enforcement.spec.ts': '0a4d8c023a34f072e26e387189503a12209b1732fd697c0ad7db9d20c132c37b'}
contents = {}
for name, digest in expected.items():
    data = Path(name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == digest, 'Baseline changed: ' + name
    contents[name] = data.decode()

def replace(name, old, new):
    assert contents[name].count(old) == 1, 'Non-unique edit: ' + name + ' ' + old[:80]
    contents[name] = contents[name].replace(old, new)

name = 'src/components/SystemTable.tsx'
replace(name, "import { useEffect, useMemo, useState }", "import { useMemo, useState }")
replace(name, 'LegionellaAlertPayload, PropertyEnforcementSummaryFields', 'PropertyEnforcementSummaryFields')
replace(name, "import { StatusBadge } from './StatusBadge'", "import { StatusBadge } from './StatusBadge'\nimport { LegionellaLinksPanel } from './LegionellaLinksPanel'\nimport type { LegionellaSummary } from '../types/legionella'")
replace(name, 'type EnrichedSystemSummary = SystemSummary & AcrisSummaryFields & PropertyEnforcementSummaryFields', 'type EnrichedSystemSummary = SystemSummary & AcrisSummaryFields & PropertyEnforcementSummaryFields & LegionellaSummary')
start = contents[name].index('  const [legionella, setLegionella]')
end = contents[name].index('  const sorted =', start)
contents[name] = contents[name][:start] + contents[name][end:]
start = contents[name].index('  const latestLegionellaItems =')
end = contents[name].index('  return <>', start)
contents[name] = contents[name][:start] + contents[name][end:]
start = contents[name].index('    {legionella &&')
end = contents[name].index('    <div className="table-card account-table-card">', start)
contents[name] = contents[name][:start] + '    <LegionellaLinksPanel />\n' + contents[name][end:]
replace(name, '        const hasActivity = ', "        const namedEvent = (enriched.legionella_named_event_ids?.length ?? 0) > 0\n        const areaEvent = (enriched.legionella_area_only_event_ids?.length ?? 0) > 0\n        const hasActivity = namedEvent || areaEvent || ")
replace(name, '<td><div className="activity-stack">', '<td><div className="activity-stack">{namedEvent && <span title="Officially named building; individual tower system unspecified">Legionella · named building</span>}{areaEvent && <span title="ZIP context only, not a test result">Legionella · area context</span>}')
name = 'src/components/Filters.tsx'
contents[name] = "import type { LegionellaSummary } from '../types/legionella'\n" + contents[name]
replace(name, 'export interface FilterState {\n', "export interface FilterState {\n  legionellaEvent?: string; legionellaMatch?: string;\n")
replace(name, 'export const initialFilters: FilterState = {\n', "export const initialFilters: FilterState = {\n  legionellaEvent: '', legionellaMatch: '',\n")
replace(name, '    const acris = row as SystemSummary & AcrisSummaryFields\n', "    const acris = row as SystemSummary & AcrisSummaryFields\n    const outbreak = row as SystemSummary & LegionellaSummary\n    const eventIds = filters.legionellaMatch === 'named' ? outbreak.legionella_named_event_ids : filters.legionellaMatch === 'area' ? outbreak.legionella_area_only_event_ids : outbreak.legionella_event_ids\n    if (filters.legionellaEvent && !eventIds?.includes(filters.legionellaEvent)) return false\n    if (filters.legionellaMatch && !eventIds?.length) return false\n")
replace(name, 'const labels: Partial<Record<keyof FilterState, string>> = {\n', "const labels: Partial<Record<keyof FilterState, string>> = {\n  legionellaEvent: 'Legionnaires incident', legionellaMatch: 'Incident match',\n")
replace(name, "filter(([, entry]) => entry !== '')", 'filter(([, entry]) => Boolean(entry))')
replace(name, '    <div className="filter-grid filter-stack">\n', '''    <div className="filter-grid filter-stack">
      <label>Legionnaires incident<select value={value.legionellaEvent ?? ''} onChange={e => set('legionellaEvent', e.target.value)} disabled={!rows.some(row => (row as LegionellaSummary).legionella_event_ids)}><option value="">All reviewed incidents</option><option value="nyc-2026-south-bronx">South Bronx · 2026</option><option value="nyc-2026-upper-east-side">Upper East Side · 2026</option></select></label>
      <label>Incident match<select value={value.legionellaMatch ?? ''} onChange={e => set('legionellaMatch', e.target.value)} disabled={!rows.some(row => (row as LegionellaSummary).legionella_event_ids)}><option value="">Named buildings + ZIP context</option><option value="named">Officially named building</option><option value="area">Area context only</option></select></label>
''')
name = 'src/components/DetailPanel.tsx'
contents[name] = "import { LegionellaLinksPanel } from './LegionellaLinksPanel'\n" + contents[name]
replace(name, '      <PlanimetricTowerSection detail={detail} />', '      <LegionellaLinksPanel systemId={row.system_id} />\n      <PlanimetricTowerSection detail={detail} />')
name = 'src/components/ChangesView.tsx'
contents[name] = "import { LegionellaLinksPanel } from './LegionellaLinksPanel'\n" + contents[name]
replace(name, '  return <section className="changes-view changes-table-view" aria-label="TowerSignal changes">\n', '  return <section className="changes-view changes-table-view" aria-label="TowerSignal changes">\n    <details className="legionella-monitor-details"><summary>Public-health incidents linked to tower accounts</summary><LegionellaLinksPanel /></details>\n')
name = '.github/workflows/pages.yml'
replace(name, '      - name: Python fixture tests\n', '''      - name: Resolve official Legionnaires building lists and geographic context
        run: |
          command -v pdftotext || (sudo apt-get update -qq && sudo apt-get install -y poppler-utils)
          python scripts/build_legionella_tower_links.py --data public/data --previous-cache .history-store/data/history/legionella-tower-links.json
          python scripts/validate_legionella_tower_links.py --data public/data --max-age-days 1
      - name: Python fixture tests
''')
replace(name, '            public/data/legionella-alerts.json\n', '            public/data/legionella-alerts.json\n            public/data/legionella-tower-links.json\n')
replace(name, '          cp .verified-history/legionella-alerts.json data/history/legionella-alerts.json\n', '          cp .verified-history/legionella-alerts.json data/history/legionella-alerts.json\n          cp .verified-history/legionella-tower-links.json data/history/legionella-tower-links.json\n')
name = 'tests/e2e/property-enforcement.spec.ts'
replace(name, "await expect(alerts).toContainText('official channels')", "await expect(alerts).toContainText('Legionnaires incidents linked to towers')")
replace(name, "await expect(alerts.getByRole('link', { name: 'Open official source' }).first()).toBeVisible()", "await expect(alerts.getByRole('link', { name: 'View named systems' }).first()).toBeVisible()")
for name, text in contents.items():
    Path(name).write_text(text)
    print(name, hashlib.sha256(text.encode()).hexdigest())
