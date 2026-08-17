import { useEffect, useState } from 'react'
import { authHeaders } from '../lib/auth'

interface Integration {
  id: string
  name: string
  type: string
  status: 'active' | 'inactive' | 'error'
  last_sync?: string
}

async function listIntegrations(): Promise<Integration[]> {
  const res = await fetch('/admin/integrations', { headers: authHeaders() })
  if (!res.ok) return []
  return res.json() as Promise<Integration[]>
}

const STATUS_COLORS: Record<string, { bg: string; color: string; label: string }> = {
  active: { bg: '#d1fae5', color: '#065f46', label: 'Actif' },
  inactive: { bg: 'var(--code-bg)', color: 'var(--text)', label: 'Inactif' },
  error: { bg: '#fee2e2', color: '#991b1b', label: 'Erreur' },
}

export default function Integrations() {
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listIntegrations()
      .then(setIntegrations)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ padding: '32px 36px', maxWidth: 900 }}>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-h)', margin: '0 0 4px', letterSpacing: '-0.4px' }}>Intégrations</h1>
        <p style={{ fontSize: 14, color: 'var(--text)', margin: 0 }}>
          Connexions aux sources de données comptables
        </p>
      </div>

      {/* PNICompta card */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-h)', margin: '0 0 14px' }}>Sources connectées</h2>
        <div style={{
          border: '1px solid var(--border)',
          borderRadius: 14,
          overflow: 'hidden',
          background: 'var(--card-bg)',
        }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 16, padding: '18px 20px',
          }}>
            <div style={{
              width: 44, height: 44, borderRadius: 10,
              background: 'linear-gradient(135deg, #3b82f622, #1d4ed822)',
              border: '1px solid #3b82f644',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <rect x="2" y="3" width="20" height="14" rx="2" stroke="#3b82f6" strokeWidth="2"/>
                <path d="M8 21h8M12 17v4" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </div>
            <div style={{ flex: 1 }}>
              <p style={{ margin: 0, fontWeight: 600, color: 'var(--text-h)', fontSize: 14 }}>PNICompta</p>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--text)' }}>Logiciel de comptabilité — factures, transactions</p>
            </div>
            <span style={{
              padding: '4px 10px',
              borderRadius: 20,
              fontSize: 11,
              fontWeight: 600,
              background: '#d1fae5',
              color: '#065f46',
            }}>
              Connecté
            </span>
          </div>
        </div>
      </div>

      {/* Dynamic integrations */}
      {!loading && integrations.length > 0 && (
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-h)', margin: '0 0 14px' }}>Autres intégrations</h2>
          <div style={{ border: '1px solid var(--border)', borderRadius: 14, overflow: 'hidden' }}>
            {integrations.map((intg, i) => {
              const s = STATUS_COLORS[intg.status] ?? STATUS_COLORS.inactive
              return (
                <div
                  key={intg.id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 16, padding: '16px 20px',
                    borderBottom: i < integrations.length - 1 ? '1px solid var(--border)' : 'none',
                    background: 'var(--card-bg)',
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <p style={{ margin: 0, fontWeight: 600, color: 'var(--text-h)', fontSize: 14 }}>{intg.name}</p>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--text)' }}>{intg.type}</p>
                  </div>
                  {intg.last_sync && (
                    <span style={{ fontSize: 12, color: 'var(--text)' }}>
                      Sync : {new Date(intg.last_sync).toLocaleDateString('fr-FR')}
                    </span>
                  )}
                  <span style={{
                    padding: '4px 10px', borderRadius: 20,
                    fontSize: 11, fontWeight: 600,
                    background: s.bg, color: s.color,
                  }}>
                    {s.label}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Coming soon */}
      <div style={{ marginTop: 32 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-h)', margin: '0 0 14px' }}>Prochainement</h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
          {['Sage 50', 'QuickBooks', 'Pennylane', 'FEC import', 'API REST publique'].map(name => (
            <div
              key={name}
              style={{
                border: '1px dashed var(--border)',
                borderRadius: 12, padding: '16px 20px',
                background: 'var(--card-bg)',
                opacity: 0.6,
              }}
            >
              <p style={{ margin: 0, fontWeight: 600, color: 'var(--text-h)', fontSize: 13 }}>{name}</p>
              <p style={{ margin: '4px 0 0', fontSize: 11, color: 'var(--text)' }}>Bientôt disponible</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
