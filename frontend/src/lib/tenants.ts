import { authHeaders } from './auth'
import { json } from './http'

export interface Tenant {
  id: string
  name: string
}

export async function listTenants(): Promise<Tenant[]> {
  const res = await fetch('/tenants', { headers: authHeaders() })
  return json<Tenant[]>(res)
}
