import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { listTenants, type Tenant } from './tenants'

interface TenantContextValue {
  tenants: Tenant[]
  selected: Tenant | null
  setSelected: (t: Tenant) => void
  loading: boolean
}

const TenantContext = createContext<TenantContextValue>({
  tenants: [], selected: null, setSelected: () => {}, loading: true,
})

export function TenantProvider({ children }: { children: ReactNode }) {
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [selected, setSelectedState] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listTenants().then(list => {
      setTenants(list)
      const savedId = localStorage.getItem('comptis_tenant_id')
      const saved = list.find(t => t.id === savedId) ?? list[0] ?? null
      setSelectedState(saved)
    }).finally(() => setLoading(false))
  }, [])

  const setSelected = (t: Tenant) => {
    setSelectedState(t)
    localStorage.setItem('comptis_tenant_id', t.id)
  }

  return (
    <TenantContext.Provider value={{ tenants, selected, setSelected, loading }}>
      {children}
    </TenantContext.Provider>
  )
}

export function useTenant() {
  return useContext(TenantContext)
}
