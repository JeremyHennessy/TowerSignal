from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text(encoding='utf-8')
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{path}: expected exactly one match, found {count}: {old[:120]!r}')
    p.write_text(text.replace(old, new, 1), encoding='utf-8')


# Load the new stylesheet last enough to intentionally override the older account/workflow density layers.
replace_once(
    'src/main.tsx',
    "import './styles/account-report-density-final.css'\nimport './styles/known-firms.css'",
    "import './styles/account-report-density-final.css'\nimport './styles/workflow-account-round2.css'\nimport './styles/known-firms.css'",
)

# Account profile: add the decision layer, real profile modes and unified timeline without rewriting source sections.
replace_once(
    'src/components/DetailPanel.tsx',
    "import type { ChangeEvent } from '../types/history'\n",
    "import type { ChangeEvent } from '../types/history'\nimport type { WorkflowAccountState } from '../types/workflow'\n",
)
replace_once(
    'src/components/DetailPanel.tsx',
    "import { LegacyDobProjectSection } from './LegacyDobProjectSection'\n",
    "import { LegacyDobProjectSection } from './LegacyDobProjectSection'\nimport { AccountDecisionSummary } from './AccountDecisionSummary'\nimport { AccountModeTabs } from './AccountModeTabs'\nimport { AccountUnifiedTimeline } from './AccountUnifiedTimeline'\n",
)
replace_once(
    'src/components/DetailPanel.tsx',
    "export function DetailPanel({ row, metadata, historyEvents, historyStartedAt, workflowSection, onClose }: { row: SystemSummary | null; metadata: Metadata; historyEvents: ChangeEvent[]; historyStartedAt: string; workflowSection?: ReactNode; onClose: () => void }) {",
    "export function DetailPanel({ row, metadata, historyEvents, historyStartedAt, workflowAccount, workflowSection, onClose }: { row: SystemSummary | null; metadata: Metadata; historyEvents: ChangeEvent[]; historyStartedAt: string; workflowAccount?: WorkflowAccountState; workflowSection?: ReactNode; onClose: () => void }) {",
)
replace_once(
    'src/components/DetailPanel.tsx',
    "    {detail && <>\n      <TechnicianFieldPack row={row} detail={detail} />",
    "    {detail && <>\n      <AccountDecisionSummary row={row} detail={detail} historyEvents={historyEvents} workflowAccount={workflowAccount} />\n      <AccountModeTabs />\n      <TechnicianFieldPack row={row} detail={detail} />",
)
replace_once(
    'src/components/DetailPanel.tsx',
    "      <section><h3>Historical profile</h3>",
    "      <AccountUnifiedTimeline detail={detail} historyEvents={historyEvents} />\n      <section><h3>Historical profile</h3>",
)

# App navigation: preserve Workflow origin/scroll and pass the single workflow persistence owner into the command center.
replace_once(
    'src/App.tsx',
    "const filterKeys = Object.keys(initialFilters) as Array<keyof FilterState>\n",
    "const filterKeys = Object.keys(initialFilters) as Array<keyof FilterState>\nconst ACCOUNT_RETURN_KEY = 'towersignal.account-return.v1'\n\nfunction readAccountReturn(): { mode: ProductMode; scrollY: number } | null {\n  try {\n    const value = window.sessionStorage.getItem(ACCOUNT_RETURN_KEY)\n    if (!value) return null\n    const parsed = JSON.parse(value) as { mode?: ProductMode; scrollY?: number }\n    if (!parsed.mode || !validModes.has(parsed.mode)) return null\n    return { mode: parsed.mode, scrollY: typeof parsed.scrollY === 'number' ? parsed.scrollY : 0 }\n  } catch {\n    return null\n  }\n}\n",
)
replace_once(
    'src/App.tsx',
    "  const [returnMode, setReturnMode] = useState<ProductMode>('prospect')",
    "  const [returnMode, setReturnMode] = useState<ProductMode>(() => initialRoute.mode === 'account' ? (readAccountReturn()?.mode ?? 'prospect') : 'prospect')",
)
replace_once(
    'src/App.tsx',
    "  const navigate = useCallback((next: ProductMode) => {\n    if (next === 'account' || next === 'nys-account' || next === 'company') return\n    setMode(next)\n    setSelected(null)\n    setSelectedNys(null)\n    setSelectedCompanyId(null)\n    window.location.hash = routeHash(next)\n  }, [])",
    "  const navigate = useCallback((next: ProductMode) => {\n    if (next === 'account' || next === 'nys-account' || next === 'company') return\n    const returnState = next === 'workflow' ? readAccountReturn() : null\n    setMode(next)\n    setSelected(null)\n    setSelectedNys(null)\n    setSelectedCompanyId(null)\n    window.location.hash = routeHash(next)\n    if (next === 'workflow' && returnState?.mode === 'workflow') {\n      window.setTimeout(() => window.scrollTo({ top: returnState.scrollY, behavior: 'auto' }), 80)\n    }\n  }, [])",
)
replace_once(
    'src/App.tsx',
    "  const openAccount = useCallback((row: SystemSummary) => {\n    setReturnMode(mode === 'account' || mode === 'nys-account' || mode === 'company' ? 'prospect' : mode)\n    setSelected(row)\n    setMode('account')\n    window.location.hash = routeHash('account', row.system_id)\n  }, [mode])",
    "  const openAccount = useCallback((row: SystemSummary) => {\n    const origin = mode === 'account' || mode === 'nys-account' || mode === 'company' ? 'prospect' : mode\n    setReturnMode(origin)\n    if (origin === 'workflow') {\n      window.sessionStorage.setItem(ACCOUNT_RETURN_KEY, JSON.stringify({ mode: 'workflow', scrollY: window.scrollY }))\n    }\n    setSelected(row)\n    setMode('account')\n    window.location.hash = routeHash('account', row.system_id)\n  }, [mode])",
)
replace_once(
    'src/App.tsx',
    "{mode === 'workflow' && <WorkflowWorkspacePage user={workflow.user} systems={payload.systems} accounts={workflow.accounts} watchlists={workflow.watchlists} memberships={workflow.memberships} savedViews={workflow.savedViews} onOpenAccount={openAccount} />}",
    "{mode === 'workflow' && <WorkflowWorkspacePage user={workflow.user} busy={workflow.busy} systems={payload.systems} accounts={workflow.accounts} watchlists={workflow.watchlists} memberships={workflow.memberships} savedViews={workflow.savedViews} onSaveAccount={workflow.saveAccount} onToggleMembership={workflow.toggleMembership} onOpenAccount={openAccount} />}",
)
replace_once(
    'src/App.tsx',
    "historyStartedAt={changes.history_started_at} workflowSection={",
    "historyStartedAt={changes.history_started_at} workflowAccount={workflowAccount} workflowSection={",
)
replace_once(
    'src/App.tsx',
    ">← Back</button><span>New York City · account profile</span>",
    ">{returnMode === 'workflow' ? '← Back to Workflow' : '← Back'}</button><span>New York City · account profile</span>",
)

# Workflow page prop plumbing.
replace_once(
    'src/components/WorkflowWorkspacePage.tsx',
    "import type { WorkflowAccountState, WorkflowMembership, WorkflowSavedView, WorkflowUser, WorkflowWatchlist } from '../types/workflow'\n",
    "import type { WorkflowAccountPatch, WorkflowAccountState, WorkflowMembership, WorkflowSavedView, WorkflowUser, WorkflowWatchlist } from '../types/workflow'\nimport type { WorkflowSaveResult } from '../workflow/useWorkflow'\n",
)
replace_once(
    'src/components/WorkflowWorkspacePage.tsx',
    "  user,\n  systems,",
    "  user,\n  busy,\n  systems,",
)
replace_once(
    'src/components/WorkflowWorkspacePage.tsx',
    "  savedViews,\n  onOpenAccount,",
    "  savedViews,\n  onSaveAccount,\n  onToggleMembership,\n  onOpenAccount,",
)
replace_once(
    'src/components/WorkflowWorkspacePage.tsx',
    "  user: WorkflowUser | null\n  systems: WorkflowSystem[]",
    "  user: WorkflowUser | null\n  busy: boolean\n  systems: WorkflowSystem[]",
)
replace_once(
    'src/components/WorkflowWorkspacePage.tsx',
    "  savedViews: WorkflowSavedView[]\n  onOpenAccount: (row: WorkflowSystem) => void",
    "  savedViews: WorkflowSavedView[]\n  onSaveAccount: (systemId: string, patch: WorkflowAccountPatch) => Promise<WorkflowSaveResult>\n  onToggleMembership: (systemId: string, watchlistId: string, enabled: boolean) => Promise<void>\n  onOpenAccount: (row: WorkflowSystem) => void",
)
replace_once(
    'src/components/WorkflowWorkspacePage.tsx',
    "    <WorkflowScaleWorkspace systems={scopedRows} marketCount={systems.length} accounts={accounts} watchlists={watchlists} memberships={memberships} savedViews={savedViews} recentEvents={recentEvents.filter(event => scopeIds.has(event.system_id))} eventsBySystem={eventsBySystem} today={today} onOpenAccount={onOpenAccount} />",
    "    <WorkflowScaleWorkspace systems={scopedRows} marketCount={systems.length} accounts={accounts} watchlists={watchlists} memberships={memberships} savedViews={savedViews} recentEvents={recentEvents.filter(event => scopeIds.has(event.system_id))} eventsBySystem={eventsBySystem} today={today} signedIn={Boolean(user)} busy={busy} onSaveAccount={onSaveAccount} onToggleMembership={onToggleMembership} onOpenAccount={onOpenAccount} />",
)

# Workflow command center: state restoration, inline edits, safe page selection/bulk actions, useful saved-view shortcuts and zero-noise strips.
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "import type { AccountDisposition, WorkflowAccountState, WorkflowMembership, WorkflowSavedView, WorkflowWatchlist } from '../types/workflow'\n",
    "import type { AccountDisposition, WorkflowAccountPatch, WorkflowAccountState, WorkflowMembership, WorkflowSavedView, WorkflowWatchlist } from '../types/workflow'\n",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "import { TowerMap } from './TowerMap'\n",
    "import { TowerMap } from './TowerMap'\nimport { WorkflowQuickEditor } from './WorkflowQuickEditor'\n",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "type SortKey = 'address' | 'status' | 'next_action' | 'priority' | 'changes'\n",
    "type SortKey = 'address' | 'status' | 'next_action' | 'priority' | 'changes'\n\ntype WorkspaceState = {\n  tab: WorkspaceTab\n  accountView: AccountView\n  query: string\n  statusFilter: StatusFilter\n  watchlistFilter: string\n  boroughFilter: string\n  attentionFilter: AttentionFilter\n  selectedId: string | null\n  sort: { key: SortKey; dir: 'asc' | 'desc' }\n}\n\nconst WORKSPACE_STATE_KEY = 'towersignal.workflow.workspace.v2'\n\nfunction readWorkspaceState(): Partial<WorkspaceState> {\n  try {\n    const raw = window.sessionStorage.getItem(WORKSPACE_STATE_KEY)\n    return raw ? JSON.parse(raw) as Partial<WorkspaceState> : {}\n  } catch {\n    return {}\n  }\n}\n",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "  today: string\n  onOpenAccount: (row: T) => void",
    "  today: string\n  signedIn: boolean\n  busy: boolean\n  onSaveAccount: (systemId: string, patch: WorkflowAccountPatch) => Promise<'synced' | 'session-only'>\n  onToggleMembership: (systemId: string, watchlistId: string, enabled: boolean) => Promise<void>\n  onOpenAccount: (row: T) => void",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "  today,\n  onOpenAccount,\n}: Props<T>) {\n  const [tab, setTab] = useState<WorkspaceTab>('accounts')\n  const [accountView, setAccountView] = useState<AccountView>('split')\n  const [query, setQuery] = useState('')\n  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')\n  const [watchlistFilter, setWatchlistFilter] = useState('all')\n  const [boroughFilter, setBoroughFilter] = useState('all')\n  const [attentionFilter, setAttentionFilter] = useState<AttentionFilter>('all')\n  const [selectedId, setSelectedId] = useState<string | null>(null)",
    "  today,\n  signedIn,\n  busy,\n  onSaveAccount,\n  onToggleMembership,\n  onOpenAccount,\n}: Props<T>) {\n  const initialWorkspace = useMemo(readWorkspaceState, [])\n  const [tab, setTab] = useState<WorkspaceTab>(initialWorkspace.tab ?? 'accounts')\n  const [accountView, setAccountView] = useState<AccountView>(initialWorkspace.accountView ?? 'split')\n  const [query, setQuery] = useState(initialWorkspace.query ?? '')\n  const [statusFilter, setStatusFilter] = useState<StatusFilter>(initialWorkspace.statusFilter ?? 'all')\n  const [watchlistFilter, setWatchlistFilter] = useState(initialWorkspace.watchlistFilter ?? 'all')\n  const [boroughFilter, setBoroughFilter] = useState(initialWorkspace.boroughFilter ?? 'all')\n  const [attentionFilter, setAttentionFilter] = useState<AttentionFilter>(initialWorkspace.attentionFilter ?? 'all')\n  const [selectedId, setSelectedId] = useState<string | null>(initialWorkspace.selectedId ?? null)",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>({ key: 'priority', dir: 'desc' })",
    "  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' }>(initialWorkspace.sort ?? { key: 'priority', dir: 'desc' })\n  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())\n  const [bulkStatus, setBulkStatus] = useState<AccountDisposition>('investigate')\n  const [bulkWatchlistId, setBulkWatchlistId] = useState('')\n  const [bulkMembershipAction, setBulkMembershipAction] = useState<'add' | 'remove'>('add')\n  const [bulkMessage, setBulkMessage] = useState<string | null>(null)",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "  useEffect(() => { setPage(0); setEventPage(0); setActionPage(0) }, [query, statusFilter, watchlistFilter, boroughFilter, attentionFilter])\n  useEffect(() => { if (selectedId && !rowById.has(selectedId)) setSelectedId(null) }, [rowById, selectedId])",
    "  useEffect(() => { setPage(0); setEventPage(0); setActionPage(0); setSelectedIds(new Set()) }, [query, statusFilter, watchlistFilter, boroughFilter, attentionFilter])\n  useEffect(() => { if (selectedId && !rowById.has(selectedId)) setSelectedId(null) }, [rowById, selectedId])\n  useEffect(() => {\n    window.sessionStorage.setItem(WORKSPACE_STATE_KEY, JSON.stringify({ tab, accountView, query, statusFilter, watchlistFilter, boroughFilter, attentionFilter, selectedId, sort }))\n  }, [tab, accountView, query, statusFilter, watchlistFilter, boroughFilter, attentionFilter, selectedId, sort])",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "  const tabCounts = { accounts: filteredRows.length, changes: filteredEvents.length, actions: actionRows.length }\n",
    "  const tabCounts = { accounts: filteredRows.length, changes: filteredEvents.length, actions: actionRows.length }\n  const visiblePageIds = visibleRows.map(row => row.system_id)\n  const allVisibleSelected = visiblePageIds.length > 0 && visiblePageIds.every(id => selectedIds.has(id))\n  const toggleSelected = (systemId: string, checked: boolean) => setSelectedIds(current => { const next = new Set(current); if (checked) next.add(systemId); else next.delete(systemId); return next })\n  const toggleVisiblePage = (checked: boolean) => setSelectedIds(current => { const next = new Set(current); visiblePageIds.forEach(id => checked ? next.add(id) : next.delete(id)); return next })\n  const applyBulkStatus = async () => {\n    if (!signedIn || selectedIds.size === 0) return\n    const ids = [...selectedIds]\n    const results = await Promise.all(ids.map(systemId => {\n      const current = accountById.get(systemId)\n      return onSaveAccount(systemId, { status: bulkStatus, note: current?.note ?? '', next_action_date: current?.next_action_date ?? null })\n    }))\n    const sessionOnly = results.filter(result => result === 'session-only').length\n    setBulkMessage(sessionOnly ? `${ids.length} updated; ${sessionOnly} could not confirm cross-device sync.` : `${ids.length} account${ids.length === 1 ? '' : 's'} updated and synced.`)\n  }\n  const applyBulkWatchlist = async () => {\n    if (!signedIn || !bulkWatchlistId || selectedIds.size === 0) return\n    const ids = [...selectedIds]\n    const results = await Promise.allSettled(ids.map(systemId => onToggleMembership(systemId, bulkWatchlistId, bulkMembershipAction === 'add')))\n    const failed = results.filter(result => result.status === 'rejected').length\n    setBulkMessage(failed ? `${ids.length - failed} watchlist changes applied; ${failed} failed.` : `${ids.length} watchlist change${ids.length === 1 ? '' : 's'} applied.`)\n  }\n  const applySavedView = (view: WorkflowSavedView) => {\n    setQuery(view.filters.search ?? '')\n    setBoroughFilter(view.filters.borough || 'all')\n    setAttentionFilter(Number(view.filters.minScore || 0) >= 70 ? 'high' : 'all')\n    setTab('accounts')\n  }\n",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "<div className=\"workflow-pipeline-strip\" aria-label=\"Workflow status distribution\"><span>Pipeline</span><button className={statusFilter === 'none' ? 'active' : ''} onClick={() => setStatusFilter(current => current === 'none' ? 'all' : 'none')}>No status <strong>{statusCounts.get('none') ?? 0}</strong></button>{statuses.map(status => <button key={status.value} className={statusFilter === status.value ? 'active' : ''} onClick={() => setStatusFilter(current => current === status.value ? 'all' : status.value)}>{status.label} <strong>{statusCounts.get(status.value) ?? 0}</strong></button>)}</div>",
    "<div className=\"workflow-pipeline-strip\" aria-label=\"Workflow status distribution\"><span>Pipeline</span>{((statusCounts.get('none') ?? 0) > 0 || statusFilter === 'none') && <button className={statusFilter === 'none' ? 'active' : ''} onClick={() => setStatusFilter(current => current === 'none' ? 'all' : 'none')}>No status <strong>{statusCounts.get('none') ?? 0}</strong></button>}{statuses.filter(status => (statusCounts.get(status.value) ?? 0) > 0 || statusFilter === status.value).map(status => <button key={status.value} className={statusFilter === status.value ? 'active' : ''} onClick={() => setStatusFilter(current => current === status.value ? 'all' : status.value)}>{status.label} <strong>{statusCounts.get(status.value) ?? 0}</strong></button>)}</div>",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "{watchlists.length > 0 && <div className=\"workflow-watchlist-shortcuts\"><span>Watchlists</span>{watchlists.slice(0, 8).map(watchlist => <button key={watchlist.id} className={watchlistFilter === watchlist.id ? 'active' : ''} onClick={() => setWatchlistFilter(current => current === watchlist.id ? 'all' : watchlist.id)}>{watchlist.name}<strong>{watchlistCounts.get(watchlist.id) ?? 0}</strong></button>)}</div>}",
    "{watchlists.some(watchlist => (watchlistCounts.get(watchlist.id) ?? 0) > 0 || watchlistFilter === watchlist.id) && <div className=\"workflow-watchlist-shortcuts\"><span>Watchlists</span>{watchlists.filter(watchlist => (watchlistCounts.get(watchlist.id) ?? 0) > 0 || watchlistFilter === watchlist.id).slice(0, 8).map(watchlist => <button key={watchlist.id} className={watchlistFilter === watchlist.id ? 'active' : ''} onClick={() => setWatchlistFilter(current => current === watchlist.id ? 'all' : watchlist.id)}>{watchlist.name}<strong>{watchlistCounts.get(watchlist.id) ?? 0}</strong></button>)}</div>}",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "    <div className=\"workflow-command-grid\"><div className=\"workflow-command-primary\">",
    "    {selectedIds.size > 0 && <div className=\"workflow-bulk-bar\" aria-label=\"Bulk workflow actions\"><strong>{selectedIds.size} selected</strong><label>Status<select value={bulkStatus} onChange={event => setBulkStatus(event.target.value as AccountDisposition)}>{statuses.map(status => <option key={status.value} value={status.value}>{status.label}</option>)}</select><button className=\"primary\" disabled={!signedIn || busy} onClick={() => void applyBulkStatus()}>Apply</button></label>{watchlists.length > 0 && <label>Watchlist<select value={bulkMembershipAction} onChange={event => setBulkMembershipAction(event.target.value as 'add' | 'remove')}><option value=\"add\">Add to</option><option value=\"remove\">Remove from</option></select><select value={bulkWatchlistId} onChange={event => setBulkWatchlistId(event.target.value)}><option value=\"\">Choose list</option>{watchlists.map(watchlist => <option key={watchlist.id} value={watchlist.id}>{watchlist.name}</option>)}</select><button className=\"bulk-secondary\" disabled={!signedIn || busy || !bulkWatchlistId} onClick={() => void applyBulkWatchlist()}>Apply</button></label>}<button className=\"workflow-bulk-clear\" onClick={() => { setSelectedIds(new Set()); setBulkMessage(null) }}>Clear selection</button>{bulkMessage && <span className=\"workflow-bulk-message\">{bulkMessage}</span>}</div>}\n\n    <div className=\"workflow-command-grid\"><div className=\"workflow-command-primary\">",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "<thead><tr><th><button onClick={() => changeSort('address')}>Account{sortIndicator('address')}</button></th>",
    "<thead><tr><th className=\"workflow-select-cell\"><input type=\"checkbox\" aria-label=\"Select visible accounts\" checked={allVisibleSelected} onChange={event => toggleVisiblePage(event.target.checked)} /></th><th><button onClick={() => changeSort('address')}>Account{sortIndicator('address')}</button></th>",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "onKeyDown={event => { if (event.key === 'Enter') setSelectedId(row.system_id) }}><td className=\"account-cell\">",
    "onKeyDown={event => { if (event.key === 'Enter') setSelectedId(row.system_id) }}><td className=\"workflow-select-cell\" onClick={event => event.stopPropagation()}><input type=\"checkbox\" aria-label={`Select ${row.address ?? row.system_id}`} checked={selectedIds.has(row.system_id)} onChange={event => toggleSelected(row.system_id, event.target.checked)} /></td><td className=\"account-cell\">",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "{selectedAccount?.note && <div className=\"workflow-inspector-note\"><span>Private note</span><p>{selectedAccount.note}</p></div>}<button className=\"primary workflow-open-full\" onClick={() => onOpenAccount(selectedRow)}>Open account to manage →</button><p className=\"workflow-inspector-boundary\">Status, notes, next-action date and watchlist edits remain on the account workflow control so there is one verified persistence path.</p>",
    "{selectedAccount?.note && <div className=\"workflow-inspector-note\"><span>Private note</span><p>{selectedAccount.note}</p></div>}{signedIn && <WorkflowQuickEditor systemId={selectedRow.system_id} account={selectedAccount} watchlists={watchlists} membershipIds={new Set(membershipIdsBySystem.get(selectedRow.system_id) ?? [])} busy={busy} onSave={onSaveAccount} onToggleMembership={onToggleMembership} />}<button className=\"primary workflow-open-full\" onClick={() => onOpenAccount(selectedRow)}>Open full account →</button><p className=\"workflow-inspector-boundary\">Quick edits and the account page use the same workflow persistence owner. Open the full account for evidence, field and history context.</p>",
)
replace_once(
    'src/components/WorkflowScaleWorkspace.tsx',
    "{savedViews.length ? <div className=\"workflow-toolbox-list\">{savedViews.slice(0, 20).map(view => <span key={view.id}>▤ {view.name}</span>)}</div> : <p>No saved prospect views yet.</p>}",
    "{savedViews.length ? <div className=\"workflow-toolbox-list\">{savedViews.slice(0, 20).map(view => <button key={view.id} onClick={() => applySavedView(view)}>▤ {view.name}</button>)}</div> : <p>No saved prospect views yet.</p>}",
)

print('Applied Workflow + Account UX round 2 patches.')
