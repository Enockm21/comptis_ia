import { useEffect, useState } from 'react'
import { useTenant } from '../lib/TenantContext'
import { listPlanComptable, type Compte } from '../lib/plan-comptable'

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
    <div style={{ padding: '32px 36px', maxWidth: 1100 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-h)', margin: '0 0 4px', letterSpacing: '-0.4px' }}>Plan comptable</h1>
          <p style={{ fontSize: 14, color: 'var(--text)', margin: 0 }}>
            {selected?.name ?? '—'} · PCG français
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <input
            type="text"
            placeholder="Rechercher un compte…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              padding: '8px 14px',
              borderRadius: 8,
              border: '1px solid var(--border)',
              background: 'var(--code-bg)',
              color: 'var(--text-h)',
              fontSize: 13,
              outline: 'none',
              width: 220,
            }}
          />
        </div>
      </div>

      {error && (
        <div style={{ background: '#fee2e2', color: '#991b1b', borderRadius: 8, padding: '10px 16px', marginBottom: 16, fontSize: 13 }}>
          {error}
        </div>
      )}

      {(loading || fetching) && <p style={{ color: 'var(--text)' }}>Chargement…</p>}
      {!loading && !selected && <p style={{ color: 'var(--text)' }}>Aucun client sélectionné.</p>}

      {!loading && !fetching && selected && filtered.length === 0 && (
        <div style={{ padding: 48, textAlign: 'center', color: 'var(--text)' }}>
          <p style={{ margin: 0, fontSize: 15 }}>Aucun compte</p>
          <p style={{ margin: '6px 0 0', fontSize: 13 }}>Le plan comptable sera importé automatiquement lors de la configuration.</p>
        </div>
      )}

      {!fetching && Object.entries(byClass).sort(([a], [b]) => Number(a) - Number(b)).map(([cls, list]) => (
        <div key={cls} style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
            <div style={{
              width: 28, height: 28, borderRadius: 7,
              background: 'linear-gradient(135deg, #aa3bff22, #7c3aed22)',
              border: '1px solid #aa3bff44',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 12, fontWeight: 700, color: '#aa3bff',
              flexShrink: 0,
            }}>
              {cls}
            </div>
            <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-h)', margin: 0 }}>
              Classe {cls} — {CLASSES[Number(cls)] ?? 'Autres'}
            </h2>
            <span style={{ fontSize: 12, color: 'var(--text)' }}>({list.length})</span>
          </div>

          <div style={{ border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
            {list.map((c, i) => (
              <div
                key={c.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 16,
                  padding: '10px 16px',
                  borderBottom: i < list.length - 1 ? '1px solid var(--border)' : 'none',
                  background: 'var(--card-bg)',
                }}
              >
                <code style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: '#aa3bff',
                  background: '#aa3bff12',
                  padding: '2px 7px',
                  borderRadius: 5,
                  flexShrink: 0,
                  minWidth: 60,
                  textAlign: 'center',
                }}>
                  {c.numero}
                </code>
                <span style={{ fontSize: 13, color: 'var(--text-h)', flex: 1 }}>{c.libelle}</span>
              </div>
            ))}
          </div>
        </div>
      ))}

      {!fetching && filtered.length > 0 && (
        <p style={{ fontSize: 12, color: 'var(--text)', marginTop: 4 }}>
          {filtered.length} compte{filtered.length > 1 ? 's' : ''}
        </p>
      )}
    </div>
  )
}
