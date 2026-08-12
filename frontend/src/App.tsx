import { type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AdminIntegrations from './pages/AdminIntegrations'
import Login from './pages/Login'
import Reconciliation from './pages/Reconciliation'
import { getToken } from './lib/auth'

function RequireAuth({ children }: { children: ReactNode }) {
  if (!getToken()) return <Navigate to="/login" replace />
  return <>{children}</>
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/reconciliation"
          element={
            <RequireAuth>
              <Reconciliation />
            </RequireAuth>
          }
        />
        <Route
          path="/admin/integrations"
          element={
            <RequireAuth>
              <AdminIntegrations />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/reconciliation" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
