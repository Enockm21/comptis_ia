import { useCallback, useEffect, useRef, useState } from 'react'
import { useTenant } from '../lib/TenantContext'
import { fetchWithAuth } from '../lib/http'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────────

interface FactureExtraite {
  fournisseur: string
  date_facture: string
  numero_facture: string
  montant_ht: number
  taux_tva: number
  montant_tva: number
  montant_ttc: number
  compte_charge: string
  journal_code: string
  notes: string
}

interface Facture extends FactureExtraite {
  id: string
  statut: string
  created_at: string
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const fmtEur = (v: number) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(v)

const fmtDate = (s: string) =>
  new Date(s).toLocaleDateString('fr-FR')

// ── Drag-and-drop zone ────────────────────────────────────────────────────────

function DropZone({ onFile }: { onFile: (f: File) => void }) {
  const [dragging, setDragging] = useState(false)
  const ref = useRef<HTMLInputElement>(null)

  const handle = (f: File) => {
    if (f.type.startsWith('image/') || f.type === 'application/pdf') onFile(f)
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) handle(f)
  }

  return (
    <div
      onClick={() => ref.current?.click()}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={cn(
        'border-2 border-dashed rounded-xl p-10 flex flex-col items-center gap-3 cursor-pointer transition-colors',
        dragging
          ? 'border-[var(--accent)] bg-[var(--accent-bg)]'
          : 'border-[var(--border)] hover:border-[var(--accent)] hover:bg-[var(--accent-bg)]'
      )}
    >
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" className="text-[var(--text)] opacity-50">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <polyline points="17,8 12,3 7,8" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <line x1="12" y1="3" x2="12" y2="15" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      </svg>
      <p className="text-[14px] font-medium text-[var(--text-h)] m-0">
        Déposez une facture ici
      </p>
      <p className="text-[12px] text-[var(--text)] m-0">
        JPG, PNG ou PDF — Claude extrait automatiquement les données
      </p>
      <input ref={ref} type="file" accept="image/*,application/pdf" className="hidden"
        onChange={e => { if (e.target.files?.[0]) handle(e.target.files[0]) }} />
    </div>
  )
}

// ── OCR Review form ───────────────────────────────────────────────────────────

function ReviewForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: FactureExtraite
  onSave: (data: FactureExtraite) => void
  onCancel: () => void
}) {
  const [form, setForm] = useState<FactureExtraite>(initial)

  const set = (k: keyof FactureExtraite, v: string) => {
    setForm(prev => {
      const next = { ...prev, [k]: v }
      // Auto-recalculate tva / ttc when ht or taux changes
      if (k === 'montant_ht' || k === 'taux_tva') {
        const ht = parseFloat(k === 'montant_ht' ? v : String(prev.montant_ht)) || 0
        const taux = parseFloat(k === 'taux_tva' ? v : String(prev.taux_tva)) || 0
        const tva = Math.round(ht * taux) / 100
        next.montant_tva = tva
        next.montant_ttc = Math.round((ht + tva) * 100) / 100
      }
      return next
    })
  }

  const Field = ({ label, k, type = 'text' }: { label: string; k: keyof FactureExtraite; type?: string }) => (
    <div className="flex flex-col gap-1">
      <label className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em]">{label}</label>
      <input
        type={type}
        value={String(form[k])}
        onChange={e => set(k, e.target.value)}
        className="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--code-bg)] text-[var(--text-h)] text-[13px] outline-none focus:border-[var(--accent)] transition-colors"
      />
    </div>
  )

  return (
    <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-6">
      <div className="flex items-center gap-2 mb-5">
        <div className="w-2 h-2 rounded-full bg-emerald-500" />
        <p className="text-[13px] font-semibold text-[var(--text-h)] m-0">Données extraites par Claude</p>
        <span className="text-[11px] text-[var(--text)] ml-auto">Vérifiez et corrigez si nécessaire</span>
      </div>
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="col-span-2"><Field label="Fournisseur" k="fournisseur" /></div>
        <Field label="Date facture" k="date_facture" type="date" />
        <Field label="N° facture" k="numero_facture" />
        <Field label="Montant HT (€)" k="montant_ht" type="number" />
        <Field label="Taux TVA (%)" k="taux_tva" type="number" />
        <Field label="Montant TVA (€)" k="montant_tva" type="number" />
        <Field label="Montant TTC (€)" k="montant_ttc" type="number" />
        <Field label="Compte de charge" k="compte_charge" />
        <Field label="Journal" k="journal_code" />
        <div className="col-span-2">
          <div className="flex flex-col gap-1">
            <label className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em]">Notes</label>
            <textarea
              value={form.notes}
              onChange={e => set('notes', e.target.value)}
              rows={2}
              className="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--code-bg)] text-[var(--text-h)] text-[13px] outline-none focus:border-[var(--accent)] resize-none transition-colors"
            />
          </div>
        </div>
      </div>
      <div className="flex gap-2.5 justify-end">
        <Button variant="outline" onClick={onCancel}>Annuler</Button>
        <Button
          onClick={() => onSave(form)}
          className="bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 hover:opacity-90"
        >
          Enregistrer la facture
        </Button>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Factures() {
  const { selected, loading } = useTenant()
  const [factures, setFactures] = useState<Facture[]>([])
  const [analysing, setAnalysing] = useState(false)
  const [preview, setPreview] = useState<string | null>(null)
  const [extracted, setExtracted] = useState<FactureExtraite | null>(null)
  const [saving, setSaving] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadFactures = useCallback(async () => {
    if (!selected) return
    setFetching(true)
    try {
      const r = await fetchWithAuth(`/facturation/factures?tenant_id=${selected.id}`)
      if (r.ok) setFactures(await r.json())
    } finally {
      setFetching(false)
    }
  }, [selected])

  useEffect(() => { loadFactures() }, [loadFactures])

  const handleFile = async (file: File) => {
    if (!selected) return
    setError(null)
    setExtracted(null)
    setPreview(URL.createObjectURL(file))
    setAnalysing(true)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const r = await fetchWithAuth(`/facturation/analyser?tenant_id=${selected.id}`, {
        method: 'POST',
        body: fd,
      })
      if (!r.ok) {
        const err = await r.json().catch(() => ({ detail: 'Erreur inconnue' }))
        throw new Error(err.detail || 'Erreur OCR')
      }
      setExtracted(await r.json())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur OCR')
      setPreview(null)
    } finally {
      setAnalysing(false)
    }
  }

  const handleSave = async (data: FactureExtraite) => {
    if (!selected) return
    setSaving(true)
    try {
      const r = await fetchWithAuth(`/facturation/factures?tenant_id=${selected.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!r.ok) throw new Error('Sauvegarde échouée')
      setExtracted(null)
      setPreview(null)
      await loadFactures()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id: string) => {
    if (!selected) return
    await fetchWithAuth(`/facturation/factures/${id}?tenant_id=${selected.id}`, { method: 'DELETE' })
    setFactures(prev => prev.filter(f => f.id !== id))
  }

  if (loading) return <div className="p-10 text-[var(--text)]">Chargement…</div>
  if (!selected) return <div className="p-10 text-[var(--text)]">Aucun client sélectionné.</div>

  return (
    <div className="px-9 py-8 max-w-[900px]">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-[22px] font-bold text-[var(--text-h)] m-0 mb-1 tracking-[-0.4px]">
          Factures fournisseurs
        </h1>
        <p className="text-[14px] text-[var(--text)] m-0">
          Importez une facture — Claude extrait automatiquement les données comptables
        </p>
      </div>

      {/* Error */}
      {error && (
        <div className="mb-4 px-4 py-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-[13px]">
          {error}
        </div>
      )}

      {/* Upload zone — hidden while analysing or reviewing */}
      {!analysing && !extracted && (
        <div className="mb-6">
          <DropZone onFile={handleFile} />
        </div>
      )}

      {/* Analysing state */}
      {analysing && (
        <div className="mb-6 bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-8 flex flex-col items-center gap-4">
          <div className="flex gap-1">
            {[0, 1, 2].map(i => (
              <div key={i} className="w-2 h-2 rounded-full bg-[var(--accent)] animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }} />
            ))}
          </div>
          <p className="text-[14px] text-[var(--text-h)] font-medium m-0">Claude analyse la facture…</p>
          <p className="text-[12px] text-[var(--text)] m-0">Extraction des données comptables en cours</p>
        </div>
      )}

      {/* Preview + review form */}
      {extracted && !saving && (
        <div className="mb-6 flex flex-col gap-4">
          {preview && (
            <div className="rounded-xl overflow-hidden border border-[var(--border)] max-h-56">
              <img src={preview} alt="facture" className="w-full object-contain max-h-56 bg-white" />
            </div>
          )}
          <ReviewForm
            initial={extracted}
            onSave={handleSave}
            onCancel={() => { setExtracted(null); setPreview(null) }}
          />
        </div>
      )}

      {saving && (
        <div className="mb-6 text-center text-[var(--text)] text-[14px]">Enregistrement…</div>
      )}

      {/* Factures list */}
      <div>
        <h2 className="text-[15px] font-semibold text-[var(--text-h)] m-0 mb-3.5">
          Factures enregistrées
          {fetching && <span className="ml-2 text-[12px] font-normal text-[var(--text)]">Chargement…</span>}
        </h2>
        {factures.length === 0 && !fetching ? (
          <p className="text-[14px] text-[var(--text)]">Aucune facture importée pour ce client.</p>
        ) : (
          <div className="border border-[var(--border)] rounded-xl overflow-hidden">
            {factures.map((f, i) => (
              <div
                key={f.id}
                className={cn(
                  'flex items-start gap-4 px-5 py-4 bg-[var(--card-bg)]',
                  i < factures.length - 1 && 'border-b border-[var(--border)]'
                )}
              >
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="m-0 text-[13px] font-semibold text-[var(--text-h)] truncate">{f.fournisseur}</p>
                    {f.numero_facture && (
                      <span className="text-[11px] text-[var(--text)] shrink-0">#{f.numero_facture}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-[12px] text-[var(--text)]">{fmtDate(f.date_facture)}</span>
                    <span className="text-[12px] text-[var(--text)]">Compte {f.compte_charge}</span>
                    {f.notes && <span className="text-[11px] text-[var(--text)] italic truncate max-w-[200px]">{f.notes}</span>}
                  </div>
                </div>

                {/* Amounts */}
                <div className="text-right shrink-0">
                  <p className="m-0 text-[15px] font-bold text-[var(--text-h)] tabular-nums">{fmtEur(f.montant_ttc)}</p>
                  <p className="m-0 text-[11px] text-[var(--text)]">
                    HT {fmtEur(f.montant_ht)} + TVA {f.taux_tva}%
                  </p>
                </div>

                {/* Delete */}
                <button
                  onClick={() => handleDelete(f.id)}
                  className="shrink-0 p-1.5 rounded-lg text-[var(--text)] hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                  title="Supprimer"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
