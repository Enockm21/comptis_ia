import { authHeaders } from './auth'

export interface Compte {
  id: string
  numero: string
  libelle: string
  classe: number
}

export async function listPlanComptable(tenantId: string): Promise<Compte[]> {
  const res = await fetch(`/plan-comptable?tenant_id=${tenantId}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<Compte[]>
}
