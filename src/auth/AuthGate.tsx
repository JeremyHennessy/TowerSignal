import { useCallback, useEffect, useRef, useState } from 'react'
import App from '../App'
import { AuthLandingPage } from '../components/AuthLandingPage'
import { HomePage } from '../components/HomePage'
import { MarketingLandingPage } from '../components/MarketingLandingPage'
import { UserAccountPage } from '../components/UserAccountPage'
import type { WorkflowUser } from '../types/workflow'
import { getWorkflowSession, signInWorkflow, signOutWorkflow, signUpWorkflow } from '../workflow/client'

type GateRoute = 'marketing' | 'login' | 'home' | 'account' | 'app'

function currentRoute(): GateRoute {
  const raw = window.location.hash.replace(/^#\/?/, '').split('?')[0]
  if (!raw || raw === 'marketing') return 'marketing'
  if (raw === 'login') return 'login'
  if (raw === 'home') return 'home'
  if (raw === 'my-account') return 'account'
  return 'app'
}

function currentHashOrHome(): string {
  return window.location.hash || '#/home'
}

function isPublicRoute(route: GateRoute) {
  return route === 'marketing' || route === 'login'
}

export function AuthGate() {
  const [user, setUser] = useState<WorkflowUser | null>(null)
  const [checking, setChecking] = useState(true)
  const [sessionError, setSessionError] = useState<string | null>(null)
  const [route, setRoute] = useState<GateRoute>(currentRoute)
  const intendedHash = useRef(isPublicRoute(route) ? '#/home' : currentHashOrHome())

  const refreshSession = useCallback(async () => {
    try {
      const sessionUser = await getWorkflowSession()
      setUser(sessionUser)
      setSessionError(null)
    } catch (err) {
      setSessionError(err instanceof Error ? err.message : 'Unable to verify TowerSignal session.')
    } finally {
      setChecking(false)
    }
  }, [])

  useEffect(() => {
    void refreshSession()
    const onFocus = () => { void refreshSession() }
    window.addEventListener('focus', onFocus)
    return () => window.removeEventListener('focus', onFocus)
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
    setUser(sessionUser)
    setSessionError(null)
    const target = intendedHash.current || '#/home'
    if (window.location.hash !== target) window.location.hash = target
    setRoute(currentRoute())
  }

  const signIn = async (email: string, password: string) => {
    const sessionUser = await signInWorkflow(email, password)
    completeAuthentication(sessionUser)
    return sessionUser
  }

  const signUp = async (name: string, email: string, password: string) => {
    const sessionUser = await signUpWorkflow(email, password, name)
    completeAuthentication(sessionUser)
    return sessionUser
  }

  const signOut = async () => {
    await signOutWorkflow()
    intendedHash.current = '#/home'
    setUser(null)
    setRoute('marketing')
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`)
  }

  if (route === 'marketing') return <MarketingLandingPage />
  if (checking) return <main className="auth-check-page"><div className="auth-check-card"><span className="auth-brand-mark">TS</span><h1>TowerSignal</h1><p>Verifying authenticated workspace…</p></div></main>
  if (!user) return <AuthLandingPage initialError={sessionError} onSignIn={signIn} onSignUp={signUp} />
  if (route === 'login' || route === 'home') return <HomePage user={user} />
  if (route === 'account') return <UserAccountPage user={user} onSignOut={signOut} />
  return <App />
}
