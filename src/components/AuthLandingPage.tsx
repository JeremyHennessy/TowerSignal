import { useState, type FormEvent } from 'react'
import type { WorkflowUser } from '../types/workflow'

const logoAsset = `${import.meta.env.BASE_URL}marketing/towersignal-logo.webp`

export function AuthLandingPage({
  initialError,
  onSignIn,
}: {
  initialError?: string | null
  onSignIn: (email: string, password: string) => Promise<WorkflowUser>
}) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(initialError ?? null)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onSignIn(email.trim(), password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed.')
    } finally {
      setBusy(false)
    }
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
          <h2>Sign in to TowerSignal</h2>
          <p>Access is limited to administrator-provisioned accounts.</p>
        </div>
        <form className="auth-form" onSubmit={event => void submit(event)}>
          <label>Email<input aria-label="Email" type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} required /></label>
          <label>Password<input aria-label="Password" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} minLength={8} required /></label>
          {error && <div className="auth-form-error" role="alert">{error}</div>}
          <button className="auth-submit" type="submit" disabled={busy || !email.trim() || password.length < 8}>{busy ? 'Working…' : 'Sign in'} <span aria-hidden="true">→</span></button>
        </form>
        <div className="auth-security-note"><strong>Private access only</strong><span>New accounts cannot be created from TowerSignal. Access is provisioned by an administrator.</span></div>
      </div>
    </section>
  </main>
}
