import { useEffect, useState, type FormEvent } from 'react'
import type { WorkflowUser } from '../types/workflow'

type AuthMode = 'sign-in' | 'sign-up'
type MarketingSection = 'platform' | 'workflow' | 'audience' | 'evidence'

const screenshot = (name: string) => `${import.meta.env.BASE_URL}marketing/${name}`

function isProtectedDeepLink(): boolean {
  const raw = window.location.hash.replace(/^#\/?/, '').split('?')[0]
  return Boolean(raw && raw !== 'home')
}

function scrollToSection(section: MarketingSection) {
  document.getElementById(section)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

export function AuthLandingPage({
  initialError,
  onSignIn,
  onSignUp,
}: {
  initialError?: string | null
  onSignIn: (email: string, password: string) => Promise<WorkflowUser>
  onSignUp: (name: string, email: string, password: string) => Promise<WorkflowUser>
}) {
  const protectedDeepLink = isProtectedDeepLink()
  const [mode, setMode] = useState<AuthMode>('sign-in')
  const [authOpen, setAuthOpen] = useState(protectedDeepLink || Boolean(initialError))
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(initialError ?? null)

  useEffect(() => {
    if (protectedDeepLink) setAuthOpen(true)
  }, [protectedDeepLink])

  useEffect(() => {
    if (!authOpen) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setAuthOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => {
      document.body.style.overflow = previousOverflow
      window.removeEventListener('keydown', onKeyDown)
    }
  }, [authOpen])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    const normalizedEmail = email.trim()
    const normalizedName = name.trim()
    if (mode === 'sign-up' && password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }
    if (mode === 'sign-up' && normalizedName.length < 2) {
      setError('Enter your name to create the account.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      if (mode === 'sign-up') await onSignUp(normalizedName, normalizedEmail, password)
      else await onSignIn(normalizedEmail, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed.')
    } finally {
      setBusy(false)
    }
  }

  const switchMode = (next: AuthMode) => {
    setMode(next)
    setError(null)
    setPassword('')
    setConfirmPassword('')
  }

  const openAuth = (next: AuthMode) => {
    switchMode(next)
    setAuthOpen(true)
  }

  return <main className="marketing-page">
    <header className="marketing-nav">
      <button className="marketing-brand" type="button" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} aria-label="TowerSignal home">
        <span className="auth-brand-mark small">TS</span><span>TowerSignal</span>
      </button>
      <nav className="marketing-nav-links" aria-label="Landing page navigation">
        <button type="button" onClick={() => scrollToSection('platform')}>Platform</button>
        <button type="button" onClick={() => scrollToSection('workflow')}>How it works</button>
        <button type="button" onClick={() => scrollToSection('audience')}>Who it’s for</button>
        <button type="button" onClick={() => scrollToSection('evidence')}>Evidence</button>
      </nav>
      <button className="marketing-login" type="button" onClick={() => openAuth('sign-in')}>Log in</button>
    </header>

    <section className="marketing-hero" aria-labelledby="marketing-hero-title">
      <div className="marketing-hero-copy">
        <span className="marketing-kicker"><i /> Commercial intelligence for water-service markets</span>
        <h1 id="marketing-hero-title">Know which accounts matter, <em>why now</em>, and what changed.</h1>
        <p>TowerSignal turns fragmented public cooling-tower, building, ownership and procurement records into source-backed commercial intelligence—so service teams can prioritize the right account and open the evidence behind it.</p>
        <div className="marketing-hero-actions">
          <button className="marketing-primary" type="button" onClick={() => scrollToSection('platform')}>Explore the platform <span aria-hidden="true">→</span></button>
          <button className="marketing-secondary" type="button" onClick={() => openAuth('sign-up')}>Create account</button>
        </div>
        <div className="marketing-trust-line" aria-label="TowerSignal product principles"><span>Deterministic signals</span><span>Traceable source evidence</span><span>Private workflow</span></div>
      </div>
      <div className="marketing-hero-product" aria-label="TowerSignal product preview">
        <div className="marketing-glow" />
        <div className="marketing-phone marketing-phone-main"><div className="marketing-phone-bar"><span /><span /><span /></div><img src={screenshot('towersignal-prospect-mobile.svg')} alt="TowerSignal Prospect workspace showing account priority and commercial timing signals" /></div>
        <div className="marketing-signal-card marketing-signal-card-top"><small>ACCOUNT INTELLIGENCE</small><strong>Priority + timing</strong><span>Move from a market-wide list to the accounts with the clearest reason to act.</span></div>
        <div className="marketing-signal-card marketing-signal-card-bottom"><small>EVIDENCE FIRST</small><strong>Open the source trail</strong><span>Each signal stays connected to the public record behind it.</span></div>
      </div>
    </section>

    <section className="marketing-proof-strip" aria-label="TowerSignal coverage summary">
      <div><strong>NYC</strong><span>Cooling-tower account intelligence</span></div><div><strong>Change</strong><span>Regulatory, building and ownership signals</span></div><div><strong>Buying</strong><span>Public procurement and vendor observations</span></div><div><strong>Workflow</strong><span>Watchlists, notes and next actions</span></div>
    </section>

    <section className="marketing-section marketing-platform" id="platform">
      <div className="marketing-section-heading"><span className="marketing-eyebrow">THE PLATFORM</span><h2>From public records to a usable commercial workflow.</h2><p>TowerSignal does more than aggregate data. It links account context, change signals, procurement evidence and company observations into one place designed for deciding what deserves attention next.</p></div>
      <div className="marketing-feature-grid">
        <article><span>01</span><h3>Prioritize accounts</h3><p>Surface accounts around deterministic timing signals instead of working an undifferentiated property list.</p></article>
        <article><span>02</span><h3>Detect meaningful change</h3><p>Track source-backed changes across cooling-tower, building, violation and property records.</p></article>
        <article><span>03</span><h3>See procurement activity</h3><p>Review relevant solicitations, awards, contracts, vendors and public buyers without treating observed contract values as company revenue.</p></article>
        <article><span>04</span><h3>Understand companies</h3><p>Connect conservative vendor identities to their observed public-customer and service history while keeping uncertain matches explicit.</p></article>
        <article><span>05</span><h3>Work the lead</h3><p>Keep account notes, watchlists, disposition and next actions beside the evidence that made the account interesting.</p></article>
        <article><span>06</span><h3>Verify the reason</h3><p>Move from score to source. TowerSignal is designed to show why a signal exists, not hide it behind an opaque recommendation.</p></article>
      </div>
    </section>

    <section className="marketing-product-stories" aria-label="TowerSignal product views">
      <article className="marketing-story">
        <div className="marketing-story-copy"><span className="marketing-eyebrow">PROSPECT</span><h2>Start with the accounts that have a reason to call now.</h2><p>Filter the NYC market by priority, sampling follow-up, violations, recent property activity and other account criteria. The goal is a smaller, explainable working set—not another giant spreadsheet.</p><ul><li>Market-wide account screening</li><li>Commercial timing signals</li><li>Fast drill-through to account evidence</li></ul></div>
        <div className="marketing-screenshot-stage"><div className="marketing-phone marketing-phone-story"><img src={screenshot('towersignal-prospect-mobile.svg')} alt="TowerSignal Prospect workspace on mobile" /></div></div>
      </article>
      <article className="marketing-story marketing-story-reverse">
        <div className="marketing-story-copy"><span className="marketing-eyebrow">ACCOUNT PROFILE</span><h2>See the account, the signal and the source trail together.</h2><p>Open a property to move from priority score to identity, source-backed account details and workflow. Lead briefs are designed to make the reason for outreach portable without stripping away the evidence.</p><ul><li>Shareable account profiles</li><li>Source-backed identity and history</li><li>Private notes and next-action workflow</li></ul></div>
        <div className="marketing-screenshot-stage marketing-screenshot-stage-dark"><div className="marketing-phone marketing-phone-story"><img src={screenshot('towersignal-account-mobile.svg')} alt="TowerSignal account profile showing a selected system and priority score" /></div></div>
      </article>
      <article className="marketing-story">
        <div className="marketing-story-copy"><span className="marketing-eyebrow">WORKSPACE</span><h2>Keep market intelligence in the same place you act on it.</h2><p>Prospecting, change monitoring, procurement, companies and personal workflow live in one authenticated workspace so account research does not get separated from follow-up.</p><ul><li>Prospect and Monitor workspaces</li><li>Company and procurement context</li><li>Saved user workflow tied to login</li></ul></div>
        <div className="marketing-screenshot-stage marketing-screenshot-stage-soft"><div className="marketing-phone marketing-phone-story"><img src={screenshot('towersignal-home-mobile.svg')} alt="TowerSignal authenticated Home workspace on mobile" /></div></div>
      </article>
    </section>

    <section className="marketing-section marketing-workflow" id="workflow">
      <div className="marketing-section-heading marketing-section-heading-light"><span className="marketing-eyebrow">HOW IT WORKS</span><h2>A defensible path from source to signal.</h2><p>The product is deliberately evidence-first: collect, normalize, link conservatively, then expose the reason behind each commercial signal.</p></div>
      <div className="marketing-process-grid"><article><span>1</span><div><h3>Collect</h3><p>Bring together authoritative cooling-tower, building, property and procurement records.</p></div></article><article><span>2</span><div><h3>Resolve</h3><p>Normalize records and link identities only where the evidence supports the relationship.</p></div></article><article><span>3</span><div><h3>Prioritize</h3><p>Turn observable account conditions and recent changes into deterministic timing signals.</p></div></article><article><span>4</span><div><h3>Act + verify</h3><p>Work the account, save context and open the underlying evidence whenever a decision needs support.</p></div></article></div>
    </section>

    <section className="marketing-section marketing-audience" id="audience">
      <div className="marketing-section-heading"><span className="marketing-eyebrow">WHO IT’S FOR</span><h2>Built for teams that sell, service and protect complex water systems.</h2><p>TowerSignal is most useful when account timing, compliance context and evidence all matter to the next commercial conversation.</p></div>
      <div className="marketing-audience-grid"><article><span>WT</span><h3>Water treatment providers</h3><p>Prioritize cooling-tower accounts, understand recent signals and carry evidence into outreach and account planning.</p></article><article><span>CT</span><h3>Cooling-tower service & maintenance</h3><p>Find properties where equipment, building activity or compliance context creates a defensible reason for attention.</p></article><article><span>LQ</span><h3>Legionella & water-quality teams</h3><p>Screen for sampling and compliance follow-up signals, then verify the underlying account record before outreach.</p></article><article><span>EH</span><h3>Industrial hygiene & environmental services</h3><p>Use source-backed building and regulatory context to identify accounts where specialist support may be relevant.</p></article></div>
    </section>

    <section className="marketing-section marketing-evidence" id="evidence">
      <div className="marketing-evidence-copy"><span className="marketing-eyebrow">EVIDENCE, NOT MYSTERY SCORES</span><h2>Public-source intelligence that stays auditable.</h2><p>TowerSignal’s NYC workspace is built from public records including cooling-tower registrations and inspections, DOB and OATH activity, property and ownership evidence, City Record, Checkbook NYC and New York State authority procurement data.</p><p className="marketing-evidence-note">Where identity or linkage is uncertain, the product is designed to keep that uncertainty visible rather than silently manufacture a relationship.</p></div>
      <div className="marketing-source-list" aria-label="Example TowerSignal source families"><div><strong>Cooling towers</strong><span>Registrations, inspections and equipment context</span></div><div><strong>Buildings + violations</strong><span>DOB, OATH and related property activity</span></div><div><strong>Ownership + property</strong><span>Source-backed identity and recorded property changes</span></div><div><strong>Procurement</strong><span>City Record, Checkbook NYC and NYS authority observations</span></div></div>
    </section>

    <section className="marketing-final-cta"><span className="marketing-eyebrow">TOWERSIGNAL</span><h2>Turn a fragmented market into an explainable next action.</h2><p>Start with the account. See why it matters. Keep the evidence attached.</p><div><button className="marketing-primary marketing-primary-light" type="button" onClick={() => openAuth('sign-up')}>Create account <span aria-hidden="true">→</span></button><button className="marketing-text-button" type="button" onClick={() => openAuth('sign-in')}>Already have access? Log in</button></div></section>

    <footer className="marketing-footer"><div className="marketing-brand marketing-brand-static"><span className="auth-brand-mark small">TS</span><span>TowerSignal</span></div><p>Commercial intelligence for water-service markets.</p><button type="button" onClick={() => openAuth('sign-in')}>Log in</button></footer>

    {authOpen && <div className="marketing-auth-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) setAuthOpen(false) }}>
      <section className="marketing-auth-modal" role="dialog" aria-modal="true" aria-labelledby="tower-auth-heading">
        <button className="marketing-auth-close" type="button" aria-label="Close login" onClick={() => setAuthOpen(false)}>×</button>
        <div className="auth-form-heading"><span className="eyebrow">Protected workspace</span><h2 id="tower-auth-heading">{mode === 'sign-up' ? 'Create your TowerSignal account' : 'Sign in to TowerSignal'}</h2><p>{mode === 'sign-up' ? 'Create a private workspace login to access the application.' : protectedDeepLink ? 'Sign in to continue to the TowerSignal page you requested.' : 'Sign in to open your TowerSignal workspace.'}</p></div>
        <div className="auth-mode-tabs" role="tablist" aria-label="Authentication mode"><button type="button" role="tab" aria-selected={mode === 'sign-in'} className={mode === 'sign-in' ? 'active' : ''} onClick={() => switchMode('sign-in')}>Sign in</button><button type="button" role="tab" aria-selected={mode === 'sign-up'} className={mode === 'sign-up' ? 'active' : ''} onClick={() => switchMode('sign-up')}>Create account</button></div>
        <form className="auth-form" onSubmit={event => void submit(event)}>
          {mode === 'sign-up' && <label>Full name<input aria-label="Full name" type="text" autoComplete="name" value={name} onChange={event => setName(event.target.value)} minLength={2} required /></label>}
          <label>Email<input aria-label="Email" type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} required /></label>
          <label>Password<input aria-label="Password" type="password" autoComplete={mode === 'sign-up' ? 'new-password' : 'current-password'} value={password} onChange={event => setPassword(event.target.value)} minLength={8} required /></label>
          {mode === 'sign-up' && <label>Confirm password<input aria-label="Confirm password" type="password" autoComplete="new-password" value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} minLength={8} required /></label>}
          {error && <div className="auth-form-error" role="alert">{error}</div>}
          <button className="primary auth-submit" type="submit" disabled={busy || !email.trim() || password.length < 8 || (mode === 'sign-up' && (!name.trim() || confirmPassword.length < 8))}>{busy ? 'Working…' : mode === 'sign-up' ? 'Create account' : 'Sign in'}</button>
        </form>
        <div className="auth-security-note"><strong>Authenticated application access</strong><span>Your private workflow state is tied to your account. TowerSignal’s underlying public-source datasets remain public-source evidence.</span></div>
      </section>
    </div>}
  </main>
}
