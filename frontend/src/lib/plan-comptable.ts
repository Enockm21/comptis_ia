import { fetchWithAuth } from './http'

export interface Compte {
  id: string
  numero: string
  libelle: string
  classe: number
}

export async function listPlanComptable(tenantId: string): Promise<Compte[]> {
  const res = await fetchWithAuth(`/plan-comptable?tenant_id=${tenantId}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<Compte[]>
}
