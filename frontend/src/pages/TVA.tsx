import { useState, useEffect, useCallback } from 'react'
import { useTenant } from '../lib/TenantContext'
import { computeTVA, createDeclaration, exportCA3, listDeclarations, updateStatut } from '../lib/tva'
import type { TVACompute, TVADeclaration, TVALine } from '../lib/tva'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const fmt = (v: string | number) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(Number(v))

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })

function periodDefaults() {
  const now = new Date()
  const y = now.getFullYear()
  const m = now.getMonth()
  const debut = new Date(y, m - 1, 1)
  const fin = new Date(y, m, 0)
  return {
    debut: debut.toISOString().slice(0, 10),
    fin: fin.toISOString().slice(0, 10),
  }
}

const STATUT_MAP: Record<string, { label: string; classes: string }> = {
  brouillon: { label: 'Brouillon', classes: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400' },
  deposee:   { label: 'Déposée',   classes: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' },
  payee:     { label: 'Payée',     classes: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400' },
}

function StatutBadge({ statut }: { statut: string }) {
  const s = STATUT_MAP[statut] ?? STATUT_MAP.brouillon
  return (
    <span className={cn('px-2.5 py-0.5 rounded-md text-[12px] font-semibold', s.classes)}>
      {s.label}
    </span>
  )
}

function TVALineTable({ lines, label }: { lines: TVALine[]; label: string }) {
  if (lines.length === 0) return null
  return (
    <div className="mb-5">
      <p className="m-0 mb-2 text-[13px] font-semibold text-[var(--text-h)]">{label}</p>
      <div className="border border-[var(--border)] rounded-[10px] overflow-hidden">
        <table className="w-full border-collapse">
          <thead>
            <tr className="bg-[rgba(107,99,117,0.04)]">
              {['Taux TVA', 'Base HT', 'Montant TVA', 'Nb factures'].map(h => (
                <th key={h} className={cn(
                  'px-3.5 py-2.5 text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.07em] border-b border-[var(--border)]',
                  h === 'Taux TVA' || h === 'Nb factures' ? 'text-left' : 'text-right'
                )}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {lines.map((l, i) => (
              <tr key={i} className={i < lines.length - 1 ? 'border-b border-[var(--border)]' : ''}>
                <td className="px-3.5 py-2.5 text-[14px] text-[var(--text-h)]">{Number(l.taux).toFixed(1)}%</td>
                <td className="px-3.5 py-2.5 text-[14px] text-[var(--text-h)] text-right font-mono tabular-nums">{fmt(l.base_ht)}</td>
                <td className="px-3.5 py-2.5 text-[14px] font-semibold text-[var(--text-h)] text-right font-mono tabular-nums">{fmt(l.montant_tva)}</td>
                <td className="px-3.5 py-2.5 text-[14px] text-[var(--text)]">{l.nb_factures}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function TVA() {
  const { selected: selectedTenant } = useTenant()
  const [dateDebut, setDateDebut] = useState(periodDefaults().debut)
  const [dateFin, setDateFin] = useState(periodDefaults().fin)
  const [compute, setCompute] = useState<TVACompute | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [history, setHistory] = useState<TVADeclaration[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadHistory = useCallback(async (tid: string) => {
    setHistoryLoading(true)
    try {
      setHistory(await listDeclarations(tid))
    } catch { } finally {
      setHistoryLoading(false)
    }
  }, [])

  useEffect(() => {
    if (selectedTenant) loadHistory(selectedTenant.id)
  }, [selectedTenant, loadHistory])

  async function handleCompute() {
    if (!selectedTenant) return
    setLoading(true); setError(null); setCompute(null)
    try {
      setCompute(await computeTVA(selectedTenant.id, dateDebut, dateFin))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur lors du calcul')
    } finally {
      setLoading(false)
    }
  }

  async function handleSave() {
    if (!selectedTenant || !compute) return
    setSaving(true)
    try {
      await createDeclaration({
        tenant_id: selectedTenant.id,
        date_debut: compute.date_debut,
        date_fin: compute.date_fin,
        tva_collectee: compute.tva_collectee,
        tva_deductible: compute.tva_deductible,
        tva_nette: compute.tva_nette,
        lignes_collectee: compute.lignes_collectee,
        lignes_deductible: compute.lignes_deductible,
      })
      setCompute(null)
      await loadHistory(selectedTenant.id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erreur lors de la sauvegarde')
    } finally {
      setSaving(false)
    }
  }

  async function handleStatut(id: string, statut: string) {
    if (!selectedTenant) return
    try {
      await updateStatut(id, statut)
      await loadHistory(selectedTenant.id)
    } catch { }
  }

  function setPreset(months: number) {
    const now = new Date()
    const debut = new Date(now.getFullYear(), now.getMonth() - months, 1)
    const fin = new Date(now.getFullYear(), now.getMonth() - months + 1, 0)
    setDateDebut(debut.toISOString().slice(0, 10))
    setDateFin(fin.toISOString().slice(0, 10))
    setCompute(null)
  }

  const nette = compute ? Number(compute.tva_nette) : 0
  const netteColor = nette < 0 ? '#10b981' : nette > 0 ? '#ef4444' : 'var(--text-h)'

  return (
    <div className="px-9 py-8 max-w-[760px]">
      {/* Header */}
      <div className="mb-7">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--accent-bg)] border border-[var(--accent-border)] mb-3">
          <div className="w-1.5 h-1.5 rounded-full bg-[#aa3bff]" />
          <span className="text-[11px] font-semibold text-[#aa3bff] uppercase tracking-[0.08em]">CA3 — Réel normal</span>
        </div>
        <h1 className="text-[26px] font-bold text-[var(--text-h)] m-0 mb-1.5 tracking-[-0.4px]">
          Déclaration de TVA
        </h1>
        <p className="text-[14px] text-[var(--text)] m-0">
          Calculez et enregistrez vos déclarations CA3 à partir de vos factures PNICompta.
        </p>
      </div>

      {/* Period selector */}
      <div className="border border-[var(--border)] rounded-xl px-[22px] py-5 bg-[var(--card-bg)] mb-5">
        <p className="m-0 mb-3 text-[13px] font-semibold text-[var(--text-h)]">Période</p>
        <div className="flex gap-2 mb-3.5 flex-wrap">
          {['Mois précédent', 'Il y a 2 mois', 'Il y a 3 mois'].map((label, i) => (
            <button
              key={label}
              onClick={() => setPreset(i + 1)}
              className="px-3 py-1.5 rounded-md border border-[var(--border)] bg-transparent text-[var(--text)] text-[12px] cursor-pointer font-medium hover:bg-[var(--code-bg)] transition-colors"
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex gap-3 items-end flex-wrap">
          <label className="flex flex-col gap-1.5">
            <span className="text-[12px] text-[var(--text)] font-medium">Du</span>
            <input
              type="date"
              value={dateDebut}
              onChange={e => { setDateDebut(e.target.value); setCompute(null) }}
              className="px-2.5 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] text-[var(--text-h)] text-[14px] outline-none"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-[12px] text-[var(--text)] font-medium">Au</span>
            <input
              type="date"
              value={dateFin}
              onChange={e => { setDateFin(e.target.value); setCompute(null) }}
              className="px-2.5 py-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] text-[var(--text-h)] text-[14px] outline-none"
            />
          </label>
          <Button
            onClick={handleCompute}
            disabled={loading || !selectedTenant}
            className="bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 hover:opacity-90 disabled:opacity-50"
          >
            {loading ? 'Calcul…' : 'Calculer'}
          </Button>
        </div>
        {error && <p className="mt-3 m-0 text-[#ef4444] text-[13px]">{error}</p>}
      </div>

      {/* Results */}
      {compute && (
        <div className="border border-[var(--border)] rounded-xl p-[22px] bg-[var(--card-bg)] mb-5">
          <p className="m-0 mb-4 text-[13px] text-[var(--text)]">
            {fmtDate(compute.date_debut)} — {fmtDate(compute.date_fin)}
          </p>

          {/* 3 stat cards */}
          <div className="grid grid-cols-3 gap-3 mb-6">
            {[
              { label: 'TVA collectée', value: compute.tva_collectee, color: '#2563eb' },
              { label: 'TVA déductible', value: compute.tva_deductible, color: '#10b981' },
              { label: compute.est_credit ? 'Crédit TVA' : 'TVA à payer', value: Math.abs(nette).toFixed(2), color: netteColor },
            ].map(({ label, value, color }) => (
              <div key={label} className="border border-[var(--border)] rounded-[10px] px-4 py-3.5 bg-[var(--bg)]">
                <p className="m-0 mb-1.5 text-[12px] text-[var(--text)]">{label}</p>
                <p className="m-0 text-[24px] font-bold font-mono tabular-nums" style={{ color }}>{fmt(value)}</p>
              </div>
            ))}
          </div>

          <TVALineTable lines={compute.lignes_collectee} label="TVA collectée (ventes) par taux" />
          <TVALineTable lines={compute.lignes_deductible} label="TVA déductible (achats) par taux" />

          <div className="flex justify-end gap-2.5 mt-2">
            <Button variant="outline" onClick={() => setCompute(null)}>Annuler</Button>
            <Button
              variant="outline"
              disabled={exporting}
              onClick={async () => {
                if (!selectedTenant) return
                setExporting(true)
                try { await exportCA3(selectedTenant.id, dateDebut, dateFin) }
                catch { setError("Erreur lors de l'export PDF") }
                finally { setExporting(false) }
              }}
              className="border-[#00348A] text-[#00348A] hover:bg-[#00348A]/5"
            >
              {exporting ? 'Génération…' : '↓ Télécharger CA3 PDF'}
            </Button>
            <Button
              disabled={saving}
              onClick={handleSave}
              className="bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 hover:opacity-90 disabled:opacity-50"
            >
              {saving ? 'Enregistrement…' : 'Valider la déclaration'}
            </Button>
          </div>
        </div>
      )}

      {/* History */}
      <div>
        <h2 className="text-[17px] font-semibold text-[var(--text-h)] m-0 mb-3.5 tracking-[-0.2px]">
          Historique des déclarations
        </h2>
        {historyLoading && <p className="text-[var(--text)] text-[14px]">Chargement…</p>}
        {!historyLoading && history.length === 0 && (
          <p className="text-[var(--text)] text-[14px] italic">Aucune déclaration enregistrée.</p>
        )}
        {history.length > 0 && (
          <div className="border border-[var(--border)] rounded-xl overflow-hidden">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-[rgba(107,99,117,0.04)]">
                  {['Période', 'TVA collectée', 'TVA déductible', 'Net', 'Statut', 'Actions'].map(h => (
                    <th key={h} className="px-3.5 py-2.5 text-left text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.07em] border-b border-[var(--border)]">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.map((d, i) => {
                  const net = Number(d.tva_nette)
                  const isCredit = net < 0
                  return (
                    <tr key={d.id} className={i < history.length - 1 ? 'border-b border-[var(--border)]' : ''}>
                      <td className="px-3.5 py-3 text-[13px] text-[var(--text-h)]">
                        {new Date(d.date_debut).toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' })}
                        {' – '}
                        {new Date(d.date_fin).toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' })}
                      </td>
                      <td className="px-3.5 py-3 text-[13px] font-mono tabular-nums text-blue-600">{fmt(d.tva_collectee)}</td>
                      <td className="px-3.5 py-3 text-[13px] font-mono tabular-nums text-emerald-600">{fmt(d.tva_deductible)}</td>
                      <td className={cn('px-3.5 py-3 text-[13px] font-mono tabular-nums font-semibold', isCredit ? 'text-emerald-600' : 'text-red-500')}>
                        {isCredit ? `Crédit ${fmt(Math.abs(net))}` : fmt(net)}
                      </td>
                      <td className="px-3.5 py-3"><StatutBadge statut={d.statut} /></td>
                      <td className="px-3.5 py-3">
                        <div className="flex gap-1.5 flex-wrap">
                          <button
                            onClick={async () => {
                              if (!selectedTenant) return
                              try { await exportCA3(selectedTenant.id, d.date_debut, d.date_fin) }
                              catch { alert('Erreur export PDF') }
                            }}
                            className="px-2.5 py-1 rounded-md border border-[#00348A] bg-transparent text-[#00348A] text-[12px] font-medium cursor-pointer hover:bg-[#00348A]/5"
                          >
                            ↓ CA3
                          </button>
                          {d.statut === 'brouillon' && (
                            <button
                              onClick={() => handleStatut(d.id, 'deposee')}
                              className="px-2.5 py-1 rounded-md border border-blue-500 bg-transparent text-blue-600 text-[12px] font-medium cursor-pointer hover:bg-blue-50"
                            >
                              Marquer déposée
                            </button>
                          )}
                          {d.statut === 'deposee' && (
                            <button
                              onClick={() => handleStatut(d.id, 'payee')}
                              className="px-2.5 py-1 rounded-md border border-emerald-500 bg-transparent text-emerald-600 text-[12px] font-medium cursor-pointer hover:bg-emerald-50"
                            >
                              Marquer payée
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
