import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTenant } from '../lib/TenantContext'
import { listEcritures, type Ecriture } from '../lib/ecritures'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-5 flex flex-col gap-1.5">
      <p className="text-[13px] text-[var(--text)] m-0">{label}</p>
      <p className={cn('text-[28px] font-bold m-0 tracking-[-0.5px]', color ? '' : 'text-[var(--text-h)]')}
         style={color ? { color } : undefined}>
        {value}
      </p>
      {sub && <p className="text-[12px] text-[var(--text)] m-0">{sub}</p>}
    </div>
  )
}

const fmt = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })

export default function Dashboard() {
  const { selected, loading } = useTenant()
  const navigate = useNavigate()
  const [ecritures, setEcritures] = useState<Ecriture[]>([])
  const [fetching, setFetching] = useState(false)

  useEffect(() => {
    if (!selected) return
    setFetching(true)
    listEcritures(selected.id)
      .then(setEcritures)
      .catch(() => {})
      .finally(() => setFetching(false))
  }, [selected])

  if (loading || fetching) {
    return <div className="p-10 text-[var(--text)]">Chargement…</div>
  }

  if (!selected) {
    return <div className="p-10 text-[var(--text)]">Aucun client sélectionné.</div>
  }

  const total = ecritures.length
  const aCategoriser = ecritures.filter(e => e.statut === 'a_categoriser').length
  const categorisees = ecritures.filter(e => e.statut === 'categorisee').length
  const validees = ecritures.filter(e => e.statut === 'validee').length
  const montantTotal = ecritures.reduce((s, e) => s + parseFloat(e.montant), 0)

  const recentEcritures = [...ecritures]
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    .slice(0, 5)

  return (
    <div className="px-9 py-8 max-w-[1100px]">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-[22px] font-bold text-[var(--text-h)] m-0 mb-1 tracking-[-0.4px]">
          Tableau de bord
        </h1>
        <p className="text-[14px] text-[var(--text)] m-0">{selected.name}</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4 mb-9">
        <StatCard label="Rapprochées" value={total} color="#10b981" sub="transactions confirmées" />
        <StatCard label="À catégoriser" value={aCategoriser} color={aCategoriser > 0 ? '#f59e0b' : undefined} />
        <StatCard label="Catégorisées" value={categorisees} />
        <StatCard label="Validées" value={validees} />
        <StatCard label="Volume total" value={fmt.format(montantTotal)} />
      </div>

      {/* Quick actions */}
      <div className="mb-9">
        <h2 className="text-[15px] font-semibold text-[var(--text-h)] m-0 mb-3.5">Actions rapides</h2>
        <div className="flex gap-2.5 flex-wrap">
          <Button
            onClick={() => navigate('/rapprochement')}
            className="bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 shadow-[0_2px_8px_rgba(170,59,255,0.25)] hover:opacity-90"
          >
            Lancer un rapprochement
          </Button>
          <Button variant="outline" onClick={() => navigate('/categorisation')}>
            Catégoriser les écritures
          </Button>
          <Button variant="outline" onClick={() => navigate('/ecritures')}>
            Voir toutes les écritures
          </Button>
        </div>
      </div>

      {/* Recent écritures */}
      <div>
        <h2 className="text-[15px] font-semibold text-[var(--text-h)] m-0 mb-3.5">Dernières écritures</h2>
        {recentEcritures.length === 0 ? (
          <p className="text-[var(--text)] text-[14px]">Aucune écriture pour ce client.</p>
        ) : (
          <div className="border border-[var(--border)] rounded-xl overflow-hidden">
            {recentEcritures.map((e, i) => (
              <div
                key={e.id}
                className={cn(
                  'flex items-center gap-4 px-5 py-3.5 bg-[var(--card-bg)]',
                  i < recentEcritures.length - 1 && 'border-b border-[var(--border)]'
                )}
              >
                <div className="flex-1 min-w-0">
                  <p className="m-0 text-[13px] font-medium text-[var(--text-h)] truncate">
                    {e.transaction_id}
                  </p>
                  <p className="m-0 text-[12px] text-[var(--text)]">
                    {new Date(e.date).toLocaleDateString('fr-FR')}
                  </p>
                </div>
                <span className="text-[14px] font-semibold text-[var(--text-h)]">
                  {fmt.format(parseFloat(e.montant))}
                </span>
                <StatutBadge statut={e.statut} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function StatutBadge({ statut }: { statut: Ecriture['statut'] }) {
  const map: Record<string, { label: string; classes: string }> = {
    a_categoriser: { label: 'À catégoriser', classes: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400' },
    categorisee:   { label: 'Catégorisée',   classes: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400' },
    validee:       { label: 'Validée',        classes: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400' },
  }
  const s = map[statut] ?? { label: statut, classes: 'bg-[var(--code-bg)] text-[var(--text)]' }
  return (
    <span className={cn('px-2.5 py-0.5 rounded-full text-[11px] font-semibold shrink-0', s.classes)}>
      {s.label}
    </span>
  )
}
