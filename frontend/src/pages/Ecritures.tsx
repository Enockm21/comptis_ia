import { useEffect, useState } from 'react'
import { useTenant } from '../lib/TenantContext'
import { listEcritures, type Ecriture } from '../lib/ecritures'
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
