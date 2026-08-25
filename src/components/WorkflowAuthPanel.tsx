import { useState, type FormEvent } from 'react'
import type { WorkflowUser } from '../types/workflow'

export function WorkflowAuthPanel({
  user,
  loading,
  busy,
  error,
  onSignIn,
  onSignUp,
  onSignOut,
}: {
  user: WorkflowUser | null
  loading: boolean
  busy: boolean
  error: string | null
  onSignIn: (email: string, password: string) => Promise<void>
  onSignUp: (email: string, password: string) => Promise<void>
  onSignOut: () => Promise<void>
}) {
  const [open, setOpen] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [createAccount, setCreateAccount] = useState(false)

  if (loading) return <span className="workflow-sync-chip">Checking workflow sync…</span>
  if (user) return <div className="workflow-auth signed-in"><span><strong>Workflow synced</strong><small>{user.email}</small></span>{error && <div className="workflow-error workflow-auth-error" role="alert" title={error}>{error}</div>}<button onClick={() => void onSignOut()} disabled={busy}>Sign out</button></div>

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    try {
      if (createAccount) await onSignUp(email.trim(), password)
      else await onSignIn(email.trim(), password)
      setOpen(false)
      setPassword('')
    } catch {
      // Error text is surfaced by the workflow state owner.
    }
  }

  return <div className="workflow-auth">
    <button className="workflow-sync-button" onClick={() => setOpen(value => !value)}>Sync workflow</button>
    {open && <div className="workflow-auth-popover">
      <div><span className="eyebrow">Private workflow state</span><strong>{createAccount ? 'Create TowerSignal login' : 'Sign in to sync'}</strong><p>Saved accounts, notes and next actions are private workflow data, separate from public-source evidence.</p></div>
      <form onSubmit={event => void submit(event)}>
        <label>Email<input type="email" value={email} onChange={event => setEmail(event.target.value)} autoComplete="email" required /></label>
        <label>Password<input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete={createAccount ? 'new-password' : 'current-password'} minLength={8} required /></label>
        {error && <div className="workflow-error" role="alert">{error}</div>}
        <button className="primary" type="submit" disabled={busy || !email.trim() || password.length < 8}>{busy ? 'Working…' : createAccount ? 'Create account' : 'Sign in'}</button>
      </form>
      <button className="link-button" onClick={() => setCreateAccount(value => !value)}>{createAccount ? 'Already have an account? Sign in' : 'Need an account? Create one'}</button>
    </div>}
  </div>
}
