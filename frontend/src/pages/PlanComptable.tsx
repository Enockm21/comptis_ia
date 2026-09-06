import { useEffect, useState } from 'react'
import { useTenant } from '../lib/TenantContext'
import { listPlanComptable, type Compte } from '../lib/plan-comptable'
import { Input } from '@/components/ui/input'

const CLASSES: Record<number, string> = {
  1: 'Capitaux',
  2: 'Immobilisations',
  3: 'Stocks',
  4: 'Tiers',
  5: 'Financiers',
  6: 'Charges',
  7: 'Produits',
}

export default function PlanComptable() {
  const { selected, loading } = useTenant()
  const [comptes, setComptes] = useState<Compte[]>([])
  const [search, setSearch] = useState('')
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!selected) return
    setFetching(true)
    setError(null)
    listPlanComptable(selected.id)
      .then(setComptes)
      .catch(e => setError(String(e)))
      .finally(() => setFetching(false))
  }, [selected])

  const filtered = comptes.filter(c =>
    c.numero.startsWith(search) ||
    c.libelle.toLowerCase().includes(search.toLowerCase())
  )

  const byClass = filtered.reduce<Record<number, Compte[]>>((acc, c) => {
    const k = Math.floor(c.classe)
    acc[k] = acc[k] ?? []
    acc[k].push(c)
    return acc
  }, {})

  return (
    <div className="px-9 py-8 max-w-[1100px]">
      <div className="flex items-center justify-between mb-7 flex-wrap gap-3">
        <div>
          <h1 className="text-[22px] font-bold text-[var(--text-h)] m-0 mb-1 tracking-[-0.4px]">Plan comptable</h1>
          <p className="text-[14px] text-[var(--text)] m-0">{selected?.name ?? '—'} · PCG français</p>
        </div>
        <Input
          type="text"
          placeholder="Rechercher un compte…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-[220px] bg-[var(--code-bg)] border-[var(--border)] text-[var(--text-h)]"
        />
      </div>

      {error && (
        <div className="bg-red-50 text-red-800 rounded-lg px-4 py-2.5 mb-4 text-[13px] dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      {(loading || fetching) && <p className="text-[var(--text)]">Chargement…</p>}
      {!loading && !selected && <p className="text-[var(--text)]">Aucun client sélectionné.</p>}

      {!loading && !fetching && selected && filtered.length === 0 && (
        <div className="py-12 px-8 text-center text-[var(--text)]">
          <p className="m-0 text-[15px]">Aucun compte</p>
          <p className="mt-1.5 m-0 text-[13px]">Le plan comptable sera importé automatiquement lors de la configuration.</p>
        </div>
      )}

      {!fetching && Object.entries(byClass).sort(([a], [b]) => Number(a) - Number(b)).map(([cls, list]) => (
        <div key={cls} className="mb-6">
          <div className="flex items-center gap-2.5 mb-2.5">
            <div className="w-7 h-7 rounded-[7px] bg-[#aa3bff22] border border-[#aa3bff44] flex items-center justify-center text-[12px] font-bold text-[#aa3bff] shrink-0">
              {cls}
            </div>
            <h2 className="text-[14px] font-semibold text-[var(--text-h)] m-0">
              Classe {cls} — {CLASSES[Number(cls)] ?? 'Autres'}
            </h2>
            <span className="text-[12px] text-[var(--text)]">({list.length})</span>
          </div>

          <div className="border border-[var(--border)] rounded-[10px] overflow-hidden">
            {list.map((c, i) => (
              <div
                key={c.id}
                className={`flex items-center gap-4 px-4 py-2.5 bg-[var(--card-bg)] ${i < list.length - 1 ? 'border-b border-[var(--border)]' : ''}`}
              >
                <code className="text-[12px] font-semibold text-[#aa3bff] bg-[#aa3bff12] px-1.5 py-0.5 rounded shrink-0 min-w-[60px] text-center">
                  {c.numero}
                </code>
                <span className="text-[13px] text-[var(--text-h)] flex-1">{c.libelle}</span>
              </div>
            ))}
          </div>
        </div>
      ))}

      {!fetching && filtered.length > 0 && (
        <p className="text-[12px] text-[var(--text)] mt-1">
          {filtered.length} compte{filtered.length > 1 ? 's' : ''}
        </p>
      )}
    </div>
  )
}
