import { useEffect, useMemo, useState } from 'react'
import { loadChanges, loadCompanies, loadProcurement, loadSystems } from '../data/api'
import type { WorkflowUser } from '../types/workflow'

interface HomeSummary {
  registeredSystems: number
  highPriorityAccounts: number
  recentChanges: number
  procurementRecords: number
  observedCompanies: number
  generatedAt: string
}

const TORONTO_ENABLED = import.meta.env.VITE_ENABLE_TORONTO === 'true'

function go(hash: string) {
  window.location.hash = hash
}

function displayName(user: WorkflowUser): string {
  return user.name?.trim() || user.email.split('@')[0] || 'TowerSignal user'
}

export function HomePage({ user }: { user: WorkflowUser }) {
  const [summary, setSummary] = useState<HomeSummary | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([loadSystems(), loadChanges(), loadProcurement(), loadCompanies()])
      .then(([systems, changes, procurement, companies]) => {
        setSummary({
          registeredSystems: systems.summary.registered_systems,
          highPriorityAccounts: systems.systems.filter(row => row.priority_score >= 70).length,
          recentChanges: changes.new_event_count,
          procurementRecords: procurement.cityRecord.notices.length + procurement.checkbook.contracts.length + (procurement.nysAuthorities?.contracts.length ?? 0),
          observedCompanies: companies.summary.observed_vendor_company_count,
          generatedAt: systems.metadata.generated_at,
        })
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Unable to load Home summary.'))
  }, [])

  const firstName = useMemo(() => displayName(user).split(/\s+/)[0], [user])

  return <main className="portal-page home-portal-page">
    <header className="portal-header">
      <button className="portal-brand" onClick={() => go('#/home')} aria-label="TowerSignal Home"><span className="auth-brand-mark small">TS</span><strong>TowerSignal</strong></button>
      <nav aria-label="TowerSignal portal navigation">
        <button className="active" onClick={() => go('#/home')}>Home</button>
        <button onClick={() => go('#/prospect')}>Prospect</button>
        <button onClick={() => go('#/opportunities')}>Opportunities</button>
        <button onClick={() => go('#/companies')}>Companies</button>
        <button onClick={() => go('#/workflow')}>Workflow</button>
      </nav>
      <button className="portal-account-button" onClick={() => go('#/my-account')}>My account</button>
    </header>

    <section className="portal-content">
      <div className="home-hero">
        <div>
          <span className="page-kicker">Authenticated commercial intelligence workspace</span>
          <h1>Good morning, {firstName}.</h1>
          <p>Start with the accounts, procurement changes and vendor relationships that deserve commercial attention. Priority Score 1.0 remains the deterministic account-timing signal; no acquisition or Opportunity Score is implied here.</p>
        </div>
        <button className="primary home-primary-action" onClick={() => go('#/prospect')}>Open Prospect workspace</button>
      </div>

      {error && <div className="portal-alert" role="alert"><strong>Home summary unavailable</strong><span>{error}</span></div>}
      {!summary && !error && <div className="portal-loading">Loading current TowerSignal summary…</div>}
      {summary && <div className="home-metric-grid" aria-label="TowerSignal Home summary">
        <article><small>NYC registered systems</small><strong>{summary.registeredSystems.toLocaleString()}</strong><span>Current source-backed account universe</span></article>
        <article><small>High-priority accounts</small><strong>{summary.highPriorityAccounts.toLocaleString()}</strong><span>Priority Score 1.0 ≥ 70</span></article>
        <article><small>New deterministic changes</small><strong>{summary.recentChanges.toLocaleString()}</strong><span>Current history-build delta</span></article>
        <article><small>Procurement observations</small><strong>{summary.procurementRecords.toLocaleString()}</strong><span>NYC + statewide NY authority sources</span></article>
        <article><small>Observed vendor companies</small><strong>{summary.observedCompanies.toLocaleString()}</strong><span>Conservative company identities</span></article>
      </div>}

      <div className="home-workspace-grid">
        <button onClick={() => go('#/prospect')}><span>01</span><strong>Prospect</strong><p>Find accounts with actionable timing and evidence.</p></button>
        <button onClick={() => go('#/monitor')}><span>02</span><strong>Monitor</strong><p>Review deterministic changes across the market.</p></button>
        <button onClick={() => go('#/opportunities')}><span>03</span><strong>Opportunities</strong><p>Inspect live source-backed procurement activity.</p></button>
        <button onClick={() => go('#/companies')}><span>04</span><strong>Companies</strong><p>Review observed vendors, customers and contracts.</p></button>
        <button onClick={() => go('#/map')}><span>05</span><strong>Map</strong><p>Explore the current account universe geographically.</p></button>
        <button onClick={() => go('#/workflow')}><span>06</span><strong>Workflow</strong><p>Open your private watchlists, notes and next actions.</p></button>
        {TORONTO_ENABLED && <button onClick={() => go('#/toronto')}><span>07</span><strong>Toronto Beta</strong><p>Explore the isolated municipal property and evidence universe.</p></button>}
      </div>

      <section className="home-methodology-note">
        <div><span className="eyebrow">Current model boundary</span><h2>Evidence before scoring</h2></div>
        <p>Deal Intelligence validation remains coverage-limited. Opportunity Score 2.0 and acquisition-oriented Home recommendations stay disabled until the expanded procurement backtest meets its fixed validation gate.</p>
      </section>
    </section>
  </main>
}
