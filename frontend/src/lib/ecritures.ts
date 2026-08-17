import { authHeaders } from './auth'

export interface Ecriture {
  id: string
  transaction_id: string
  facture_id: string
  montant: string
  date: string
  compte_id: string | null
  statut: 'a_categoriser' | 'categorisee' | 'validee'
  created_at: string
}

export async function listEcritures(tenantId: string, statut?: string): Promise<Ecriture[]> {
  const params = new URLSearchParams({ tenant_id: tenantId })
  if (statut) params.set('statut', statut)
  const res = await fetch(`/ecritures?${params}`, { headers: authHeaders() })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<Ecriture[]>
}
