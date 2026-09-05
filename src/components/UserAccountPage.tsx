import { useMemo, useState } from 'react'
import type { WorkflowUser } from '../types/workflow'
import { PortalNavigation } from './PortalNavigation'

function initials(user: WorkflowUser): string {
  const source = user.name?.trim() || user.email.split('@')[0] || 'TS'
  const parts = source.split(/[\s._-]+/).filter(Boolean)
  return (parts.length > 1 ? `${parts[0][0]}${parts[1][0]}` : source.slice(0, 2)).toUpperCase()
}

export function UserAccountPage({ user, onSignOut }: { user: WorkflowUser; onSignOut: () => Promise<void> }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const avatar = useMemo(() => initials(user), [user])
  const name = user.name?.trim() || user.email.split('@')[0] || 'TowerSignal user'

  const signOut = async () => {
    setBusy(true)
    setError(null)
    try { await onSignOut() }
    catch (err) { setError(err instanceof Error ? err.message : 'Unable to sign out.') }
    finally { setBusy(false) }
  }

  return <main className="portal-page account-portal-page">
    <PortalNavigation current="my-account" user={user} />

    <section className="portal-content account-content">
      <div className="account-heading">
        <div className="account-avatar" aria-hidden="true">{avatar}</div>
        <div><span className="page-kicker">TowerSignal account</span><h1>{name}</h1><p>{user.email}</p></div>
      </div>

      <div className="account-grid">
        <section className="account-card">
          <span className="eyebrow">Account identity</span>
          <dl>
            <div><dt>Name</dt><dd>{name}</dd></div>
            <div><dt>Email</dt><dd>{user.email}</dd></div>
            <div><dt>Account ID</dt><dd className="account-id">{user.id}</dd></div>
          </dl>
        </section>
        <section className="account-card">
          <span className="eyebrow">Access</span>
          <dl>
            <div><dt>Session</dt><dd><span className="account-status active">Authenticated</span></dd></div>
            <div><dt>Application pages</dt><dd>Login required</dd></div>
            <div><dt>Private workflow</dt><dd>Synced to this account</dd></div>
          </dl>
        </section>
      </div>

      <section className="account-card account-security-card">
        <div><span className="eyebrow">Security boundary</span><h2>Authenticated application, public-source evidence</h2><p>The TowerSignal interface and workspace routes require a valid login. Because the current deployment is static GitHub Pages, published public-source JSON assets are not made private by the client-side route gate.</p></div>
      </section>

      <section className="account-actions-card">
        <div><span className="eyebrow">Session controls</span><h2>Sign out of TowerSignal</h2><p>Signing out closes access to Home and every application workspace until you authenticate again.</p></div>
        <button className="danger-button" onClick={() => void signOut()} disabled={busy}>{busy ? 'Signing out…' : 'Sign out'}</button>
      </section>
      {error && <div className="auth-form-error" role="alert">{error}</div>}
    </section>
  </main>
}
