import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './auth/AuthProvider'
import { AppShell } from './components/AppShell'
import { AlertsPage } from './pages/AlertsPage'
import { FlowsPage } from './pages/FlowsPage'
import { LoginPage } from './pages/LoginPage'

function ProtectedShell() {
  const { user } = useAuth()
  const location = useLocation()
  if (!user) return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />
  return <AppShell />
}

export function App() {
  return <Routes>
    <Route path="/login" element={<LoginPage />} />
    <Route element={<ProtectedShell />}>
      <Route path="/" element={<Navigate to="/alerts" replace />} />
      <Route path="/alerts" element={<AlertsPage />} />
      <Route path="/flows" element={<FlowsPage />} />
    </Route>
    <Route path="*" element={<Navigate to="/alerts" replace />} />
  </Routes>
}
