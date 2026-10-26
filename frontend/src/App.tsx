import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth/AuthProvider'
import { AppShell } from './components/AppShell'
import { LoadingState } from './components/ListStates'

const AlertsPage = lazy(() => import('./pages/AlertsPage').then(({ AlertsPage }) => ({ default: AlertsPage })))
const CaptureHistoryPage = lazy(() => import('./pages/CaptureHistoryPage').then(({ CaptureHistoryPage }) => ({ default: CaptureHistoryPage })))
const FlowsPage = lazy(() => import('./pages/FlowsPage').then(({ FlowsPage }) => ({ default: FlowsPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then(({ LoginPage }) => ({ default: LoginPage })))
const ModelPage = lazy(() => import('./pages/ModelPage').then(({ ModelPage }) => ({ default: ModelPage })))
const UserManagementPage = lazy(() => import('./pages/UserManagementPage').then(({ UserManagementPage }) => ({ default: UserManagementPage })))
const OverviewPage = lazy(() => import('./pages/OverviewPage').then(({ OverviewPage }) => ({ default: OverviewPage })))
const SimulationPage = lazy(() => import('./pages/SimulationPage').then(({ SimulationPage }) => ({ default: SimulationPage })))

function ProtectedShell() {
  const { user } = useAuth()
  const location = useLocation()
  if (!user) return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />
  return <AppShell />
}

function AdminOnlyUserManagement() {
  const { user } = useAuth()
  if (user?.role !== 'admin') return <div className="page-content"><section className="inline-error" role="alert"><div><strong>Administrator access required</strong><p>This area is available only to active administrators.</p></div></section></div>
  return <UserManagementPage />
}

export function App() {
  return <Suspense fallback={<main className="main-column lazy-route-loading"><LoadingState label="Loading view…" /></main>}>
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedShell />}>
        <Route path="/" element={<Navigate to="/overview" replace />} />
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/simulation" element={<SimulationPage />} />
        <Route path="/history" element={<CaptureHistoryPage />} />
        <Route path="/model" element={<ModelPage />} />
        <Route path="/users" element={<AdminOnlyUserManagement />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/flows" element={<FlowsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/overview" replace />} />
    </Routes>
  </Suspense>
}
