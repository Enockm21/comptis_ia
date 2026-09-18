import { useCallback, useEffect, useState } from 'react'
import { useTenant } from '../lib/TenantContext'
import { fetchWithAuth } from '../lib/http'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────────

interface Ligne {
  description: string
  quantite: number
  prix_unitaire: number
  taux_tva: number
}

interface LigneSchema extends Ligne {
  id: string
  montant_ht: number
  montant_ttc: number
  ordre: number
}

interface FactureClient {
  id: string
  type: string
  statut: string
  numero: string
  date_emission: string
  date_echeance: string | null
  client_nom: string
  client_adresse: string
  client_email: string
  notes: string
  total_ht: number
  total_tva: number
  total_ttc: number
  lignes: LigneSchema[]
  created_at: string
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const fmtEur = (v: number) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(v)

const fmtDate = (s: string) => new Date(s).toLocaleDateString('fr-FR')

const STATUTS: Record<string, { label: string; classes: string }> = {
  brouillon: { label: 'Brouillon', classes: 'bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300' },
  envoyee:   { label: 'Envoyée',   classes: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  payee:     { label: 'Payée',     classes: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' },
  annulee:   { label: 'Annulée',   classes: 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400' },
}

// ── Empty ligne factory ───────────────────────────────────────────────────────

const newLigne = (): Ligne => ({ description: '', quantite: 1, prix_unitaire: 0, taux_tva: 20 })

// ── Create form ────────────────────────────────────────────────────────────────

interface CreateFormProps {
  onCreated: (f: FactureClient) => void
  onCancel: () => void
  tenantId: string
}

function CreateForm({ onCreated, onCancel, tenantId }: CreateFormProps) {
  const today = new Date().toISOString().split('T')[0]
  const in30 = new Date(Date.now() + 30 * 86400000).toISOString().split('T')[0]

  const [type, setType] = useState<'facture' | 'devis'>('facture')
  const [dateEmission, setDateEmission] = useState(today)
  const [dateEcheance, setDateEcheance] = useState(in30)
  const [clientNom, setClientNom] = useState('')
  const [clientAdresse, setClientAdresse] = useState('')
  const [clientEmail, setClientEmail] = useState('')
  const [notes, setNotes] = useState('')
  const [lignes, setLignes] = useState<Ligne[]>([newLigne()])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const updateLigne = (i: number, k: keyof Ligne, v: string) =>
    setLignes(prev => prev.map((l, idx) => idx === i ? { ...l, [k]: k === 'description' ? v : parseFloat(v) || 0 } : l))

  const totalHt = lignes.reduce((s, l) => s + l.quantite * l.prix_unitaire, 0)
  const totalTtc = lignes.reduce((s, l) => {
    const ht = l.quantite * l.prix_unitaire
    return s + ht + ht * l.taux_tva / 100
  }, 0)

  const handleSubmit = async () => {
    if (!clientNom || lignes.some(l => !l.description)) {
      setError('Remplissez le nom du client et toutes les descriptions de lignes.')
      return
    }
    setSaving(true); setError(null)
    try {
      const r = await fetchWithAuth(`/facturation-client/factures?tenant_id=${tenantId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type, date_emission: dateEmission,
          date_echeance: dateEcheance || null,
          client_nom: clientNom, client_adresse: clientAdresse,
          client_email: clientEmail, notes,
          lignes,
        }),
      })
      if (!r.ok) throw new Error((await r.json()).detail || 'Erreur')
      onCreated(await r.json())
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur')
    } finally {
      setSaving(false)
    }
  }

  const inputCls = 'px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--code-bg)] text-[var(--text-h)] text-[13px] outline-none focus:border-[var(--accent)] transition-colors'

  return (
    <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-6">
      <h2 className="text-[15px] font-semibold text-[var(--text-h)] m-0 mb-5">
        Nouveau {type === 'facture' ? 'facture' : 'devis'}
      </h2>

      {/* Type toggle */}
      <div className="flex gap-2 mb-5">
        {(['facture', 'devis'] as const).map(t => (
          <button key={t} onClick={() => setType(t)}
            className={cn('px-4 py-1.5 rounded-lg text-[13px] font-medium border transition-colors',
              type === t
                ? 'bg-[var(--accent)] text-white border-[var(--accent)]'
                : 'border-[var(--border)] text-[var(--text)] hover:border-[var(--accent)]'
            )}
          >
            {t === 'facture' ? 'Facture' : 'Devis'}
          </button>
        ))}
      </div>

      {/* Client + dates */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="col-span-2 flex flex-col gap-1">
          <label className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em]">Nom du client *</label>
          <input value={clientNom} onChange={e => setClientNom(e.target.value)} className={inputCls} placeholder="Société ABC" />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em]">Adresse</label>
          <input value={clientAdresse} onChange={e => setClientAdresse(e.target.value)} className={inputCls} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em]">Email</label>
          <input type="email" value={clientEmail} onChange={e => setClientEmail(e.target.value)} className={inputCls} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em]">Date d'émission</label>
          <input type="date" value={dateEmission} onChange={e => setDateEmission(e.target.value)} className={inputCls} />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em]">Date d'échéance</label>
          <input type="date" value={dateEcheance} onChange={e => setDateEcheance(e.target.value)} className={inputCls} />
        </div>
      </div>

      {/* Lines */}
      <div className="mb-4">
        <div className="grid grid-cols-[1fr_70px_100px_70px_28px] gap-1.5 mb-1.5">
          {['Description', 'Qté', 'P.U. HT', 'TVA %', ''].map(h => (
            <span key={h} className="text-[10px] font-semibold text-[var(--text)] uppercase tracking-[0.05em] px-1">{h}</span>
          ))}
        </div>
        {lignes.map((l, i) => (
          <div key={i} className="grid grid-cols-[1fr_70px_100px_70px_28px] gap-1.5 mb-1.5">
            <input value={l.description} onChange={e => updateLigne(i, 'description', e.target.value)}
              placeholder="Prestation de service" className={inputCls} />
            <input type="number" value={l.quantite} onChange={e => updateLigne(i, 'quantite', e.target.value)}
              min="0" step="0.01" className={cn(inputCls, 'text-right')} />
            <input type="number" value={l.prix_unitaire} onChange={e => updateLigne(i, 'prix_unitaire', e.target.value)}
              min="0" step="0.01" className={cn(inputCls, 'text-right')} />
            <select value={l.taux_tva} onChange={e => updateLigne(i, 'taux_tva', e.target.value)}
              className={inputCls}>
              {[0, 5.5, 10, 20].map(t => <option key={t} value={t}>{t}%</option>)}
            </select>
            <button onClick={() => setLignes(prev => prev.filter((_, idx) => idx !== i))}
              disabled={lignes.length === 1}
              className="flex items-center justify-center text-[var(--text)] hover:text-red-500 disabled:opacity-30 transition-colors">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        ))}
        <button onClick={() => setLignes(prev => [...prev, newLigne()])}
          className="text-[12px] text-[var(--accent)] hover:underline mt-1">
          + Ajouter une ligne
        </button>
      </div>

      {/* Totals preview */}
      <div className="flex justify-end mb-4">
        <div className="text-right text-[13px] text-[var(--text)] space-y-0.5">
          <div>Total HT : <span className="font-semibold text-[var(--text-h)]">{fmtEur(totalHt)}</span></div>
          <div>TVA : <span className="font-semibold text-[var(--text-h)]">{fmtEur(totalTtc - totalHt)}</span></div>
          <div className="text-[15px]">Total TTC : <span className="font-bold text-[var(--accent)]">{fmtEur(totalTtc)}</span></div>
        </div>
      </div>

      {/* Notes */}
      <div className="flex flex-col gap-1 mb-5">
        <label className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em]">Notes</label>
        <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2}
          className={cn(inputCls, 'resize-none')} />
      </div>

      {error && <p className="text-red-500 text-[12px] mb-3">{error}</p>}

      <div className="flex gap-2.5 justify-end">
        <Button variant="outline" onClick={onCancel}>Annuler</Button>
        <Button disabled={saving} onClick={handleSubmit}
          className="bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 hover:opacity-90">
          {saving ? 'Création…' : `Créer la ${type}`}
        </Button>
      </div>
    </div>
  )
}

// ── Facture row ────────────────────────────────────────────────────────────────

function FactureRow({ f, tenantId, onDeleted, onStatutChanged }: {
  f: FactureClient
  tenantId: string
  onDeleted: (id: string) => void
  onStatutChanged: (id: string, s: string) => void
}) {
  const [downloading, setDownloading] = useState(false)
  const [relanceText, setRelanceText] = useState<string | null>(null)

  const downloadPdf = async () => {
    setDownloading(true)
    try {
      const r = await fetchWithAuth(`/facturation-client/factures/${f.id}/pdf?tenant_id=${tenantId}`)
      if (!r.ok) return
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `${f.numero}.pdf`; a.click()
      URL.revokeObjectURL(url)
    } finally {
      setDownloading(false)
    }
  }

  const setStatut = async (s: string) => {
    const r = await fetchWithAuth(
      `/facturation-client/factures/${f.id}/statut?tenant_id=${tenantId}&statut=${s}`,
      { method: 'PATCH' }
    )
    if (r.ok) onStatutChanged(f.id, s)
  }

  const del = async () => {
    await fetchWithAuth(`/facturation-client/factures/${f.id}?tenant_id=${tenantId}`, { method: 'DELETE' })
    onDeleted(f.id)
  }

  const genRelance = () => {
    const echeance = f.date_echeance ? fmtDate(f.date_echeance) : 'échue'
    const text = `Objet : Relance facture ${f.numero} — ${fmtEur(f.total_ttc)}\n\nBonjour,\n\nSauf erreur de notre part, notre facture n° ${f.numero} d'un montant de ${fmtEur(f.total_ttc)} TTC, émise le ${fmtDate(f.date_emission)} et arrivée à échéance le ${echeance}, n'a pas encore été réglée.\n\nNous vous remercions de bien vouloir procéder au paiement dans les meilleurs délais, ou de nous contacter si vous avez des questions.\n\nCordialement`
    setRelanceText(text)
    navigator.clipboard?.writeText(text).catch(() => {})
  }

  const st = STATUTS[f.statut] ?? { label: f.statut, classes: 'bg-zinc-100 text-zinc-600' }

  return (
    <div className="bg-[var(--card-bg)]">
    {relanceText && (
      <div className="mx-5 mb-3 mt-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800">
        <div className="flex items-center justify-between mb-2">
          <p className="text-[11px] font-semibold text-amber-800 dark:text-amber-400 m-0">Email de relance (copié dans le presse-papier)</p>
          <button onClick={() => setRelanceText(null)} className="text-amber-600 hover:text-amber-900 text-[12px]">✕</button>
        </div>
        <pre className="text-[11px] text-amber-900 dark:text-amber-300 whitespace-pre-wrap font-sans m-0">{relanceText}</pre>
      </div>
    )}
    <div className="flex items-start gap-4 px-5 py-4">
      {/* Left */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <span className="text-[11px] font-bold text-[var(--text)] bg-[var(--code-bg)] px-2 py-0.5 rounded">
            {f.type === 'devis' ? 'DEVIS' : 'FACTURE'}
          </span>
          <span className="text-[13px] font-semibold text-[var(--text-h)]">{f.numero}</span>
          <span className={cn('px-2 py-0.5 rounded-full text-[11px] font-semibold', st.classes)}>{st.label}</span>
        </div>
        <p className="m-0 text-[13px] text-[var(--text-h)] font-medium truncate">{f.client_nom}</p>
        <div className="flex gap-3 mt-1 flex-wrap">
          <span className="text-[12px] text-[var(--text)]">{fmtDate(f.date_emission)}</span>
          {f.date_echeance && (
            <span className="text-[12px] text-[var(--text)]">Échéance : {fmtDate(f.date_echeance)}</span>
          )}
        </div>
      </div>

      {/* Right */}
      <div className="shrink-0 text-right mr-4">
        <p className="m-0 text-[16px] font-bold text-[var(--text-h)] tabular-nums">{fmtEur(f.total_ttc)}</p>
        <p className="m-0 text-[11px] text-[var(--text)]">HT {fmtEur(f.total_ht)}</p>
      </div>

      {/* Actions */}
      <div className="flex flex-col gap-1 shrink-0">
        <button onClick={downloadPdf} disabled={downloading}
          className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--accent)] hover:underline disabled:opacity-50">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"
              stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          PDF
        </button>

        {f.statut === 'brouillon' && (
          <button onClick={() => setStatut('envoyee')}
            className="text-[11px] font-medium text-blue-600 dark:text-blue-400 hover:underline">
            → Envoyée
          </button>
        )}
        {f.statut === 'envoyee' && (
          <button onClick={genRelance}
            className="text-[11px] font-medium text-amber-600 dark:text-amber-400 hover:underline">
            📧 Relance
          </button>
        )}
        {f.statut === 'envoyee' && (
          <button onClick={() => setStatut('payee')}
            className="text-[11px] font-medium text-emerald-600 hover:underline">
            ✓ Payée
          </button>
        )}
        <button onClick={del}
          className="text-[11px] text-[var(--text)] hover:text-red-500 transition-colors">
          Supprimer
        </button>
      </div>
    </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function FacturesClient() {
  const { selected, loading } = useTenant()
  const [factures, setFactures] = useState<FactureClient[]>([])
  const [fetching, setFetching] = useState(false)
  const [creating, setCreating] = useState(false)

  const loadFactures = useCallback(async () => {
    if (!selected) return
    setFetching(true)
    try {
      const r = await fetchWithAuth(`/facturation-client/factures?tenant_id=${selected.id}`)
      if (r.ok) setFactures(await r.json())
    } finally {
      setFetching(false)
    }
  }, [selected])

  useEffect(() => { loadFactures() }, [loadFactures])

  const onCreated = (f: FactureClient) => {
    setFactures(prev => [f, ...prev])
    setCreating(false)
  }

  const onDeleted = (id: string) => setFactures(prev => prev.filter(f => f.id !== id))

  const onStatutChanged = (id: string, statut: string) =>
    setFactures(prev => prev.map(f => f.id === id ? { ...f, statut } : f))

  if (loading) return <div className="p-10 text-[var(--text)]">Chargement…</div>
  if (!selected) return <div className="p-10 text-[var(--text)]">Aucun client sélectionné.</div>

  const totalImpaye = factures
    .filter(f => f.statut === 'envoyee')
    .reduce((s, f) => s + f.total_ttc, 0)

  return (
    <div className="px-9 py-8 max-w-[900px]">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-[22px] font-bold text-[var(--text-h)] m-0 mb-1 tracking-[-0.4px]">
            Facturation client
          </h1>
          <p className="text-[14px] text-[var(--text)] m-0">Devis et factures — PDF automatique</p>
        </div>
        {!creating && (
          <Button onClick={() => setCreating(true)}
            className="bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 hover:opacity-90 shrink-0">
            + Nouvelle facture
          </Button>
        )}
      </div>

      {/* Impayés banner */}
      {totalImpaye > 0 && (
        <div className="mb-5 px-4 py-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800">
          <p className="m-0 text-[13px] font-semibold text-amber-800 dark:text-amber-400">
            {factures.filter(f => f.statut === 'envoyee').length} facture(s) en attente de paiement —{' '}
            <span className="tabular-nums">{new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(totalImpaye)}</span>
          </p>
        </div>
      )}

      {/* Create form */}
      {creating && (
        <div className="mb-6">
          <CreateForm
            tenantId={selected.id}
            onCreated={onCreated}
            onCancel={() => setCreating(false)}
          />
        </div>
      )}

      {/* List */}
      {fetching ? (
        <p className="text-[var(--text)] text-[14px]">Chargement…</p>
      ) : factures.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-[var(--text)] text-[14px] mb-2">Aucune facture pour ce client.</p>
          {!creating && (
            <button onClick={() => setCreating(true)} className="text-[var(--accent)] text-[13px] hover:underline">
              Créer la première facture
            </button>
          )}
        </div>
      ) : (
        <div className="border border-[var(--border)] rounded-xl overflow-hidden divide-y divide-[var(--border)]">
          {factures.map(f => (
            <FactureRow
              key={f.id} f={f} tenantId={selected.id}
              onDeleted={onDeleted} onStatutChanged={onStatutChanged}
            />
          ))}
        </div>
      )}
    </div>
  )
}
