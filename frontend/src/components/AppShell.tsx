import { Activity, ArrowRight, Bell, CalendarDays, CircleDot, LayoutDashboard, LogOut, RadioTower, Waves } from 'lucide-react'
import { createContext, useContext } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useCallback, useEffect, useRef, useState } from 'react'
import { API_BASE, websocketUrl } from '../lib/api'
import { useAuth } from '../auth/AuthProvider'
import type { Alert, TokenCursor } from '../lib/types'

export type StreamStatus = 'connecting' | 'live' | 'reconnecting' | 'offline'

interface AlertStreamValue {
  status: StreamStatus
  receivedCount: number
}

const AlertStreamContext = createContext<AlertStreamValue>({ status: 'offline', receivedCount: 0 })

export function useAlertStream() {
  return useContext(AlertStreamContext)
}

export function AppShell() {
  const { user, accessToken, logout, refreshSession } = useAuth()
  const [streamStatus, setStreamStatus] = useState<StreamStatus>('connecting')
  const [receivedCount, setReceivedCount] = useState(0)
  const [apiReady, setApiReady] = useState<boolean | null>(null)
  const [loggingOut, setLoggingOut] = useState(false)
  const cursor = useRef<TokenCursor | null>(null)
  const attempt = useRef(0)
  const location = useLocation()
  const navigate = useNavigate()

  useEffect(() => {
    let active = true
    const check = async () => {
      try {
        const response = await fetch(`${API_BASE}/health/ready`, { credentials: 'omit' })
        if (active) setApiReady(response.ok)
      } catch {
        if (active) setApiReady(false)
      }
    }
    void check()
    const timer = window.setInterval(() => void check(), 30_000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    if (!accessToken) {
      setStreamStatus('offline')
      return
    }
    let stopped = false
    let socket: WebSocket | null = null
    let reconnectTimer = 0
    setStreamStatus(attempt.current === 0 ? 'connecting' : 'reconnecting')

    const connect = () => {
      if (stopped) return
      try {
        socket = new WebSocket(websocketUrl('/api/v1/ws/alerts'))
      } catch {
        scheduleReconnect()
        return
      }
      socket.onopen = () => {
        attempt.current = 0
        const handshake: { access_token: string; after_created_at?: string; after_id?: string } = {
          access_token: accessToken,
        }
        if (cursor.current) Object.assign(handshake, cursor.current)
        socket?.send(JSON.stringify(handshake))
      }
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(String(event.data)) as { type?: string; data?: Alert }
          if (message.type === 'ready') {
            setStreamStatus('live')
            return
          }
          if (message.type === 'alert' && message.data) {
            cursor.current = { after_created_at: message.data.created_at, after_id: message.data.id }
            setReceivedCount((count) => count + 1)
          }
        } catch {
          // Ignore malformed frames; the REST list remains the history source.
        }
      }
      socket.onerror = () => socket?.close()
      socket.onclose = (event) => {
        if (stopped) return
        if (event.code === 4401) void refreshSession()
        scheduleReconnect()
      }
    }

    const scheduleReconnect = () => {
      if (stopped) return
      attempt.current += 1
      setStreamStatus('reconnecting')
      const delay = Math.min(30_000, 1_000 * 2 ** Math.min(attempt.current - 1, 5))
      reconnectTimer = window.setTimeout(connect, delay)
    }

    connect()
    return () => {
      stopped = true
      window.clearTimeout(reconnectTimer)
      socket?.close(1000, 'route session changed')
    }
  }, [accessToken, refreshSession])

  const handleLogout = useCallback(async () => {
    setLoggingOut(true)
    await logout()
    setLoggingOut(false)
    navigate('/login', { replace: true, state: { from: location.pathname } })
  }, [location.pathname, logout, navigate])

  const streamLabel = streamStatus === 'live'
    ? 'Alert stream live'
    : streamStatus === 'connecting'
      ? 'Connecting to alert stream'
      : streamStatus === 'reconnecting'
        ? 'Reconnecting alert stream'
        : 'Alert stream offline'
  const pageTitle = location.pathname.startsWith('/history')
    ? 'Capture history'
    : location.pathname.startsWith('/alerts')
      ? 'Alerts'
      : location.pathname.startsWith('/flows')
        ? 'Flows'
        : 'Overview'

  return (
    <AlertStreamContext.Provider value={{ status: streamStatus, receivedCount }}>
      <div className="app-shell">
        <aside className="side-rail" aria-label="Main navigation">
          <NavLink className="brand-lockup" to="/overview" aria-label="Network observatory home">
            <span className="brand-mark" aria-hidden="true"><RadioTower size={19} strokeWidth={1.7} /></span>
            <span className="brand-copy"><strong>Network</strong><span>observatory</span></span>
          </NavLink>

          <div className="rail-caption">Observe</div>
          <nav className="primary-nav">
            <NavLink to="/overview" className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}>
              <LayoutDashboard size={17} strokeWidth={1.8} /><span>Overview</span><ArrowRight className="nav-arrow" size={14} />
            </NavLink>
            <NavLink to="/history" className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}>
              <CalendarDays size={17} strokeWidth={1.8} /><span>Capture history</span><ArrowRight className="nav-arrow" size={14} />
            </NavLink>
            <NavLink to="/alerts" className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}>
              <Bell size={17} strokeWidth={1.8} /><span>Alerts</span><ArrowRight className="nav-arrow" size={14} />
            </NavLink>
            <NavLink to="/flows" className={({ isActive }) => `nav-link${isActive ? ' is-active' : ''}`}>
              <Waves size={17} strokeWidth={1.8} /><span>Flows</span><ArrowRight className="nav-arrow" size={14} />
            </NavLink>
          </nav>

          <div className="rail-spacer" />
          <div className="rail-status" aria-label="Service status">
            <div className="rail-status-heading"><Activity size={15} /><span>Service</span></div>
            <div className="service-row"><CircleDot size={12} className={apiReady ? 'is-good' : 'is-muted'} /><span>API</span><strong>{apiReady === null ? 'Checking' : apiReady ? 'Ready' : 'Unavailable'}</strong></div>
            <div className="service-row"><CircleDot size={12} className={streamStatus === 'live' ? 'is-good' : 'is-muted'} /><span>Alerts</span><strong>{streamStatus === 'live' ? 'Live' : streamStatus === 'reconnecting' ? 'Retrying' : streamStatus === 'connecting' ? 'Joining' : 'Offline'}</strong></div>
          </div>

          <div className="account-card">
            <span className="avatar" aria-hidden="true">{user?.username.slice(0, 1).toUpperCase()}</span>
            <div className="account-copy"><strong>{user?.username}</strong><span>{user?.role}</span></div>
            <button className="icon-button logout-button" type="button" aria-label="Sign out" title="Sign out" disabled={loggingOut} onClick={() => void handleLogout()}>
              <LogOut size={16} />
            </button>
          </div>
        </aside>

        <div className="mobile-bar">
          <NavLink className="brand-lockup" to="/overview" aria-label="Network observatory home">
            <span className="brand-mark" aria-hidden="true"><RadioTower size={18} /></span>
            <span className="brand-copy"><strong>Network</strong><span>observatory</span></span>
          </NavLink>
          <button className="text-button mobile-signout" type="button" onClick={() => void handleLogout()} disabled={loggingOut}>Sign out</button>
          <nav className="mobile-nav" aria-label="Main navigation">
            <NavLink to="/overview" className={({ isActive }) => `mobile-nav-link${isActive ? ' is-active' : ''}`}><LayoutDashboard size={15} />Overview</NavLink>
            <NavLink to="/history" className={({ isActive }) => `mobile-nav-link${isActive ? ' is-active' : ''}`}><CalendarDays size={15} />History</NavLink>
            <NavLink to="/alerts" className={({ isActive }) => `mobile-nav-link${isActive ? ' is-active' : ''}`}><Bell size={16} />Alerts</NavLink>
            <NavLink to="/flows" className={({ isActive }) => `mobile-nav-link${isActive ? ' is-active' : ''}`}><Waves size={16} />Flows</NavLink>
          </nav>
        </div>

        <main className="main-column">
          <div className="topline">
            <div className="breadcrumbs"><span>Workspace</span><span aria-hidden="true">/</span><strong>{pageTitle}</strong></div>
            <div className={`stream-indicator stream-${streamStatus}`} role="status" aria-live="polite">
              <span className="status-pip" aria-hidden="true" />{streamLabel}
            </div>
          </div>
          <Outlet />
        </main>
      </div>
    </AlertStreamContext.Provider>
  )
}
