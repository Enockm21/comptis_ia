import { useEffect, useState } from 'react'
import { useTenant } from '../lib/TenantContext'
import { listEcritures, type Ecriture } from '../lib/ecritures'

const fmt = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })

const STATUTS = [
  { value: '', label: 'Toutes' },
  { value: 'a_categoriser', label: 'À catégoriser' },
  { value: 'categorisee', label: 'Catégorisées' },
  { value: 'validee', label: 'Validées' },
]

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
      whiteSpace: 'nowrap',
    }}>
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
    <div style={{ padding: '32px 36px', maxWidth: 1100 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-h)', margin: '0 0 4px', letterSpacing: '-0.4px' }}>Écritures</h1>
          <p style={{ fontSize: 14, color: 'var(--text)', margin: 0 }}>
            {selected?.name ?? '—'}
          </p>
        </div>
        {/* Filter tabs */}
        <div style={{ display: 'flex', gap: 4, background: 'var(--code-bg)', padding: 4, borderRadius: 10, border: '1px solid var(--border)' }}>
          {STATUTS.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setStatut(value)}
              style={{
                padding: '6px 14px',
                borderRadius: 7,
                border: 'none',
                background: statut === value ? 'var(--bg)' : 'transparent',
                color: statut === value ? 'var(--text-h)' : 'var(--text)',
                fontSize: 13,
                fontWeight: statut === value ? 600 : 400,
                cursor: 'pointer',
                boxShadow: statut === value ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                transition: 'background 0.1s',
              }}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {loading && <p style={{ color: 'var(--text)' }}>Chargement…</p>}
      {!loading && !selected && <p style={{ color: 'var(--text)' }}>Aucun client sélectionné.</p>}
      {error && (
        <div style={{ background: '#fee2e2', color: '#991b1b', borderRadius: 8, padding: '10px 16px', marginBottom: 16, fontSize: 13 }}>
          {error}
        </div>
      )}

      {!loading && selected && (
        <div style={{ border: '1px solid var(--border)', borderRadius: 12, overflow: 'auto' }}>
          {fetching ? (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--text)' }}>Chargement…</div>
          ) : ecritures.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--text)' }}>
              <p style={{ margin: 0, fontSize: 15 }}>Aucune écriture</p>
              <p style={{ margin: '6px 0 0', fontSize: 13 }}>Lancez un rapprochement pour en créer.</p>
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--code-bg)' }}>
                  {['Date', 'Transaction', 'Facture', 'Montant', 'Compte', 'Statut'].map(h => (
                    <th key={h} style={{ padding: '12px 16px', textAlign: 'left', fontWeight: 600, color: 'var(--text)', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ecritures.map((e, i) => (
                  <tr
                    key={e.id}
                    style={{
                      borderBottom: i < ecritures.length - 1 ? '1px solid var(--border)' : 'none',
                      background: 'var(--card-bg)',
                    }}
                  >
                    <td style={{ padding: '12px 16px', color: 'var(--text)', whiteSpace: 'nowrap' }}>
                      {new Date(e.date).toLocaleDateString('fr-FR')}
                    </td>
                    <td style={{ padding: '12px 16px', color: 'var(--text-h)', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {e.transaction_id}
                    </td>
                    <td style={{ padding: '12px 16px', color: 'var(--text)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {e.facture_id ?? '—'}
                    </td>
                    <td style={{ padding: '12px 16px', color: 'var(--text-h)', fontWeight: 600, whiteSpace: 'nowrap' }}>
                      {fmt.format(parseFloat(e.montant))}
                    </td>
                    <td style={{ padding: '12px 16px', color: 'var(--text)', fontFamily: 'monospace', fontSize: 11 }}>
                      {e.compte_id ?? <span style={{ opacity: 0.4 }}>—</span>}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
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
        <p style={{ fontSize: 12, color: 'var(--text)', marginTop: 10 }}>
          {ecritures.length} écriture{ecritures.length > 1 ? 's' : ''}
        </p>
      )}
    </div>
  )
}
