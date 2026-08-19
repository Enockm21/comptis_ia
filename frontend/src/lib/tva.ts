import { fetchWithAuth } from './http'

export interface TVALine {
  taux: string
  base_ht: string
  montant_tva: string
  nb_factures: number
}

export interface TVACompute {
  date_debut: string
  date_fin: string
  tva_collectee: string
  tva_deductible: string
  tva_nette: string
  est_credit: boolean
  lignes_collectee: TVALine[]
  lignes_deductible: TVALine[]
}

export interface TVADeclaration {
  id: string
  tenant_id: string
  date_debut: string
  date_fin: string
  tva_collectee: string
  tva_deductible: string
  tva_nette: string
  lignes: Array<{ type: string; taux: string; base_ht: string; montant_tva: string; nb_factures: number }>
  statut: 'brouillon' | 'deposee' | 'payee'
  created_at: string
  deposee_le: string | null
  payee_le: string | null
}

export async function computeTVA(tenantId: string, dateDebut: string, dateFin: string): Promise<TVACompute> {
  const params = new URLSearchParams({ tenant_id: tenantId, date_debut: dateDebut, date_fin: dateFin })
  const res = await fetchWithAuth(`/tva/compute?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function createDeclaration(body: {
  tenant_id: string
  date_debut: string
  date_fin: string
  tva_collectee: string
  tva_deductible: string
  tva_nette: string
  lignes_collectee: TVALine[]
  lignes_deductible: TVALine[]
}): Promise<TVADeclaration> {
  const res = await fetchWithAuth('/tva/declarations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function listDeclarations(tenantId: string): Promise<TVADeclaration[]> {
  const res = await fetchWithAuth(`/tva/declarations?tenant_id=${tenantId}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function exportCA3(tenantId: string, dateDebut: string, dateFin: string): Promise<void> {
  const params = new URLSearchParams({ tenant_id: tenantId, date_debut: dateDebut, date_fin: dateFin })
  const res = await fetchWithAuth(`/tva/export-ca3?${params}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  const month = dateDebut.slice(0, 7)
  a.href = url
  a.download = `CA3_${month}.pdf`
  a.click()
  URL.revokeObjectURL(url)
}

export async function updateStatut(declarationId: string, statut: string): Promise<TVADeclaration> {
  const res = await fetchWithAuth(`/tva/declarations/${declarationId}/statut`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ statut }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
