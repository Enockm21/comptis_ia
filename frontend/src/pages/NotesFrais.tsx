import { useCallback, useEffect, useRef, useState } from 'react'
import { useTenant } from '../lib/TenantContext'
import { fetchWithAuth } from '../lib/http'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface Depense {
  date_depense: string
  fournisseur: string
  description: string
  montant_ht: number
  taux_tva: number
  montant_tva: number
  montant_ttc: number
  compte_charge: string
  categorie: string
}

interface NoteFrais extends Depense {
  id: string
  statut: string
  submitted_by: string
  created_at: string
}

const fmtEur = (v: number) => new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(v)
const fmtDate = (s: string) => new Date(s).toLocaleDateString('fr-FR')

const STATUTS: Record<string, { label: string; classes: string }> = {
  soumis:   { label: 'Soumis',   classes: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  approuve: { label: 'Approuvé', classes: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' },
  refuse:   { label: 'Refusé',   classes: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400' },
}

const CATEGORIES: Record<string, string> = {
  Restauration: '🍽',
  Transport: '🚆',
  Hébergement: '🏨',
  Carburant: '⛽',
  Fournitures: '📦',
  Informatique: '💻',
  Télécom: '📱',
  Formation: '📚',
  Cadeau: '🎁',
  Autre: '📄',
}

function ReviewForm({ initial, onSave, onCancel }: {
  initial: Depense; onSave: (d: Depense) => void; onCancel: () => void
}) {
  const [form, setForm] = useState<Depense>(initial)
  const set = (k: keyof Depense, v: string) => {
    setForm(prev => {
      const next = { ...prev, [k]: k === 'fournisseur' || k === 'description' || k === 'compte_charge' || k === 'categorie' ? v : parseFloat(v) || 0 }
      if (k === 'montant_ht' || k === 'taux_tva') {
        const ht = parseFloat(k === 'montant_ht' ? v : String(prev.montant_ht)) || 0
        const tx = parseFloat(k === 'taux_tva' ? v : String(prev.taux_tva)) || 0
        next.montant_tva = Math.round(ht * tx) / 100
        next.montant_ttc = Math.round((ht + next.montant_tva) * 100) / 100
      }
      return next
    })
  }
  const inp = 'px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--code-bg)] text-[var(--text-h)] text-[13px] outline-none focus:border-[var(--accent)] transition-colors'
  const F = ({ label, k, type = 'text' }: { label: string; k: keyof Depense; type?: string }) => (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em]">{label}</label>
      <input type={type} value={String(form[k])} onChange={e => set(k, e.target.value)} className={inp} />
    </div>
  )
  return (
    <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-5">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-2 h-2 rounded-full bg-emerald-500" />
        <p className="text-[13px] font-semibold text-[var(--text-h)] m-0">Données extraites — vérifiez et corrigez</p>
      </div>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <F label="Date" k="date_depense" type="date" />
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em]">Catégorie</label>
          <select value={form.categorie} onChange={e => set('categorie', e.target.value)} className={inp}>
            {Object.keys(CATEGORIES).map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div className="col-span-2"><F label="Fournisseur / Commerce" k="fournisseur" /></div>
        <div className="col-span-2"><F label="Description" k="description" /></div>
        <F label="Montant HT (€)" k="montant_ht" type="number" />
        <F label="TVA (%)" k="taux_tva" type="number" />
        <F label="TVA (€)" k="montant_tva" type="number" />
        <F label="TTC (€)" k="montant_ttc" type="number" />
        <F label="Compte PCG" k="compte_charge" />
      </div>
      <div className="flex gap-2 justify-end">
        <Button variant="outline" onClick={onCancel}>Annuler</Button>
        <Button onClick={() => onSave(form)}
          className="bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 hover:opacity-90">
          Soumettre
        </Button>
      </div>
    </div>
  )
}

export default function NotesFrais() {
  const { selected, loading } = useTenant()
  const [notes, setNotes] = useState<NoteFrais[]>([])
  const [analysing, setAnalysing] = useState(false)
  const [extracted, setExtracted] = useState<Depense | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [fetching, setFetching] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    if (!selected) return
    setFetching(true)
    fetchWithAuth(`/notes-frais?tenant_id=${selected.id}`)
      .then(r => r.ok ? r.json() : []).then(setNotes).finally(() => setFetching(false))
  }, [selected])

  useEffect(() => { load() }, [load])

  const handleFile = async (file: File) => {
    if (!selected) return
    setError(null); setExtracted(null); setAnalysing(true)
    try {
      const fd = new FormData(); fd.append('file', file)
      const r = await fetchWithAuth(`/notes-frais/analyser?tenant_id=${selected.id}`, { method: 'POST', body: fd })
      if (!r.ok) throw new Error((await r.json()).detail || 'Erreur OCR')
      setExtracted(await r.json())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur')
    } finally { setAnalysing(false) }
  }

  const handleSave = async (data: Depense) => {
    if (!selected) return
    const r = await fetchWithAuth(`/notes-frais?tenant_id=${selected.id}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
    })
    if (r.ok) { setExtracted(null); load() }
  }

  const setStatut = async (id: string, statut: string) => {
    if (!selected) return
    const r = await fetchWithAuth(`/notes-frais/${id}/statut?tenant_id=${selected.id}&statut=${statut}`, { method: 'PATCH' })
    if (r.ok) setNotes(prev => prev.map(n => n.id === id ? { ...n, statut } : n))
  }

  const del = async (id: string) => {
    if (!selected) return
    await fetchWithAuth(`/notes-frais/${id}?tenant_id=${selected.id}`, { method: 'DELETE' })
    setNotes(prev => prev.filter(n => n.id !== id))
  }

  if (loading) return <div className="p-10 text-[var(--text)]">Chargement…</div>
  if (!selected) return <div className="p-10 text-[var(--text)]">Aucun client sélectionné.</div>

  const totalSoumis = notes.filter(n => n.statut === 'soumis').reduce((s, n) => s + n.montant_ttc, 0)
  const totalApprouve = notes.filter(n => n.statut === 'approuve').reduce((s, n) => s + n.montant_ttc, 0)

  return (
    <div className="px-9 py-8 max-w-[900px]">
      <div className="mb-6">
        <h1 className="text-[22px] font-bold text-[var(--text-h)] m-0 mb-1 tracking-[-0.4px]">Notes de frais</h1>
        <p className="text-[14px] text-[var(--text)] m-0">Photographiez un ticket — Claude extrait automatiquement</p>
      </div>

      {/* Totaux */}
      {notes.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-6">
          {[
            { label: 'En attente', val: totalSoumis, color: 'text-blue-600 dark:text-blue-400' },
            { label: 'Approuvé', val: totalApprouve, color: 'text-emerald-600' },
            { label: 'Total dépenses', val: totalSoumis + totalApprouve, color: 'text-[var(--text-h)]' },
          ].map(({ label, val, color }) => (
            <div key={label} className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-4">
              <p className="text-[11px] text-[var(--text)] uppercase tracking-[0.05em] m-0">{label}</p>
              <p className={cn('text-[20px] font-bold tabular-nums m-0 mt-0.5', color)}>{fmtEur(val)}</p>
            </div>
          ))}
        </div>
      )}

      {error && <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-[13px]">{error}</div>}

      {/* Upload */}
      {!analysing && !extracted && (
        <div className="mb-6">
          <div onClick={() => fileRef.current?.click()}
            className="border-2 border-dashed border-[var(--border)] rounded-xl p-8 flex flex-col items-center gap-3 cursor-pointer hover:border-[var(--accent)] hover:bg-[var(--accent-bg)] transition-colors">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" className="text-[var(--text)] opacity-50">
              <rect x="3" y="3" width="18" height="18" rx="3" stroke="currentColor" strokeWidth="2"/>
              <circle cx="8.5" cy="8.5" r="1.5" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M21 15l-5-5-4 4-3-3-3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            <p className="text-[14px] font-medium text-[var(--text-h)] m-0">Importer un justificatif</p>
            <p className="text-[12px] text-[var(--text)] m-0">Ticket, reçu, facture — JPG, PNG ou PDF</p>
          </div>
          <input ref={fileRef} type="file" accept="image/*,application/pdf" className="hidden"
            onChange={e => { if (e.target.files?.[0]) handleFile(e.target.files[0]) }} />
        </div>
      )}

      {analysing && (
        <div className="mb-6 bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-8 flex flex-col items-center gap-3">
          <div className="flex gap-1">{[0,1,2].map(i => (
            <div key={i} className="w-2 h-2 rounded-full bg-[var(--accent)] animate-bounce" style={{animationDelay:`${i*0.15}s`}} />
          ))}</div>
          <p className="text-[14px] font-medium text-[var(--text-h)] m-0">Claude analyse le justificatif…</p>
        </div>
      )}

      {extracted && (
        <div className="mb-6">
          <ReviewForm initial={extracted} onSave={handleSave} onCancel={() => setExtracted(null)} />
        </div>
      )}

      {/* List */}
      <div>
        <h2 className="text-[15px] font-semibold text-[var(--text-h)] m-0 mb-3">Notes de frais{fetching && <span className="ml-2 text-[12px] font-normal text-[var(--text)]">…</span>}</h2>
        {notes.length === 0 && !fetching ? (
          <p className="text-[14px] text-[var(--text)]">Aucune note de frais.</p>
        ) : (
          <div className="border border-[var(--border)] rounded-xl overflow-hidden divide-y divide-[var(--border)]">
            {notes.map(n => {
              const st = STATUTS[n.statut] ?? STATUTS.soumis
              const emoji = CATEGORIES[n.categorie] ?? '📄'
              return (
                <div key={n.id} className="flex items-center gap-4 px-5 py-3.5 bg-[var(--card-bg)]">
                  <span className="text-xl shrink-0">{emoji}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <p className="m-0 text-[13px] font-semibold text-[var(--text-h)] truncate">{n.fournisseur}</p>
                      <span className={cn('shrink-0 px-2 py-0.5 rounded-full text-[10px] font-semibold', st.classes)}>{st.label}</span>
                    </div>
                    <p className="m-0 text-[11px] text-[var(--text)]">{fmtDate(n.date_depense)} · {n.categorie} · compte {n.compte_charge}</p>
                  </div>
                  <div className="text-right shrink-0 mr-3">
                    <p className="m-0 text-[14px] font-bold tabular-nums text-[var(--text-h)]">{fmtEur(n.montant_ttc)}</p>
                    <p className="m-0 text-[10px] text-[var(--text)]">HT {fmtEur(n.montant_ht)}</p>
                  </div>
                  <div className="flex flex-col gap-1 shrink-0 text-right">
                    {n.statut === 'soumis' && <>
                      <button onClick={() => setStatut(n.id, 'approuve')} className="text-[11px] text-emerald-600 hover:underline">✓ Approuver</button>
                      <button onClick={() => setStatut(n.id, 'refuse')} className="text-[11px] text-red-500 hover:underline">✗ Refuser</button>
                    </>}
                    <button onClick={() => del(n.id)} className="text-[10px] text-[var(--text)] hover:text-red-500 transition-colors">Supprimer</button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
