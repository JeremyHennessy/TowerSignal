import { useCallback, useEffect, useRef, useState } from 'react'
import App from '../App'
import { AuthLandingPage } from '../components/AuthLandingPage'
import { HomePage } from '../components/HomePage'
import { MarketingLandingPage } from '../components/MarketingLandingPage'
import { PasswordSetupPage } from '../components/PasswordSetupPage'
import { UserAccountPage } from '../components/UserAccountPage'
import type { WorkflowUser } from '../types/workflow'
import { getWorkflowSession, signInWorkflow, signOutWorkflow } from '../workflow/client'

type GateRoute = 'marketing' | 'login' | 'password-setup' | 'home' | 'account' | 'app'

function currentRoute(): GateRoute {
  const raw = window.location.hash.replace(/^#\/?/, '').split('?')[0]
  if (!raw || raw === 'marketing') return 'marketing'
  if (raw === 'login') return 'login'
  if (raw === 'password-setup') return 'password-setup'
  if (raw === 'home') return 'home'
  if (raw === 'my-account') return 'account'
  return 'app'
}

function currentHashOrHome(): string {
  return window.location.hash || '#/home'
}

function isPublicRoute(route: GateRoute) {
  return route === 'marketing' || route === 'login' || route === 'password-setup'
}

export function AuthGate() {
  const [user, setUser] = useState<WorkflowUser | null>(null)
  const [checking, setChecking] = useState(true)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [route, setRoute] = useState<GateRoute>(currentRoute)
  const intendedHash = useRef(isPublicRoute(route) ? '#/home' : currentHashOrHome())
  const sessionRequest = useRef(0)

  const refreshSession = useCallback(async (preserveExisting = false) => {
    const request = ++sessionRequest.current
    try {
      const sessionUser = await getWorkflowSession()
      if (request !== sessionRequest.current) return
      setUser(current => sessionUser ?? (preserveExisting ? current : null))
      setSessionError(null)
    } catch (err) {
      if (request !== sessionRequest.current) return
      setSessionError(err instanceof Error ? err.message : 'Unable to verify TowerSignal session.')
    } finally {
      if (request === sessionRequest.current) setChecking(false)
    }
  }, [])

  useEffect(() => {
    void refreshSession(false)
    // Safari/WebKit can block the cross-site Neon Auth cookie after a successful
    // sign-in while this GitHub Pages SPA is still open. A focus check may then
    // return no cookie-backed session even though this tab has just authenticated.
    // Keep the tab's in-memory authenticated state in that case. Initial page
    // loads still fail closed, and explicit sign-out still clears the user.
    const onFocus = () => { void refreshSession(true) }
    window.addEventListener('focus', onFocus)
    return () => { sessionRequest.current += 1; window.removeEventListener('focus', onFocus) }
  }, [refreshSession])

  useEffect(() => {
    const applyRoute = () => {
      const nextRoute = currentRoute()
      if (!user && !isPublicRoute(nextRoute)) intendedHash.current = currentHashOrHome()
      setRoute(nextRoute)
    }
    applyRoute()
    window.addEventListener('hashchange', applyRoute)
    return () => window.removeEventListener('hashchange', applyRoute)
  }, [user])

  useEffect(() => {
    if (user && route === 'login') window.location.hash = '#/home'
  }, [route, user])

  const completeAuthentication = (sessionUser: WorkflowUser) => {
    sessionRequest.current += 1
    setUser(sessionUser)
    setSessionError(null)
    const target = intendedHash.current || '#/home'
    if (window.location.hash !== target) window.location.hash = target
    setRoute(currentRoute())
  }

  const signIn = async (email: string, password: string) => {
    sessionRequest.current += 1
    const sessionUser = await signInWorkflow(email, password)
    completeAuthentication(sessionUser)
    return sessionUser
  }

  const signOut = async () => {
    sessionRequest.current += 1
    await signOutWorkflow()
    sessionRequest.current += 1
    intendedHash.current = '#/home'
    setUser(null)
    setRoute('marketing')
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`)
  }

  if (route === 'password-setup') return <PasswordSetupPage />
  if (route === 'marketing') return <MarketingLandingPage />
  if (checking) return <main className="auth-check-page"><div className="auth-check-card"><span className="auth-brand-mark">TS</span><h1>TowerSignal</h1><p>Verifying authenticated workspace…</p></div></main>
  if (!user) return <AuthLandingPage initialError={sessionError} onSignIn={signIn} />
  if (route === 'login' || route === 'home') return <HomePage user={user} />
  if (route === 'account') return <UserAccountPage key={user.id} user={user} onSignOut={signOut} />
  return <App />
}
