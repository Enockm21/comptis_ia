import type { Conflict } from '../lib/reconciliation'

interface Props {
  conflict: Conflict
  index: number
  total: number
  onDecide: (decision: 'confirmer' | 'rejeter' | 'ecart_accepte') => void
  deciding: boolean
  error?: string | null
  tenantName?: string
}

const RAISON_LABELS: Record<string, string> = {
  ecart_montant: 'Écart de montant',
  confidence_insuffisante: 'Confiance insuffisante',
  ambiguous: 'Ambiguïté',
}

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color = pct >= 80 ? '#16a34a' : pct >= 60 ? '#d97706' : '#dc2626'
  const bg = pct >= 80 ? 'rgba(22,163,74,0.1)' : pct >= 60 ? 'rgba(217,119,6,0.1)' : 'rgba(220,38,38,0.1)'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '3px 10px', borderRadius: 20,
      background: bg, color, fontSize: 13, fontWeight: 600,
    }}>
      {pct}% de confiance
    </span>
  )
}

function DataRow({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', padding: '8px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: 13, color: 'var(--text)' }}>{label}</span>
      <span style={{
        fontSize: 14, fontWeight: 500, color: 'var(--text-h)',
        fontFamily: mono ? 'var(--mono)' : undefined,
      }}>
        {value}
      </span>
    </div>
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

export default function ConflictReview({ conflict, index, total, onDecide, deciding, error, tenantName }: Props) {
  const progressPct = Math.round((index / total) * 100)
  const montantTxn = parseFloat(conflict.transaction.montant)
  const montantFac = conflict.facture ? parseFloat(conflict.facture.montant) : null
  const hasEcart = montantFac !== null && Math.abs(montantTxn - montantFac) > 0.01
  const ecart = montantFac !== null ? Math.abs(montantTxn - montantFac) : null

  return (
    <div style={{ minHeight: '100svh', background: 'var(--bg)' }}>
      {/* Top bar */}
      <div style={{
        borderBottom: '1px solid var(--border)',
        padding: '14px 24px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
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
              <span style={{ color: 'var(--border)', margin: '0 2px' }}>›</span>
              <span style={{ fontSize: 14, color: 'var(--text)' }}>{tenantName}</span>
            </>
          )}
        </div>
        <div style={{ fontSize: 13, color: 'var(--text)', fontWeight: 500 }}>
          Conflit {index} sur {total}
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ height: 3, background: 'var(--border)' }}>
        <div style={{
          height: '100%',
          width: `${progressPct}%`,
          background: 'linear-gradient(90deg, #aa3bff, #7c3aed)',
          transition: 'width 0.3s ease',
        }} />
      </div>

      <div style={{ maxWidth: 900, margin: '0 auto', padding: '40px 24px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28, flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-h)', margin: '0 0 8px', letterSpacing: '-0.3px' }}>
              Rapprochement à valider
            </h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{
                padding: '3px 10px', borderRadius: 6,
                background: 'var(--code-bg)', border: '1px solid var(--border)',
                fontSize: 12, color: 'var(--text)', fontWeight: 500,
              }}>
                {RAISON_LABELS[conflict.raison] ?? conflict.raison}
              </span>
              <ScoreBadge score={conflict.composite_score} />
            </div>
          </div>
        </div>

        {error && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20,
            padding: '10px 14px', borderRadius: 8,
            background: 'rgba(220,38,38,0.07)',
            border: '1px solid rgba(220,38,38,0.2)',
            color: '#dc2626', fontSize: 14,
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="#dc2626" strokeWidth="2"/>
              <line x1="12" y1="8" x2="12" y2="12" stroke="#dc2626" strokeWidth="2" strokeLinecap="round"/>
              <circle cx="12" cy="16" r="1" fill="#dc2626"/>
            </svg>
            {error}
          </div>
        )}

        {/* Side-by-side cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
          {/* Transaction */}
          <div style={{
            background: 'var(--bg)',
            border: '2px solid var(--border)',
            borderRadius: 14,
            overflow: 'hidden',
          }}>
            <div style={{
              padding: '14px 18px',
              background: 'rgba(107,99,117,0.04)',
              borderBottom: '1px solid var(--border)',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: '#6b6375',
              }} />
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Transaction bancaire
              </span>
            </div>
            <div style={{ padding: '4px 18px 16px' }}>
              <div style={{ padding: '14px 0 6px' }}>
                <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text-h)', fontFamily: 'var(--mono)' }}>
                  {formatAmount(conflict.transaction.montant)}
                </div>
                <div style={{ fontSize: 13, color: 'var(--text)', marginTop: 2 }}>{formatDate(conflict.transaction.date)}</div>
              </div>
              <DataRow label="Libellé" value={conflict.transaction.libelle} />
              <DataRow label="Montant brut" value={conflict.transaction.montant} mono />
              <DataRow label="Réf." value={conflict.transaction.id} />
            </div>
          </div>

          {/* Facture */}
          <div style={{
            background: 'var(--bg)',
            border: `2px solid ${conflict.facture ? '#aa3bff' : 'var(--border)'}`,
            borderRadius: 14,
            overflow: 'hidden',
          }}>
            <div style={{
              padding: '14px 18px',
              background: conflict.facture ? 'rgba(170,59,255,0.05)' : 'rgba(107,99,117,0.04)',
              borderBottom: `1px solid ${conflict.facture ? 'rgba(170,59,255,0.2)' : 'var(--border)'}`,
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%',
                background: conflict.facture ? '#aa3bff' : 'var(--border)',
              }} />
              <span style={{
                fontSize: 12, fontWeight: 700,
                color: conflict.facture ? '#aa3bff' : 'var(--text)',
                textTransform: 'uppercase', letterSpacing: '0.08em',
              }}>
                Facture candidate
              </span>
            </div>
            <div style={{ padding: '4px 18px 16px' }}>
              {conflict.facture ? (
                <>
                  <div style={{ padding: '14px 0 6px' }}>
                    <div style={{
                      fontSize: 26, fontWeight: 700, fontFamily: 'var(--mono)',
                      color: hasEcart ? '#d97706' : 'var(--text-h)',
                    }}>
                      {formatAmount(conflict.facture.montant)}
                    </div>
                    <div style={{ fontSize: 13, color: 'var(--text)', marginTop: 2 }}>{formatDate(conflict.facture.date)}</div>
                    {hasEcart && ecart !== null && (
                      <div style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 6,
                        padding: '2px 8px', borderRadius: 4,
                        background: 'rgba(217,119,6,0.1)',
                        color: '#d97706', fontSize: 12, fontWeight: 600,
                      }}>
                        Écart : {formatAmount(ecart.toFixed(2))}
                      </div>
                    )}
                  </div>
                  <DataRow label="Fournisseur" value={conflict.facture.fournisseur} />
                  <DataRow label="Montant brut" value={conflict.facture.montant} mono />
                  <DataRow label="Réf." value={conflict.facture.id} />
                </>
              ) : (
                <div style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center',
                  justifyContent: 'center', padding: '40px 0', gap: 12, color: 'var(--text)',
                }}>
                  <svg width="36" height="36" viewBox="0 0 24 24" fill="none">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" stroke="currentColor" strokeWidth="1.5"/>
                    <polyline points="14,2 14,8 20,8" stroke="currentColor" strokeWidth="1.5"/>
                    <line x1="12" y1="11" x2="12" y2="17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    <line x1="9" y1="14" x2="15" y2="14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                  <span style={{ fontSize: 14 }}>Aucune facture candidate trouvée</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Action buttons */}
        <div style={{
          background: 'var(--bg)',
          border: '1px solid var(--border)',
          borderRadius: 14,
          padding: '20px 24px',
          display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap',
        }}>
          <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text)', flexShrink: 0 }}>
            Votre décision :
          </span>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', flex: 1 }}>
            <button
              disabled={deciding || !conflict.facture}
              onClick={() => onDecide('confirmer')}
              style={{
                flex: 1, minWidth: 120,
                padding: '11px 18px', borderRadius: 9, border: 'none',
                background: deciding || !conflict.facture ? 'var(--border)' : '#16a34a',
                color: deciding || !conflict.facture ? 'var(--text)' : '#fff',
                fontSize: 14, fontWeight: 600,
                cursor: deciding || !conflict.facture ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                <polyline points="20,6 9,17 4,12" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
              </svg>
              Confirmer
            </button>
            <button
              disabled={deciding || !conflict.facture}
              onClick={() => onDecide('ecart_accepte')}
              style={{
                flex: 1, minWidth: 120,
                padding: '11px 18px', borderRadius: 9, border: 'none',
                background: deciding || !conflict.facture ? 'var(--border)' : '#d97706',
                color: deciding || !conflict.facture ? 'var(--text)' : '#fff',
                fontSize: 14, fontWeight: 600,
                cursor: deciding || !conflict.facture ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                <line x1="12" y1="8" x2="12" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                <circle cx="12" cy="16" r="1" fill="currentColor"/>
              </svg>
              Écart accepté
            </button>
            <button
              disabled={deciding}
              onClick={() => onDecide('rejeter')}
              style={{
                flex: 1, minWidth: 120,
                padding: '11px 18px', borderRadius: 9,
                border: '1px solid rgba(220,38,38,0.4)',
                background: 'rgba(220,38,38,0.05)',
                color: '#dc2626',
                fontSize: 14, fontWeight: 600,
                cursor: deciding ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                <line x1="18" y1="6" x2="6" y2="18" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
                <line x1="6" y1="6" x2="18" y2="18" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
              </svg>
              Rejeter
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
