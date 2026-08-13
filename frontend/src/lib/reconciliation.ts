import { authHeaders } from './auth'
import { checkOk, json } from './http'

export interface RunRequestBody {
  tenant_id: string
  date_debut?: string | null
  date_fin?: string | null
}

export interface RunResponse {
  run_id: string
  tenant_id: string
  date_debut: string
  date_fin: string
}

export interface TransactionData {
  id: string
  montant: string
  date: string
  libelle: string
}

export interface FactureData {
  id: string
  montant: string
  date: string
  fournisseur: string
}

export interface Conflict {
  transaction: TransactionData
  facture: FactureData | null
  raison: string
  composite_score: number
}

export interface MatchData {
  facture_id: string
  transaction_id: string
  confidence: number
  ecart_montant: string
  statut: string
}

export interface Report {
  tenant_id: string
  date_debut: string
  date_fin: string
  total_transactions: number
  total_rapprochees: number
  total_non_rapprochees: number
  total_ecarts: number
  matches: MatchData[]
  unmatched: TransactionData[]
}

export async function runReconciliation(body: RunRequestBody): Promise<RunResponse> {
  const res = await fetch('/reconciliation/run', {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return json<RunResponse>(res)
}

export async function getConflicts(runId: string): Promise<Conflict[]> {
  const res = await fetch(`/reconciliation/run/${runId}/conflicts`, { headers: authHeaders() })
  return json<Conflict[]>(res)
}

export async function resolveConflict(
  runId: string,
  conflictId: string,
  decision: 'confirmer' | 'rejeter' | 'ecart_accepte',
): Promise<void> {
  const res = await fetch(`/reconciliation/run/${runId}/resolve`, {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ conflict_id: conflictId, decision }),
  })
  checkOk(res)
}

export async function getReport(runId: string): Promise<Report> {
  const res = await fetch(`/reconciliation/run/${runId}/report`, { headers: authHeaders() })
  return json<Report>(res)
}
