import { type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { getToken } from './lib/auth'
import { TenantProvider } from './lib/TenantContext'
import Shell from './components/Shell'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Reconciliation from './pages/Reconciliation'
import Ecritures from './pages/Ecritures'
import PlanComptable from './pages/PlanComptable'
import Categorisation from './pages/Categorisation'
import Integrations from './pages/Integrations'
import AdminIntegrations from './pages/AdminIntegrations'

function RequireAuth({ children }: { children: ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AppShell({ children }: { children: ReactNode }) {
  return (
    <RequireAuth>
      <TenantProvider>
        <Shell>{children}</Shell>
      </TenantProvider>
    </RequireAuth>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<AppShell><Dashboard /></AppShell>} />
        <Route path="/rapprochement" element={<AppShell><Reconciliation /></AppShell>} />
        <Route path="/ecritures" element={<AppShell><Ecritures /></AppShell>} />
        <Route path="/plan-comptable" element={<AppShell><PlanComptable /></AppShell>} />
        <Route path="/categorisation" element={<AppShell><Categorisation /></AppShell>} />
        <Route path="/integrations" element={<AppShell><Integrations /></AppShell>} />
        <Route
          path="/admin/integrations"
          element={
            <RequireAuth>
              <AdminIntegrations />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
