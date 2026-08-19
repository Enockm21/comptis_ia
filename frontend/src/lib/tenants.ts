import { json, fetchWithAuth } from './http'

export interface Tenant {
  id: string
  name: string
  siret?: string | null
  numero_tva?: string | null
  adresse?: string | null
  code_postal_ville?: string | null
}

export async function listTenants(): Promise<Tenant[]> {
  const res = await fetchWithAuth('/tenants')
  return json<Tenant[]>(res)
}

export async function updateTenantInfo(tenantId: string, info: {
  siret?: string | null
  numero_tva?: string | null
  adresse?: string | null
  code_postal_ville?: string | null
}): Promise<Tenant> {
  const res = await fetchWithAuth(`/tenants/${tenantId}/info`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(info),
  })
  return json<Tenant>(res)
}
