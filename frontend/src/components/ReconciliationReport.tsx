import type { Report, MatchData, TransactionData } from '../lib/reconciliation'

interface Props {
  report: Report
  onRestart: () => void
  tenantName?: string
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div style={{
      background: 'var(--bg)',
      border: '1px solid var(--border)',
      borderRadius: 12,
      padding: '18px 20px',
      display: 'flex', flexDirection: 'column', gap: 4,
    }}>
      <span style={{ fontSize: 28, fontWeight: 700, color, fontFamily: 'var(--mono)', lineHeight: 1 }}>
        {value}
      </span>
      <span style={{ fontSize: 13, color: 'var(--text)', fontWeight: 500 }}>{label}</span>
    </div>
  )
}

const STATUT_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  confirme: { label: 'Confirmé', color: '#16a34a', bg: 'rgba(22,163,74,0.1)' },
  ecart: { label: 'Écart accepté', color: '#d97706', bg: 'rgba(217,119,6,0.1)' },
  auto: { label: 'Auto', color: '#aa3bff', bg: 'rgba(170,59,255,0.1)' },
}

function StatutBadge({ statut }: { statut: string }) {
  const s = STATUT_LABELS[statut] ?? { label: statut, color: 'var(--text)', bg: 'var(--code-bg)' }
  return (
    <span style={{
      padding: '3px 9px', borderRadius: 6,
      background: s.bg, color: s.color,
      fontSize: 12, fontWeight: 600,
    }}>
      {s.label}
    </span>
  )
}

function formatAmount(montant: string) {
  const n = parseFloat(montant)
  return isNaN(n) ? montant : new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(n)
}

function formatDate(d: string) {
  try {
    return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(d))
  } catch {
    return d
  }
}

const thStyle: React.CSSProperties = {
  padding: '10px 14px',
  textAlign: 'left',
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--text)',
  textTransform: 'uppercase',
  letterSpacing: '0.07em',
  borderBottom: '1px solid var(--border)',
  background: 'rgba(107,99,117,0.03)',
  whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  padding: '12px 14px',
  fontSize: 14,
  color: 'var(--text-h)',
  borderBottom: '1px solid var(--border)',
  verticalAlign: 'middle',
}

export default function ReconciliationReport({ report, onRestart, tenantName }: Props) {
  const totalMatched = report.total_rapprochees + report.total_ecarts
  const rapprochRate = report.total_transactions > 0
    ? Math.round((totalMatched / report.total_transactions) * 100)
    : 0

  return (
    <div style={{ minHeight: '100svh', background: 'var(--bg)' }}>
      {/* Top nav */}
      <div style={{
        borderBottom: '1px solid var(--border)',
        padding: '14px 24px',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: 8,
          background: 'linear-gradient(135deg, #aa3bff, #7c3aed)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M9 7H6a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-3" stroke="#fff" strokeWidth="2.5" strokeLinecap="round"/>
            <path d="M15 3h6v6M10 14 21 3" stroke="#fff" strokeWidth="2.5" strokeLinecap="round"/>
          </svg>
        </div>
        <span style={{ fontWeight: 700, fontSize: 16, color: 'var(--text-h)' }}>Comptis</span>
        {tenantName && (
          <>
            <span style={{ color: 'var(--border)' }}>›</span>
            <span style={{ fontSize: 14, color: 'var(--text)' }}>{tenantName}</span>
            <span style={{ color: 'var(--border)' }}>›</span>
            <span style={{ fontSize: 14, color: 'var(--text)' }}>Rapport</span>
          </>
        )}
      </div>

      <div style={{ maxWidth: 960, margin: '0 auto', padding: '40px 24px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 32, flexWrap: 'wrap', gap: 16 }}>
          <div>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 10,
              padding: '3px 10px', borderRadius: 20,
              background: 'rgba(22,163,74,0.1)',
              border: '1px solid rgba(22,163,74,0.3)',
            }}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                <polyline points="20,6 9,17 4,12" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round"/>
              </svg>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#16a34a', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Rapprochement terminé
              </span>
            </div>
            <h1 style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-h)', margin: '0 0 6px', letterSpacing: '-0.4px' }}>
              Rapport de rapprochement
            </h1>
            <p style={{ color: 'var(--text)', fontSize: 14, margin: 0 }}>
              {formatDate(report.date_debut)} — {formatDate(report.date_fin)}
            </p>
          </div>
          <button
            onClick={onRestart}
            style={{
              padding: '10px 18px', borderRadius: 9, border: 'none',
              background: 'linear-gradient(135deg, #aa3bff, #7c3aed)',
              color: '#fff', fontSize: 14, fontWeight: 600, cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 7,
              boxShadow: '0 2px 8px rgba(170,59,255,0.3)',
            }}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M1 4v6h6M23 20v-6h-6" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10M23 14l-4.64 4.36A9 9 0 0 1 3.51 15" stroke="#fff" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            Nouveau rapprochement
          </button>
        </div>

        {/* Stat cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 32 }}>
          <StatCard label="Transactions" value={report.total_transactions} color="var(--text-h)" />
          <StatCard label="Rapprochées" value={totalMatched} color="#16a34a" />
          <StatCard label="Non rapprochées" value={report.total_non_rapprochees} color="#dc2626" />
          <StatCard label="Écarts acceptés" value={report.total_ecarts} color="#d97706" />
        </div>

        {/* Rate bar */}
        {report.total_transactions > 0 && (
          <div style={{
            background: 'var(--bg)',
            border: '1px solid var(--border)',
            borderRadius: 12, padding: '18px 20px',
            marginBottom: 32,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
              <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-h)' }}>Taux de rapprochement</span>
              <span style={{ fontSize: 22, fontWeight: 700, color: '#16a34a', fontFamily: 'var(--mono)' }}>
                {rapprochRate}%
              </span>
            </div>
            <div style={{ height: 8, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${rapprochRate}%`,
                background: rapprochRate >= 80 ? '#16a34a' : rapprochRate >= 50 ? '#d97706' : '#dc2626',
                borderRadius: 4,
                transition: 'width 0.5s ease',
              }} />
            </div>
          </div>
        )}

        {/* Matches table */}
        {report.matches.length > 0 && (
          <div style={{ marginBottom: 28 }}>
            <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-h)', margin: '0 0 14px', letterSpacing: '-0.2px' }}>
              Transactions rapprochées
              <span style={{
                marginLeft: 8, padding: '2px 8px', borderRadius: 20,
                background: 'var(--code-bg)', fontSize: 13, fontWeight: 500, color: 'var(--text)',
              }}>
                {report.matches.length}
              </span>
            </h2>
            <div style={{
              border: '1px solid var(--border)',
              borderRadius: 12, overflow: 'hidden',
              overflowX: 'auto',
            }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 500 }}>
                <thead>
                  <tr>
                    <th style={thStyle}>Facture</th>
                    <th style={thStyle}>Transaction</th>
                    <th style={thStyle}>Statut</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Écart</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {report.matches.map((m: MatchData) => (
                    <tr key={`${m.facture_id}-${m.transaction_id}`} style={{ transition: 'background 0.1s' }}>
                      <td style={{ ...tdStyle, fontFamily: 'var(--mono)', fontSize: 13 }}>{m.facture_id}</td>
                      <td style={{ ...tdStyle, fontFamily: 'var(--mono)', fontSize: 13 }}>{m.transaction_id}</td>
                      <td style={tdStyle}><StatutBadge statut={m.statut} /></td>
                      <td style={{ ...tdStyle, textAlign: 'right', fontFamily: 'var(--mono)' }}>
                        {parseFloat(m.ecart_montant) > 0.001 ? (
                          <span style={{ color: '#d97706' }}>{formatAmount(m.ecart_montant)}</span>
                        ) : (
                          <span style={{ color: '#16a34a' }}>—</span>
                        )}
                      </td>
                      <td style={{ ...tdStyle, textAlign: 'right' }}>
                        <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--text)' }}>
                          {Math.round(m.confidence * 100)}%
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Unmatched table */}
        {report.unmatched.length > 0 && (
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-h)', margin: '0 0 14px', letterSpacing: '-0.2px' }}>
              Transactions non rapprochées
              <span style={{
                marginLeft: 8, padding: '2px 8px', borderRadius: 20,
                background: 'rgba(220,38,38,0.1)', fontSize: 13, fontWeight: 500, color: '#dc2626',
              }}>
                {report.unmatched.length}
              </span>
            </h2>
            <div style={{
              border: '1px solid var(--border)',
              borderRadius: 12, overflow: 'hidden',
              overflowX: 'auto',
            }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 420 }}>
                <thead>
                  <tr>
                    <th style={thStyle}>Référence</th>
                    <th style={{ ...thStyle, textAlign: 'right' }}>Montant</th>
                    <th style={thStyle}>Date</th>
                    <th style={thStyle}>Libellé</th>
                  </tr>
                </thead>
                <tbody>
                  {report.unmatched.map((t: TransactionData) => (
                    <tr key={t.id}>
                      <td style={{ ...tdStyle, fontFamily: 'var(--mono)', fontSize: 13 }}>{t.id}</td>
                      <td style={{ ...tdStyle, textAlign: 'right', fontFamily: 'var(--mono)', fontWeight: 600, color: '#dc2626' }}>
                        {formatAmount(t.montant)}
                      </td>
                      <td style={{ ...tdStyle, whiteSpace: 'nowrap' }}>{formatDate(t.date)}</td>
                      <td style={{ ...tdStyle, maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {t.libelle}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {report.matches.length === 0 && report.unmatched.length === 0 && (
          <div style={{
            textAlign: 'center', padding: '48px 24px',
            border: '1px solid var(--border)', borderRadius: 12,
            color: 'var(--text)',
          }}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" style={{ marginBottom: 12 }}>
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M8 12h8M12 8v8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <p style={{ margin: 0, fontSize: 15 }}>Aucune transaction trouvée sur cette période.</p>
          </div>
        )}
      </div>
    </div>
  )
}
