import { useEffect, useRef, useState } from 'react'
import { useTenant } from '../lib/TenantContext'
import { listEcritures, type Ecriture } from '../lib/ecritures'
import { fetchWithAuth } from '../lib/http'
import { cn } from '@/lib/utils'

const fmt = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })

const STATUTS = [
  { value: '', label: 'Toutes' },
  { value: 'a_categoriser', label: 'À catégoriser' },
  { value: 'categorisee', label: 'Catégorisées' },
  { value: 'validee', label: 'Validées' },
]

function StatutBadge({ statut }: { statut: Ecriture['statut'] }) {
  const map: Record<string, { label: string; classes: string }> = {
    a_categoriser: { label: 'À catégoriser', classes: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400' },
    categorisee:   { label: 'Catégorisée',   classes: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400' },
    validee:       { label: 'Validée',        classes: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400' },
  }
  const s = map[statut] ?? { label: statut, classes: 'bg-[var(--code-bg)] text-[var(--text)]' }
  return (
    <span className={cn('px-2.5 py-0.5 rounded-full text-[11px] font-semibold whitespace-nowrap', s.classes)}>
      {s.label}
    </span>
  )
}

export default function Ecritures() {
  const { selected, loading } = useTenant()
  const [ecritures, setEcritures] = useState<Ecriture[]>([])
  const [statut, setStatut] = useState('')
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [importing, setImporting] = useState(false)
  const [importMsg, setImportMsg] = useState<string | null>(null)
  const csvRef = useRef<HTMLInputElement>(null)

  const handleCSV = async (file: File) => {
    if (!selected) return
    setImporting(true); setImportMsg(null)
    try {
      const fd = new FormData(); fd.append('file', file)
      const r = await fetchWithAuth(`/ecritures/import-csv?tenant_id=${selected.id}`, { method: 'POST', body: fd })
      const data = await r.json()
      if (!r.ok) throw new Error(data.detail || 'Erreur')
      setImportMsg(`${data.importees} écritures importées${data.ignorees ? `, ${data.ignorees} ignorées (doublons)` : ''}.`)
      // Refresh list
      listEcritures(selected.id, statut || undefined).then(setEcritures).catch(() => {})
    } catch (e: unknown) {
      setImportMsg(`Erreur : ${e instanceof Error ? e.message : 'inconnue'}`)
    } finally { setImporting(false) }
  }

  useEffect(() => {
    if (!selected) return
    setFetching(true)
    setError(null)
    listEcritures(selected.id, statut || undefined)
      .then(setEcritures)
      .catch(e => setError(String(e)))
      .finally(() => setFetching(false))
  }, [selected, statut])

  return (
    <div className="px-9 py-8 max-w-[1100px]">
      <div className="flex items-center justify-between mb-7 flex-wrap gap-3">
        <div>
          <h1 className="text-[22px] font-bold text-[var(--text-h)] m-0 mb-1 tracking-[-0.4px]">Écritures</h1>
          <p className="text-[14px] text-[var(--text)] m-0">{selected?.name ?? '—'}</p>
        </div>

        {/* Import CSV */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => csvRef.current?.click()}
            disabled={importing}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg border border-[var(--border)] text-[13px] font-medium text-[var(--text)] hover:bg-[var(--code-bg)] transition-colors disabled:opacity-50"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"
                stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            {importing ? 'Import…' : 'Import CSV'}
          </button>
          <input ref={csvRef} type="file" accept=".csv,.txt" className="hidden"
            onChange={e => { if (e.target.files?.[0]) handleCSV(e.target.files[0]); e.target.value = '' }} />
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1 bg-[var(--code-bg)] p-1 rounded-[10px] border border-[var(--border)]">
          {STATUTS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setStatut(value)}
              className={cn(
                'px-3.5 py-1.5 rounded-[7px] border-none text-[13px] cursor-pointer transition-[background] duration-100',
                statut === value
                  ? 'bg-[var(--bg)] text-[var(--text-h)] font-semibold shadow-sm'
                  : 'bg-transparent text-[var(--text)] font-normal'
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading && <p className="text-[var(--text)]">Chargement…</p>}
      {!loading && !selected && <p className="text-[var(--text)]">Aucun client sélectionné.</p>}
      {error && (
        <div className="bg-red-50 text-red-800 rounded-lg px-4 py-2.5 mb-4 text-[13px] dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}
      {importMsg && (
        <div className={cn('rounded-lg px-4 py-2.5 mb-4 text-[13px]',
          importMsg.startsWith('Erreur')
            ? 'bg-red-50 text-red-800 dark:bg-red-900/20 dark:text-red-400'
            : 'bg-emerald-50 text-emerald-800 dark:bg-emerald-900/20 dark:text-emerald-400'
        )}>
          {importMsg}
        </div>
      )}

      {!loading && selected && (
        <div className="border border-[var(--border)] rounded-xl overflow-auto">
          {fetching ? (
            <div className="p-8 text-center text-[var(--text)]">Chargement…</div>
          ) : ecritures.length === 0 ? (
            <div className="py-12 px-8 text-center text-[var(--text)]">
              <p className="m-0 text-[15px]">Aucune écriture</p>
              <p className="mt-1.5 m-0 text-[13px]">Lancez un rapprochement pour en créer.</p>
            </div>
          ) : (
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-[var(--border)] bg-[var(--code-bg)]">
                  {['Date', 'Transaction', 'Facture', 'Montant', 'Compte', 'Statut'].map(h => (
                    <th key={h} className="px-4 py-3 text-left font-semibold text-[var(--text)] text-[11px] uppercase tracking-[0.05em]">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ecritures.map((e, i) => (
                  <tr
                    key={e.id}
                    className={cn('bg-[var(--card-bg)]', i < ecritures.length - 1 && 'border-b border-[var(--border)]')}
                  >
                    <td className="px-4 py-3 text-[var(--text)] whitespace-nowrap">
                      {new Date(e.date).toLocaleDateString('fr-FR')}
                    </td>
                    <td className="px-4 py-3 text-[var(--text-h)] max-w-[200px] overflow-hidden text-ellipsis whitespace-nowrap">
                      {e.transaction_id}
                    </td>
                    <td className="px-4 py-3 text-[var(--text)] max-w-[160px] overflow-hidden text-ellipsis whitespace-nowrap">
                      {e.facture_id ?? '—'}
                    </td>
                    <td className="px-4 py-3 text-[var(--text-h)] font-semibold whitespace-nowrap tabular-nums">
                      {fmt.format(parseFloat(e.montant))}
                    </td>
                    <td className="px-4 py-3 text-[var(--text)] font-mono text-[11px]">
                      {e.compte_id ?? <span className="opacity-40">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <StatutBadge statut={e.statut} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {!fetching && ecritures.length > 0 && (
        <p className="text-[12px] text-[var(--text)] mt-2.5">
          {ecritures.length} écriture{ecritures.length > 1 ? 's' : ''}
        </p>
      )}
    </div>
  )
}
