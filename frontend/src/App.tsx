import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AdminIntegrations from './pages/AdminIntegrations'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/admin/integrations" element={<AdminIntegrations />} />
        <Route path="*" element={<Navigate to="/admin/integrations" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
