import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTenant } from '../lib/TenantContext'
import { listEcritures, type Ecriture } from '../lib/ecritures'
import { fetchWithAuth } from '../lib/http'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────────

interface MonthKPI { mois: string; charges: number; produits: number; resultat: number }
interface DashboardKPI {
  charges_mois: number
  produits_mois: number
  resultat_mois: number
  tresorerie: number
  resultat_ytd: number
  monthly: MonthKPI[]
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const fmt = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 })
const fmtFull = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })
const moisLabel = (s: string) => {
  const [y, m] = s.split('-')
  return new Date(parseInt(y), parseInt(m) - 1, 1).toLocaleString('fr-FR', { month: 'short' })
}

// ── Sparkline ──────────────────────────────────────────────────────────────────

function Sparkline({ data }: { data: MonthKPI[] }) {
  if (!data.length) return null
  const W = 240, H = 56, PAD = 4
  const maxV = Math.max(...data.map(d => Math.max(d.charges, d.produits)), 1)
  const barW = (W - PAD * 2) / data.length
  const scale = (v: number) => H - PAD - ((v / maxV) * (H - PAD * 2))

  return (
    <svg width={W} height={H} className="overflow-visible">
      {data.map((d, i) => {
        const x = PAD + i * barW
        const yC = scale(d.charges)
        const yP = scale(d.produits)
        return (
          <g key={d.mois}>
            <rect x={x + 2} y={yC} width={barW / 2 - 3} height={H - PAD - yC}
              fill="#ef4444" opacity={0.7} rx={2} />
            <rect x={x + barW / 2 + 1} y={yP} width={barW / 2 - 3} height={H - PAD - yP}
              fill="#10b981" opacity={0.7} rx={2} />
          </g>
        )
      })}
    </svg>
  )
}

// ── KPI Card ───────────────────────────────────────────────────────────────────

function KpiCard({
  label, value, sub, positive, neutral
}: {
  label: string; value: string; sub?: string; positive?: boolean; neutral?: boolean
}) {
  const color = neutral ? 'text-[var(--text-h)]'
    : positive ? 'text-emerald-600 dark:text-emerald-400'
    : 'text-red-500 dark:text-red-400'
  return (
    <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl p-5 flex flex-col gap-1">
      <p className="text-[12px] font-semibold text-[var(--text)] uppercase tracking-[0.05em] m-0">{label}</p>
      <p className={cn('text-[26px] font-bold m-0 tracking-[-0.5px] tabular-nums', color)}>{value}</p>
      {sub && <p className="text-[12px] text-[var(--text)] m-0">{sub}</p>}
    </div>
  )
}

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

// ── Dashboard ──────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { selected, loading } = useTenant()
  const navigate = useNavigate()
  const [ecritures, setEcritures] = useState<Ecriture[]>([])
  const [kpi, setKpi] = useState<DashboardKPI | null>(null)
  const [fetching, setFetching] = useState(false)

  useEffect(() => {
    if (!selected) return
    setFetching(true)
    Promise.all([
      listEcritures(selected.id).catch(() => [] as Ecriture[]),
      fetchWithAuth(`/comptabilite/kpi?tenant_id=${selected.id}`)
        .then(r => r.ok ? r.json() as Promise<DashboardKPI> : null)
        .catch(() => null),
    ]).then(([ecr, k]) => {
      setEcritures(ecr)
      setKpi(k)
    }).finally(() => setFetching(false))
  }, [selected])

  if (loading || fetching) return <div className="p-10 text-[var(--text)]">Chargement…</div>
  if (!selected) return <div className="p-10 text-[var(--text)]">Aucun client sélectionné.</div>

  const aCategoriser = ecritures.filter(e => e.statut === 'a_categoriser').length
  const recentEcritures = [...ecritures]
    .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime())
    .slice(0, 5)

  const hasKpi = kpi !== null
  const resultatPositif = hasKpi && kpi!.resultat_mois >= 0

  return (
    <div className="px-9 py-8 max-w-[1100px]">
      {/* Header */}
      <div className="mb-7">
        <h1 className="text-[22px] font-bold text-[var(--text-h)] m-0 mb-1 tracking-[-0.4px]">
          Tableau de bord
        </h1>
        <p className="text-[14px] text-[var(--text)] m-0">{selected.name}</p>
      </div>

      {/* Financial KPIs — visible only when grand livre has data */}
      {hasKpi && (
        <>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(190px,1fr))] gap-4 mb-5">
            <KpiCard
              label="Résultat du mois"
              value={fmt.format(kpi!.resultat_mois)}
              positive={resultatPositif}
              sub={resultatPositif ? 'Bénéfice' : 'Déficit'}
            />
            <KpiCard
              label="Charges (mois)"
              value={fmt.format(kpi!.charges_mois)}
              positive={false}
              neutral={kpi!.charges_mois === 0}
              sub="Classe 6"
            />
            <KpiCard
              label="Produits (mois)"
              value={fmt.format(kpi!.produits_mois)}
              positive={kpi!.produits_mois > 0}
              neutral={kpi!.produits_mois === 0}
              sub="Classe 7"
            />
            <KpiCard
              label="Trésorerie"
              value={fmt.format(kpi!.tresorerie)}
              positive={kpi!.tresorerie >= 0}
              neutral={kpi!.tresorerie === 0}
              sub="Classe 5"
            />
            <KpiCard
              label="Résultat YTD"
              value={fmt.format(kpi!.resultat_ytd)}
              positive={kpi!.resultat_ytd >= 0}
              neutral={kpi!.resultat_ytd === 0}
              sub="Depuis janvier"
            />
          </div>

          {/* Sparkline charges vs produits (6 mois) */}
          {kpi!.monthly.some(m => m.charges > 0 || m.produits > 0) && (
            <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl px-5 py-4 mb-7">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[12px] font-semibold text-[var(--text)] uppercase tracking-[0.05em] m-0 mb-3">
                    Charges vs Produits — 6 mois
                  </p>
                  <Sparkline data={kpi!.monthly} />
                  <div className="flex gap-4 mt-2">
                    {kpi!.monthly.map(m => (
                      <span key={m.mois} className="text-[10px] text-[var(--text)] w-[30px] text-center">
                        {moisLabel(m.mois)}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex flex-col gap-1.5 shrink-0 mt-1">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-sm bg-red-400 opacity-70 shrink-0" />
                    <span className="text-[12px] text-[var(--text)]">Charges</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-sm bg-emerald-500 opacity-70 shrink-0" />
                    <span className="text-[12px] text-[var(--text)]">Produits</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* Workflow stats (écritures) */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-4 mb-7">
        <StatCard label="Écritures totales" value={ecritures.length} />
        <StatCard
          label="À catégoriser"
          value={aCategoriser}
          color={aCategoriser > 0 ? '#f59e0b' : undefined}
          sub={aCategoriser > 0 ? 'Action requise' : undefined}
        />
        <StatCard label="Catégorisées" value={ecritures.filter(e => e.statut === 'categorisee').length} />
        <StatCard label="Validées" value={ecritures.filter(e => e.statut === 'validee').length} />
      </div>

      {/* Quick actions */}
      <div className="mb-7">
        <h2 className="text-[15px] font-semibold text-[var(--text-h)] m-0 mb-3.5">Actions rapides</h2>
        <div className="flex gap-2.5 flex-wrap">
          <Button
            onClick={() => navigate('/rapprochement')}
            className="bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 shadow-[0_2px_8px_rgba(170,59,255,0.25)] hover:opacity-90"
          >
            Lancer un rapprochement
          </Button>
          <Button variant="outline" onClick={() => navigate('/etats-financiers')}>
            États financiers
          </Button>
          {aCategoriser > 0 && (
            <Button variant="outline" onClick={() => navigate('/categorisation')}>
              Catégoriser ({aCategoriser})
            </Button>
          )}
          <Button variant="outline" onClick={() => navigate('/ecritures')}>
            Voir les écritures
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
                  <p className="m-0 text-[13px] font-medium text-[var(--text-h)] truncate">{e.transaction_id}</p>
                  <p className="m-0 text-[12px] text-[var(--text)]">{new Date(e.date).toLocaleDateString('fr-FR')}</p>
                </div>
                <span className="text-[14px] font-semibold text-[var(--text-h)]">
                  {fmtFull.format(parseFloat(e.montant))}
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
