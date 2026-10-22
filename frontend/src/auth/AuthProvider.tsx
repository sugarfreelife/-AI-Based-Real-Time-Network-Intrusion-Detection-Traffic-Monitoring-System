import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from 'react'
import { API_BASE, ApiError, readJson, requestRefresh, requestTokenPair } from '../lib/api'
import type { TokenPair, User } from '../lib/types'

interface Session extends TokenPair {
  expiresAt: number
}

interface AuthContextValue {
  user: User | null
  accessToken: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshSession: () => Promise<boolean>
  request: <T>(path: string, init?: RequestInit) => Promise<T>
}

const AuthContext = createContext<AuthContextValue | null>(null)

function toSession(pair: TokenPair): Session {
  return { ...pair, expiresAt: Date.now() + pair.expires_in * 1000 }
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [session, setSession] = useState<Session | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const sessionRef = useRef<Session | null>(null)
  const refreshFlight = useRef<Promise<boolean> | null>(null)

  const replaceSession = useCallback((next: Session | null) => {
    sessionRef.current = next
    setSession(next)
    if (!next) setUser(null)
  }, [])

  const refreshSession = useCallback(async (): Promise<boolean> => {
    if (refreshFlight.current) return refreshFlight.current
    const active = sessionRef.current
    if (!active) return false
    const pending = requestRefresh(active.refresh_token)
      .then((pair) => {
        replaceSession(toSession(pair))
        return true
      })
      .catch(() => {
        replaceSession(null)
        return false
      })
      .finally(() => {
        refreshFlight.current = null
      })
    refreshFlight.current = pending
    return pending
  }, [replaceSession])

  const request = useCallback(async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
    const current = sessionRef.current
    if (!current) throw new ApiError('Sign in to continue.', 401)
    const send = (token: string) => fetch(path.startsWith('http') ? path : `${API_BASE}${path}`, {
      ...init,
      credentials: 'omit',
      headers: {
        Accept: 'application/json',
        ...((init.headers as Record<string, string> | undefined) ?? {}),
        Authorization: `Bearer ${token}`,
      },
    })
    let response = await send(current.access_token)
    if (response.status === 401) {
      const renewed = await refreshSession()
      const latest = sessionRef.current
      if (!renewed || !latest) throw new ApiError('Your session has ended. Sign in again to continue.', 401)
      response = await send(latest.access_token)
      if (response.status === 401) {
        replaceSession(null)
        throw new ApiError('Your session has ended. Sign in again to continue.', 401)
      }
    }
    return readJson<T>(response)
  }, [refreshSession, replaceSession])

  const login = useCallback(async (username: string, password: string) => {
    const pair = await requestTokenPair('/api/v1/auth/token', { username, password })
    const response = await fetch(`${API_BASE}/api/v1/auth/me`, {
      credentials: 'omit',
      headers: { Authorization: `Bearer ${pair.access_token}`, Accept: 'application/json' },
    })
    const currentUser = await readJson<User>(response)
    replaceSession(toSession(pair))
    setUser(currentUser)
  }, [replaceSession])

  const logout = useCallback(async () => {
    const current = sessionRef.current
    replaceSession(null)
    if (!current) return
    try {
      await fetch(`${API_BASE}/api/v1/auth/logout`, {
        method: 'POST',
        credentials: 'omit',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: current.refresh_token }),
      })
    } catch {
      // Local credentials are cleared even when the API is unreachable.
    }
  }, [replaceSession])

  useEffect(() => {
    if (!session) return
    const delay = Math.max(1000, session.expiresAt - Date.now() - 45_000)
    const timer = window.setTimeout(() => void refreshSession(), delay)
    return () => window.clearTimeout(timer)
  }, [session, refreshSession])

  const value = useMemo<AuthContextValue>(() => ({
    user,
    accessToken: session?.access_token ?? null,
    login,
    logout,
    refreshSession,
    request,
  }), [user, session?.access_token, login, logout, refreshSession, request])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
