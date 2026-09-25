import { useEffect, useState, type FormEvent } from 'react'
import { completeWorkflowPasswordSetup, requestWorkflowPasswordSetup } from '../workflow/remoteClient'

function readSetupLink() {
  const url = new URL(window.location.href)
  const hashQuery = new URLSearchParams(url.hash.split('?')[1] || '')
  const tokens = [...url.searchParams.getAll('token'), ...hashQuery.getAll('token')]
  const invalid = url.searchParams.has('error') || hashQuery.has('error') || tokens.length > 1
  return { token: invalid ? '' : tokens[0] || '', invalid }
}

export function PasswordSetupPage() {
  const [link, setLink] = useState(readSetupLink)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(link.invalid ? 'This setup link is invalid or expired. Request a new email below.' : null)
  const [status, setStatus] = useState('')
  const [complete, setComplete] = useState(false)

  useEffect(() => {
    // Keep the bearer token in this component only, never in storage or copied page links.
    const url = new URL(window.location.href)
    url.searchParams.delete('token')
    url.searchParams.delete('error')
    url.hash = '/password-setup'
    window.history.replaceState(null, '', url.pathname + url.search + url.hash)
  }, [])

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setStatus('')
    if (link.token && password !== confirmation) {
      setError('The passwords do not match.')
      return
    }
    setBusy(true)
    try {
      if (link.token) {
        await completeWorkflowPasswordSetup(link.token, password)
        setPassword('')
        setConfirmation('')
        setLink({ token: '', invalid: false })
        setComplete(true)
        setStatus('Your password is ready. Sign in to TowerSignal with your email and new password.')
      } else {
        await requestWorkflowPasswordSetup(email.trim())
        setStatus('If this email belongs to a TowerSignal account, a password-setup email has been requested. Check your inbox and spam folder.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to complete password setup. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return <main className="auth-check-page">
    <section className="auth-form-card" aria-label="TowerSignal password setup">
      <span className="eyebrow">TowerSignal workspace</span>
      <h1>{complete ? 'Password saved' : link.token ? 'Choose your password' : 'Set up or reset your password'}</h1>
      {!complete && <p>{link.token ? 'Enter a password of 8 to 128 characters.' : 'Enter the email your administrator used to create your account.'}</p>}
      {!complete && <form className="auth-form" onSubmit={event => void submit(event)}>
        {link.token ? <>
          <label>New password<input type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={password} onChange={event => setPassword(event.target.value)} /></label>
          <label>Confirm password<input type="password" autoComplete="new-password" minLength={8} maxLength={128} required value={confirmation} onChange={event => setConfirmation(event.target.value)} /></label>
        </> : <label>Email<input type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} /></label>}
        {error && <div className="auth-form-error" role="alert">{error}</div>}
        <button className="auth-submit" disabled={busy} type="submit">{busy ? 'Working…' : link.token ? 'Save password' : 'Send setup email'}</button>
      </form>}
      {status && <p role="status">{status}</p>}
      {!complete && link.token && <button type="button" disabled={busy} onClick={() => { setLink({ token: '', invalid: false }); setPassword(''); setConfirmation(''); setError(null) }}>Request a new setup email</button>}
      <p><a href={`${import.meta.env.BASE_URL}#/login`}>Back to sign in</a></p>
    </section>
  </main>
}
