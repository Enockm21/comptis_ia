import { authHeaders } from './auth'

export interface Tenant {
  id: string
  name: string
}

export async function listTenants(): Promise<Tenant[]> {
  const res = await fetch('/tenants', { headers: authHeaders() })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<Tenant[]>
}
