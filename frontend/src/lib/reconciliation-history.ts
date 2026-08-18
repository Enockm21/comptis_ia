import { fetchWithAuth } from './http'

export interface RunHistoryItem {
  id: string
  tenant_id: string
  date_debut: string
  date_fin: string
  total_transactions: number
  total_rapprochees: number
  total_ecarts: number
  total_non_rapprochees: number
  statut: 'termine' | 'en_cours'
  ran_at: string
}

export async function listRunHistory(tenantId: string): Promise<RunHistoryItem[]> {
  const res = await fetchWithAuth(`/reconciliation/history?tenant_id=${tenantId}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<RunHistoryItem[]>
}
