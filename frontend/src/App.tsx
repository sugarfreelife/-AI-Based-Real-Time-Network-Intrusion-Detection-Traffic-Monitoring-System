import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth/AuthProvider'
import { AppShell } from './components/AppShell'
import { AlertsPage } from './pages/AlertsPage'
import { CaptureHistoryPage } from './pages/CaptureHistoryPage'
import { FlowsPage } from './pages/FlowsPage'
import { LoginPage } from './pages/LoginPage'
import { ModelPage } from './pages/ModelPage'
import { UserManagementPage } from './pages/UserManagementPage'
import { OverviewPage } from './pages/OverviewPage'

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
  return <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route element={<ProtectedShell />}>
      <Route path="/" element={<Navigate to="/overview" replace />} />
      <Route path="/overview" element={<OverviewPage />} />
      <Route path="/history" element={<CaptureHistoryPage />} />
      <Route path="/model" element={<ModelPage />} />
      <Route path="/users" element={<AdminOnlyUserManagement />} />
      <Route path="/alerts" element={<AlertsPage />} />
      <Route path="/flows" element={<FlowsPage />} />
    </Route>
    <Route path="*" element={<Navigate to="/overview" replace />} />
  </Routes>
}
