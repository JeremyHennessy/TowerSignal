import { useState, type FormEvent } from 'react'
import type { WorkflowUser } from '../types/workflow'

type AuthMode = 'sign-in' | 'sign-up'

const logoAsset = `${import.meta.env.BASE_URL}marketing/towersignal-logo.webp`

export function AuthLandingPage({
  initialError,
  onSignIn,
  onSignUp,
}: {
  initialError?: string | null
  onSignIn: (email: string, password: string) => Promise<WorkflowUser>
  onSignUp: (name: string, email: string, password: string) => Promise<WorkflowUser>
}) {
  const [mode, setMode] = useState<AuthMode>('sign-in')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(initialError ?? null)

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

  return <main className="auth-gate-page auth-themed-page">
    <section className="auth-brand-panel" aria-label="TowerSignal product introduction">
      <div className="auth-brand-topline">
        <a className="auth-brand-logo" href={import.meta.env.BASE_URL} aria-label="TowerSignal marketing home">
          <img src={logoAsset} alt="TowerSignal" />
        </a>
        <a className="auth-back-link" href={import.meta.env.BASE_URL}>Back to website <span aria-hidden="true">→</span></a>
      </div>

      <div className="auth-brand-copy">
        <span className="auth-theme-kicker"><i /> Property, compliance &amp; service intelligence</span>
        <h1>Turn public signals into the <em>next action.</em></h1>
        <p>Access TowerSignal's authenticated workspace for account prioritization, property intelligence, compliance activity, procurement, relationships and private workflow.</p>
      </div>

      <div className="auth-value-grid">
        <article><small>01</small><strong>Account timing</strong><span>Source-backed operational and regulatory changes.</span></article>
        <article><small>02</small><strong>Procurement intelligence</strong><span>Observed solicitations, awards, contracts and vendors.</span></article>
        <article><small>03</small><strong>Company intelligence</strong><span>Conservative vendor identity and public customer relationships.</span></article>
        <article><small>04</small><strong>Private workflow</strong><span>Watchlists, notes, next actions and saved views tied to your login.</span></article>
      </div>
    </section>

    <section className="auth-form-panel" aria-label="TowerSignal authentication">
      <div className="auth-form-card">
        <div className="auth-form-heading">
          <span className="eyebrow">TowerSignal workspace</span>
          <h2>{mode === 'sign-up' ? 'Create your TowerSignal account' : 'Sign in to TowerSignal'}</h2>
          <p>{mode === 'sign-up' ? 'Create a private workspace login to access the application.' : 'Welcome back. Sign in to continue to your TowerSignal workspace.'}</p>
        </div>
        <div className="auth-mode-tabs" role="tablist" aria-label="Authentication mode">
          <button type="button" role="tab" aria-selected={mode === 'sign-in'} className={mode === 'sign-in' ? 'active' : ''} onClick={() => switchMode('sign-in')}>Sign in</button>
          <button type="button" role="tab" aria-selected={mode === 'sign-up'} className={mode === 'sign-up' ? 'active' : ''} onClick={() => switchMode('sign-up')}>Create account</button>
        </div>
        <form className="auth-form" onSubmit={event => void submit(event)}>
          {mode === 'sign-up' && <label>Full name<input aria-label="Full name" type="text" autoComplete="name" value={name} onChange={event => setName(event.target.value)} minLength={2} required /></label>}
          <label>Email<input aria-label="Email" type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} required /></label>
          <label>Password<input aria-label="Password" type="password" autoComplete={mode === 'sign-up' ? 'new-password' : 'current-password'} value={password} onChange={event => setPassword(event.target.value)} minLength={8} required /></label>
          {mode === 'sign-up' && <label>Confirm password<input aria-label="Confirm password" type="password" autoComplete="new-password" value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} minLength={8} required /></label>}
          {error && <div className="auth-form-error" role="alert">{error}</div>}
          <button className="auth-submit" type="submit" disabled={busy || !email.trim() || password.length < 8 || (mode === 'sign-up' && (!name.trim() || confirmPassword.length < 8))}>{busy ? 'Working…' : mode === 'sign-up' ? 'Create account' : 'Sign in'} <span aria-hidden="true">→</span></button>
        </form>
        <div className="auth-security-note"><strong>Authenticated application access</strong><span>Your private workflow state is tied to your account. TowerSignal's underlying public-source datasets remain public-source evidence.</span></div>
      </div>
    </section>
  </main>
}