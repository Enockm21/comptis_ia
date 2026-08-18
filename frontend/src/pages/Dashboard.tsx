import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTenant } from '../lib/TenantContext'
import { listEcritures, type Ecriture } from '../lib/ecritures'

function StatCard({ label, value, sub, color }: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div style={{
      background: 'var(--card-bg)',
      border: '1px solid var(--border)',
      borderRadius: 12,
      padding: '20px 24px',
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
    }}>
      <p style={{ fontSize: 13, color: 'var(--text)', margin: 0 }}>{label}</p>
      <p style={{ fontSize: 28, fontWeight: 700, color: color ?? 'var(--text-h)', margin: 0, letterSpacing: '-0.5px' }}>{value}</p>
      {sub && <p style={{ fontSize: 12, color: 'var(--text)', margin: 0 }}>{sub}</p>}
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
    return (
      <div style={{ padding: 40, color: 'var(--text)' }}>Chargement…</div>
    )
  }

  if (!selected) {
    return (
      <div style={{ padding: 40, color: 'var(--text)' }}>
        Aucun client sélectionné.
      </div>
    )
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
    <div style={{ padding: '32px 36px', maxWidth: 1100 }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-h)', margin: '0 0 4px', letterSpacing: '-0.4px' }}>
          Tableau de bord
        </h1>
        <p style={{ fontSize: 14, color: 'var(--text)', margin: 0 }}>
          {selected.name}
        </p>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16, marginBottom: 36 }}>
        <StatCard label="Rapprochées" value={total} color="#10b981" sub="transactions confirmées" />
        <StatCard label="À catégoriser" value={aCategoriser} color={aCategoriser > 0 ? '#f59e0b' : undefined} />
        <StatCard label="Catégorisées" value={categorisees} />
        <StatCard label="Validées" value={validees} />
        <StatCard label="Volume total" value={fmt.format(montantTotal)} />
      </div>

      {/* Quick actions */}
      <div style={{ marginBottom: 36 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-h)', margin: '0 0 14px' }}>Actions rapides</h2>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {[
            { label: 'Lancer un rapprochement', to: '/rapprochement', accent: true },
            { label: 'Catégoriser les écritures', to: '/categorisation', accent: false },
            { label: 'Voir toutes les écritures', to: '/ecritures', accent: false },
          ].map(({ label, to, accent }) => (
            <button
              key={to}
              onClick={() => navigate(to)}
              style={{
                padding: '9px 18px',
                borderRadius: 8,
                border: accent ? 'none' : '1px solid var(--border)',
                background: accent ? 'linear-gradient(135deg, #aa3bff, #7c3aed)' : 'var(--card-bg)',
                color: accent ? '#fff' : 'var(--text-h)',
                fontSize: 13,
                fontWeight: 500,
                cursor: 'pointer',
                boxShadow: accent ? '0 2px 8px rgba(170,59,255,0.25)' : 'none',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Recent écritures */}
      <div>
        <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-h)', margin: '0 0 14px' }}>Dernières écritures</h2>
        {recentEcritures.length === 0 ? (
          <p style={{ color: 'var(--text)', fontSize: 14 }}>Aucune écriture pour ce client.</p>
        ) : (
          <div style={{ border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
            {recentEcritures.map((e, i) => (
              <div
                key={e.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 16,
                  padding: '14px 20px',
                  borderBottom: i < recentEcritures.length - 1 ? '1px solid var(--border)' : 'none',
                  background: 'var(--card-bg)',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: 'var(--text-h)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {e.transaction_id}
                  </p>
                  <p style={{ margin: 0, fontSize: 12, color: 'var(--text)' }}>{new Date(e.date).toLocaleDateString('fr-FR')}</p>
                </div>
                <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-h)' }}>
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
  const map: Record<string, { label: string; bg: string; color: string }> = {
    a_categoriser: { label: 'À catégoriser', bg: '#fef3c7', color: '#92400e' },
    categorisee: { label: 'Catégorisée', bg: '#dbeafe', color: '#1e40af' },
    validee: { label: 'Validée', bg: '#d1fae5', color: '#065f46' },
  }
  const s = map[statut] ?? { label: statut, bg: 'var(--code-bg)', color: 'var(--text)' }
  return (
    <span style={{
      padding: '3px 9px',
      borderRadius: 20,
      fontSize: 11,
      fontWeight: 600,
      background: s.bg,
      color: s.color,
      flexShrink: 0,
    }}>
      {s.label}
    </span>
  )
}
