import { json, fetchWithAuth } from './http'

export interface Tenant {
  id: string
  name: string
}

export async function listTenants(): Promise<Tenant[]> {
  const res = await fetchWithAuth('/tenants')
  return json<Tenant[]>(res)
}
