import { useState, useEffect, useCallback } from 'react'
import { useTenant } from '../lib/TenantContext'
import { computeTVA, createDeclaration, listDeclarations, updateStatut } from '../lib/tva'
import type { TVACompute, TVADeclaration, TVALine } from '../lib/tva'

const fmt = (v: string | number) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(Number(v))

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })

function periodDefaults() {
  const now = new Date()
  const y = now.getFullYear()
  const m = now.getMonth() // 0-based
  const debut = new Date(y, m - 1, 1)
  const fin = new Date(y, m, 0)
  return {
    debut: debut.toISOString().slice(0, 10),
    fin: fin.toISOString().slice(0, 10),
  }
}

const STATUT_STYLE: Record<string, { label: string; color: string; bg: string }> = {
  brouillon: { label: 'Brouillon', color: '#6b7280', bg: 'rgba(107,114,128,0.1)' },
  deposee: { label: 'Déposée', color: '#2563eb', bg: 'rgba(37,99,235,0.1)' },
  payee: { label: 'Payée', color: '#10b981', bg: 'rgba(16,185,129,0.1)' },
}

function Badge({ statut }: { statut: string }) {
  const s = STATUT_STYLE[statut] ?? STATUT_STYLE.brouillon
  return (
    <span style={{ padding: '3px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600, color: s.color, background: s.bg }}>
      {s.label}
    </span>
  )
}

function TVALineTable({ lines, label }: { lines: TVALine[]; label: string }) {
  if (lines.length === 0) return null
  return (
    <div style={{ marginBottom: 20 }}>
      <p style={{ margin: '0 0 8px', fontSize: 13, fontWeight: 600, color: 'var(--text-h)' }}>{label}</p>
      <div style={{ border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ background: 'rgba(107,99,117,0.04)' }}>
              {['Taux TVA', 'Base HT', 'Montant TVA', 'Nb factures'].map(h => (
                <th key={h} style={{ padding: '9px 14px', textAlign: h === 'Taux TVA' || h === 'Nb factures' ? 'left' : 'right', fontSize: 11, fontWeight: 600, color: 'var(--text)', textTransform: 'uppercase', letterSpacing: '0.07em', borderBottom: '1px solid var(--border)' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {lines.map((l, i) => (
              <tr key={i}>
                <td style={{ padding: '10px 14px', fontSize: 14, color: 'var(--text-h)', borderBottom: i < lines.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  {Number(l.taux).toFixed(1)}%
                </td>
                <td style={{ padding: '10px 14px', fontSize: 14, color: 'var(--text-h)', textAlign: 'right', fontFamily: 'monospace', borderBottom: i < lines.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  {fmt(l.base_ht)}
                </td>
                <td style={{ padding: '10px 14px', fontSize: 14, fontWeight: 600, color: 'var(--text-h)', textAlign: 'right', fontFamily: 'monospace', borderBottom: i < lines.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  {fmt(l.montant_tva)}
                </td>
                <td style={{ padding: '10px 14px', fontSize: 14, color: 'var(--text)', borderBottom: i < lines.length - 1 ? '1px solid var(--border)' : 'none' }}>
                  {l.nb_factures}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function TVA() {
  const { selectedTenant } = useTenant()
  const [dateDebut, setDateDebut] = useState(periodDefaults().debut)
  const [dateFin, setDateFin] = useState(periodDefaults().fin)
  const [compute, setCompute] = useState<TVACompute | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [history, setHistory] = useState<TVADeclaration[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadHistory = useCallback(async (tid: string) => {
    setHistoryLoading(true)
    try {
      setHistory(await listDeclarations(tid))
    } catch { /* ignore */ } finally {
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
    } catch { /* ignore */ }
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
    <div style={{ padding: '32px 36px', maxWidth: 760 }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '4px 12px', borderRadius: 20, background: 'var(--accent-bg)', border: '1px solid var(--accent-border)', marginBottom: 12 }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#aa3bff' }} />
          <span style={{ fontSize: 11, fontWeight: 600, color: '#aa3bff', textTransform: 'uppercase', letterSpacing: '0.08em' }}>CA3 — Réel normal</span>
        </div>
        <h1 style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-h)', margin: '0 0 6px', letterSpacing: '-0.4px' }}>
          Déclaration de TVA
        </h1>
        <p style={{ fontSize: 14, color: 'var(--text)', margin: 0 }}>
          Calculez et enregistrez vos déclarations CA3 à partir de vos factures PNICompta.
        </p>
      </div>

      {/* Period selector */}
      <div style={{ border: '1px solid var(--border)', borderRadius: 12, padding: '20px 22px', background: 'var(--card-bg)', marginBottom: 20 }}>
        <p style={{ margin: '0 0 12px', fontSize: 13, fontWeight: 600, color: 'var(--text-h)' }}>Période</p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
          {['Mois précédent', 'Il y a 2 mois', 'Il y a 3 mois'].map((label, i) => (
            <button key={label} onClick={() => setPreset(i + 1)} style={{ padding: '5px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text)', fontSize: 12, cursor: 'pointer', fontWeight: 500 }}>
              {label}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500 }}>Du</span>
            <input type="date" value={dateDebut} onChange={e => { setDateDebut(e.target.value); setCompute(null) }}
              style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text-h)', fontSize: 14 }} />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
            <span style={{ fontSize: 12, color: 'var(--text)', fontWeight: 500 }}>Au</span>
            <input type="date" value={dateFin} onChange={e => { setDateFin(e.target.value); setCompute(null) }}
              style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text-h)', fontSize: 14 }} />
          </label>
          <button onClick={handleCompute} disabled={loading || !selectedTenant}
            style={{ padding: '9px 20px', borderRadius: 9, border: 'none', background: loading ? 'var(--border)' : 'linear-gradient(135deg, #aa3bff, #7c3aed)', color: '#fff', fontSize: 14, fontWeight: 600, cursor: loading ? 'default' : 'pointer' }}>
            {loading ? 'Calcul…' : 'Calculer'}
          </button>
        </div>
        {error && <p style={{ margin: '12px 0 0', color: '#ef4444', fontSize: 13 }}>{error}</p>}
      </div>

      {/* Results */}
      {compute && (
        <div style={{ border: '1px solid var(--border)', borderRadius: 12, padding: '22px', background: 'var(--card-bg)', marginBottom: 20 }}>
          <p style={{ margin: '0 0 16px', fontSize: 13, color: 'var(--text)' }}>
            {fmtDate(compute.date_debut)} — {fmtDate(compute.date_fin)}
          </p>

          {/* 3 stat cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 22 }}>
            {[
              { label: 'TVA collectée', value: compute.tva_collectee, color: '#2563eb' },
              { label: 'TVA déductible', value: compute.tva_deductible, color: '#10b981' },
              { label: compute.est_credit ? 'Crédit TVA' : 'TVA à payer', value: Math.abs(nette).toFixed(2), color: netteColor },
            ].map(({ label, value, color }) => (
              <div key={label} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px', background: 'var(--bg)' }}>
                <p style={{ margin: '0 0 6px', fontSize: 12, color: 'var(--text)' }}>{label}</p>
                <p style={{ margin: 0, fontSize: 24, fontWeight: 700, color, fontFamily: 'monospace' }}>{fmt(value)}</p>
              </div>
            ))}
          </div>

          {/* Detail by rate */}
          <TVALineTable lines={compute.lignes_collectee} label="TVA collectée (ventes) par taux" />
          <TVALineTable lines={compute.lignes_deductible} label="TVA déductible (achats) par taux" />

          {/* Save button */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 8 }}>
            <button onClick={() => setCompute(null)} style={{ padding: '9px 18px', borderRadius: 9, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text)', fontSize: 14, fontWeight: 500, cursor: 'pointer' }}>
              Annuler
            </button>
            <button onClick={handleSave} disabled={saving}
              style={{ padding: '9px 20px', borderRadius: 9, border: 'none', background: 'linear-gradient(135deg, #aa3bff, #7c3aed)', color: '#fff', fontSize: 14, fontWeight: 600, cursor: saving ? 'default' : 'pointer' }}>
              {saving ? 'Enregistrement…' : 'Valider la déclaration'}
            </button>
          </div>
        </div>
      )}

      {/* History */}
      <div>
        <h2 style={{ fontSize: 17, fontWeight: 600, color: 'var(--text-h)', margin: '0 0 14px', letterSpacing: '-0.2px' }}>
          Historique des déclarations
        </h2>
        {historyLoading && <p style={{ color: 'var(--text)', fontSize: 14 }}>Chargement…</p>}
        {!historyLoading && history.length === 0 && (
          <p style={{ color: 'var(--text)', fontSize: 14, fontStyle: 'italic' }}>Aucune déclaration enregistrée.</p>
        )}
        {history.length > 0 && (
          <div style={{ border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'rgba(107,99,117,0.04)' }}>
                  {['Période', 'TVA collectée', 'TVA déductible', 'Net', 'Statut', 'Actions'].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 11, fontWeight: 600, color: 'var(--text)', textTransform: 'uppercase', letterSpacing: '0.07em', borderBottom: '1px solid var(--border)' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.map((d, i) => {
                  const net = Number(d.tva_nette)
                  const isCredit = net < 0
                  return (
                    <tr key={d.id} style={{ borderBottom: i < history.length - 1 ? '1px solid var(--border)' : 'none' }}>
                      <td style={{ padding: '12px 14px', fontSize: 13, color: 'var(--text-h)' }}>
                        {new Date(d.date_debut).toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' })}
                        {' – '}
                        {new Date(d.date_fin).toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' })}
                      </td>
                      <td style={{ padding: '12px 14px', fontSize: 13, fontFamily: 'monospace', color: '#2563eb' }}>{fmt(d.tva_collectee)}</td>
                      <td style={{ padding: '12px 14px', fontSize: 13, fontFamily: 'monospace', color: '#10b981' }}>{fmt(d.tva_deductible)}</td>
                      <td style={{ padding: '12px 14px', fontSize: 13, fontFamily: 'monospace', fontWeight: 600, color: isCredit ? '#10b981' : '#ef4444' }}>
                        {isCredit ? `Crédit ${fmt(Math.abs(net))}` : fmt(net)}
                      </td>
                      <td style={{ padding: '12px 14px' }}><Badge statut={d.statut} /></td>
                      <td style={{ padding: '12px 14px' }}>
                        <div style={{ display: 'flex', gap: 6 }}>
                          {d.statut === 'brouillon' && (
                            <button onClick={() => handleStatut(d.id, 'deposee')}
                              style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #2563eb', background: 'transparent', color: '#2563eb', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>
                              Marquer déposée
                            </button>
                          )}
                          {d.statut === 'deposee' && (
                            <button onClick={() => handleStatut(d.id, 'payee')}
                              style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #10b981', background: 'transparent', color: '#10b981', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}>
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
