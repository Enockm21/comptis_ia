import { useState, useRef } from 'react'
import { useTenant } from '../lib/TenantContext'
import { fetchWithAuth } from '../lib/http'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────────

interface PosteBalance {
  compte_num: string
  compte_lib: string
  total_debit: number
  total_credit: number
  solde_debiteur: number
  solde_crediteur: number
}

interface PosteBilan {
  classe: number
  libelle: string
  montant: number
  side: 'actif' | 'passif'
}

interface PosteResultat {
  classe: number
  libelle: string
  montant: number
  nature: 'charge' | 'produit'
}

interface ResultatResponse {
  postes: PosteResultat[]
  resultat_net: number
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const fmt = (v: number) =>
  new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', minimumFractionDigits: 2 }).format(v)

function monthBounds(offset = -1) {
  const now = new Date()
  const d = new Date(now.getFullYear(), now.getMonth() + offset, 1)
  const start = d.toISOString().slice(0, 10)
  const end = new Date(d.getFullYear(), d.getMonth() + 1, 0).toISOString().slice(0, 10)
  return { start, end }
}

const TABS = ['Balance', 'Bilan', 'Résultat'] as const
type Tab = typeof TABS[number]

// ── Component ──────────────────────────────────────────────────────────────────

export default function EtatsFinanciers() {
  const { selected: tenant } = useTenant()
  const [tab, setTab] = useState<Tab>('Balance')
  const { start: defStart, end: defEnd } = monthBounds(-1)
  const [dateDebut, setDateDebut] = useState(defStart)
  const [dateFin, setDateFin] = useState(defEnd)
  const [dateCloture, setDateCloture] = useState(defEnd)
  const [balance, setBalance] = useState<PosteBalance[] | null>(null)
  const [bilan, setBilan] = useState<PosteBilan[] | null>(null)
  const [resultat, setResultat] = useState<ResultatResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [msg, setMsg] = useState<{ text: string; error: boolean } | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  if (!tenant) return (
    <div className="p-8 text-[var(--text)] text-[14px]">Sélectionnez un dossier.</div>
  )

  const info = (text: string) => setMsg({ text, error: false })
  const err = (text: string) => setMsg({ text, error: true })

  // ── FEC import ──────────────────────────────────────────────────────────────
  const handleImport = async (file: File) => {
    setLoading(true); setMsg(null)
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetchWithAuth(
        `/comptabilite/fec/import?tenant_id=${tenant.id}`,
        { method: 'POST', body: formData }
      )
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      info(`${data.lignes_importees} lignes importées`)
    } catch (e: unknown) {
      err('Erreur import : ' + (e instanceof Error ? e.message : String(e)))
    } finally {
      setLoading(false)
    }
  }

  // ── FEC export ──────────────────────────────────────────────────────────────
  const handleExport = async () => {
    setLoading(true); setMsg(null)
    try {
      const params = new URLSearchParams({ tenant_id: tenant.id })
      if (dateDebut) params.set('date_debut', dateDebut)
      if (dateFin) params.set('date_fin', dateFin)
      const res = await fetchWithAuth(`/comptabilite/fec/export?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const cd = res.headers.get('Content-Disposition') ?? ''
      const match = cd.match(/filename="(.+)"/)
      const filename = match ? match[1] : 'FEC.txt'
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a'); a.href = url; a.download = filename; a.click()
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      err('Erreur export : ' + (e instanceof Error ? e.message : String(e)))
    } finally {
      setLoading(false)
    }
  }

  // ── Compute ─────────────────────────────────────────────────────────────────
  const handleBalance = async () => {
    setLoading(true); setMsg(null)
    try {
      const params = new URLSearchParams({ tenant_id: tenant.id })
      if (dateDebut) params.set('date_debut', dateDebut)
      if (dateFin) params.set('date_fin', dateFin)
      const res = await fetchWithAuth(`/comptabilite/balance?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setBalance(await res.json())
    } catch (e: unknown) {
      err('Erreur : ' + (e instanceof Error ? e.message : String(e)))
    } finally {
      setLoading(false)
    }
  }

  const handleBilan = async () => {
    setLoading(true); setMsg(null)
    try {
      const params = new URLSearchParams({ tenant_id: tenant.id, date_cloture: dateCloture })
      const res = await fetchWithAuth(`/comptabilite/bilan?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setBilan(await res.json())
    } catch (e: unknown) {
      err('Erreur : ' + (e instanceof Error ? e.message : String(e)))
    } finally {
      setLoading(false)
    }
  }

  const handleResultat = async () => {
    setLoading(true); setMsg(null)
    try {
      const params = new URLSearchParams({ tenant_id: tenant.id, date_debut: dateDebut, date_fin: dateFin })
      const res = await fetchWithAuth(`/comptabilite/resultat?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setResultat(await res.json())
    } catch (e: unknown) {
      err('Erreur : ' + (e instanceof Error ? e.message : String(e)))
    } finally {
      setLoading(false)
    }
  }

  const actif = bilan?.filter(p => p.side === 'actif') ?? []
  const passif = bilan?.filter(p => p.side === 'passif') ?? []
  const totalActif = actif.reduce((s, p) => s + p.montant, 0)
  const totalPassif = passif.reduce((s, p) => s + p.montant, 0)

  return (
    <div className="px-8 py-7 max-w-[1100px]">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-[22px] font-bold text-[var(--text-h)] m-0 mb-1 tracking-[-0.3px]">
          États financiers
        </h1>
        <p className="text-[14px] text-[var(--text)] m-0">
          FEC import/export · Balance · Bilan · Compte de résultat
        </p>
      </div>

      {/* FEC actions bar */}
      <div className="flex flex-wrap gap-3 mb-6 p-4 bg-[var(--card-bg)] border border-[var(--border)] rounded-xl">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <span className="text-[12px] font-semibold text-[var(--text)] uppercase tracking-[0.05em] shrink-0">FEC</span>
          <input
            ref={fileRef}
            type="file"
            accept=".txt,.csv"
            className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) { handleImport(f); e.target.value = '' } }}
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() => fileRef.current?.click()}
            disabled={loading}
            className="text-[12px]"
          >
            Importer FEC
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={handleExport}
            disabled={loading}
            className="text-[12px]"
          >
            ↓ Exporter FEC
          </Button>
        </div>
        {msg && (
          <p className={cn('text-[12px] self-center', msg.error ? 'text-red-500' : 'text-emerald-600')}>
            {msg.text}
          </p>
        )}
      </div>

      {/* Date controls */}
      <div className="flex flex-wrap gap-3 mb-5 items-end">
        {tab !== 'Bilan' ? (
          <>
            <div>
              <label className="block text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em] mb-1">Début</label>
              <Input type="date" value={dateDebut} onChange={e => setDateDebut(e.target.value)}
                className="text-[13px] bg-[var(--bg)] border-[var(--border)] text-[var(--text-h)] w-[160px]" />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em] mb-1">Fin</label>
              <Input type="date" value={dateFin} onChange={e => setDateFin(e.target.value)}
                className="text-[13px] bg-[var(--bg)] border-[var(--border)] text-[var(--text-h)] w-[160px]" />
            </div>
          </>
        ) : (
          <div>
            <label className="block text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em] mb-1">Date de clôture</label>
            <Input type="date" value={dateCloture} onChange={e => setDateCloture(e.target.value)}
              className="text-[13px] bg-[var(--bg)] border-[var(--border)] text-[var(--text-h)] w-[180px]" />
          </div>
        )}
        <Button
          onClick={tab === 'Balance' ? handleBalance : tab === 'Bilan' ? handleBilan : handleResultat}
          disabled={loading}
          className="bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 hover:opacity-90 disabled:opacity-60"
          size="sm"
        >
          {loading ? '…' : 'Calculer'}
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-5 border-b border-[var(--border)]">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cn(
              'px-4 py-2 text-[13px] font-medium border-b-2 -mb-px transition-colors',
              tab === t
                ? 'border-[var(--accent)] text-[var(--accent)]'
                : 'border-transparent text-[var(--text)] hover:text-[var(--text-h)]'
            )}
          >
            {t}
          </button>
        ))}
      </div>

      {/* ── Balance ────────────────────────────────────────────────────────── */}
      {tab === 'Balance' && (
        balance ? (
          <div className="overflow-x-auto rounded-xl border border-[var(--border)]">
            <table className="w-full text-[13px] border-collapse">
              <thead>
                <tr className="bg-[var(--code-bg)] text-[var(--text)] text-[11px] uppercase tracking-[0.05em]">
                  <th className="text-left px-4 py-3 font-semibold">Compte</th>
                  <th className="text-left px-4 py-3 font-semibold">Libellé</th>
                  <th className="text-right px-4 py-3 font-semibold tabular-nums">Débit</th>
                  <th className="text-right px-4 py-3 font-semibold tabular-nums">Crédit</th>
                  <th className="text-right px-4 py-3 font-semibold tabular-nums">Solde D</th>
                  <th className="text-right px-4 py-3 font-semibold tabular-nums">Solde C</th>
                </tr>
              </thead>
              <tbody>
                {balance.map((p, i) => (
                  <tr key={p.compte_num} className={cn(
                    'border-t border-[var(--border)]',
                    i % 2 === 0 ? 'bg-[var(--bg)]' : 'bg-[var(--card-bg)]'
                  )}>
                    <td className="px-4 py-2.5 font-mono text-[var(--text-h)]">{p.compte_num}</td>
                    <td className="px-4 py-2.5 text-[var(--text)]">{p.compte_lib}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-[var(--text-h)]">{fmt(p.total_debit)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-[var(--text-h)]">{fmt(p.total_credit)}</td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-[var(--text-h)]">
                      {p.solde_debiteur > 0 ? fmt(p.solde_debiteur) : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-right tabular-nums text-[var(--text-h)]">
                      {p.solde_crediteur > 0 ? fmt(p.solde_crediteur) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-[var(--border)] bg-[var(--code-bg)] font-semibold">
                  <td colSpan={2} className="px-4 py-3 text-[var(--text-h)]">Total</td>
                  <td className="px-4 py-3 text-right tabular-nums text-[var(--text-h)]">
                    {fmt(balance.reduce((s, p) => s + p.total_debit, 0))}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-[var(--text-h)]">
                    {fmt(balance.reduce((s, p) => s + p.total_credit, 0))}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-[var(--text-h)]">
                    {fmt(balance.reduce((s, p) => s + p.solde_debiteur, 0))}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-[var(--text-h)]">
                    {fmt(balance.reduce((s, p) => s + p.solde_crediteur, 0))}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        ) : (
          <Empty label="Choisissez une période et cliquez Calculer." />
        )
      )}

      {/* ── Bilan ──────────────────────────────────────────────────────────── */}
      {tab === 'Bilan' && (
        bilan ? (
          <div className="grid grid-cols-2 gap-4">
            <BilanColumn title="ACTIF" postes={actif} total={totalActif} accentColor="text-blue-600 dark:text-blue-400" />
            <BilanColumn title="PASSIF" postes={passif} total={totalPassif} accentColor="text-violet-600 dark:text-violet-400" />
          </div>
        ) : (
          <Empty label="Choisissez une date de clôture et cliquez Calculer." />
        )
      )}

      {/* ── Résultat ───────────────────────────────────────────────────────── */}
      {tab === 'Résultat' && (
        resultat ? (
          <div className="space-y-4">
            {resultat.postes.map(p => (
              <div key={p.classe} className="border border-[var(--border)] rounded-xl overflow-hidden">
                <div className={cn(
                  'px-5 py-3 text-[12px] font-bold uppercase tracking-[0.06em]',
                  p.nature === 'charge'
                    ? 'bg-red-50 text-red-700 dark:bg-red-900/10 dark:text-red-400'
                    : 'bg-emerald-50 text-emerald-700 dark:bg-emerald-900/10 dark:text-emerald-400'
                )}>
                  {p.nature === 'charge' ? '↓' : '↑'} {p.libelle} (classe {p.classe})
                </div>
                <div className="px-5 py-4 bg-[var(--card-bg)]">
                  <p className={cn(
                    'text-[28px] font-bold tabular-nums m-0',
                    p.nature === 'charge' ? 'text-red-500' : 'text-emerald-600'
                  )}>
                    {fmt(p.montant)}
                  </p>
                </div>
              </div>
            ))}

            <div className={cn(
              'border-2 rounded-xl p-5',
              resultat.resultat_net >= 0
                ? 'border-emerald-400 bg-emerald-50 dark:bg-emerald-900/10'
                : 'border-red-400 bg-red-50 dark:bg-red-900/10'
            )}>
              <p className="text-[12px] font-bold uppercase tracking-[0.06em] text-[var(--text)] m-0 mb-1">
                Résultat net
              </p>
              <p className={cn(
                'text-[36px] font-bold tabular-nums m-0',
                resultat.resultat_net >= 0 ? 'text-emerald-600' : 'text-red-500'
              )}>
                {resultat.resultat_net >= 0 ? '+' : ''}{fmt(resultat.resultat_net)}
              </p>
            </div>
          </div>
        ) : (
          <Empty label="Choisissez une période et cliquez Calculer." />
        )
      )}
    </div>
  )
}

function Empty({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-[var(--text)] text-[14px] gap-2">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" opacity={0.3}>
        <path d="M9 17H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-4M12 12v5M9 19h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
      {label}
    </div>
  )
}

function BilanColumn({
  title, postes, total, accentColor
}: {
  title: string; postes: PosteBilan[]; total: number; accentColor: string
}) {
  return (
    <div className="border border-[var(--border)] rounded-xl overflow-hidden">
      <div className="px-5 py-3 bg-[var(--code-bg)] border-b border-[var(--border)]">
        <p className="text-[12px] font-bold uppercase tracking-[0.08em] text-[var(--text)] m-0">{title}</p>
      </div>
      <div className="divide-y divide-[var(--border)]">
        {postes.map(p => (
          <div key={p.classe} className="flex items-center justify-between px-5 py-3 bg-[var(--card-bg)]">
            <div>
              <p className="m-0 text-[13px] font-medium text-[var(--text-h)]">{p.libelle}</p>
              <p className="m-0 text-[11px] text-[var(--text)]">Classe {p.classe}</p>
            </div>
            <p className={cn('m-0 text-[15px] font-bold tabular-nums', accentColor)}>
              {fmt(p.montant)}
            </p>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between px-5 py-3 border-t-2 border-[var(--border)] bg-[var(--code-bg)]">
        <p className="m-0 text-[12px] font-bold uppercase tracking-[0.05em] text-[var(--text-h)]">Total {title}</p>
        <p className={cn('m-0 text-[16px] font-bold tabular-nums', accentColor)}>{fmt(total)}</p>
      </div>
    </div>
  )
}
