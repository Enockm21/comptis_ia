import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { clearToken } from '../lib/auth'
import { listTenants, type Tenant } from '../lib/tenants'
import {
  runReconciliation,
  getConflicts,
  resolveConflict,
  getReport,
  type Conflict,
  type Report,
} from '../lib/reconciliation'
import ConflictReview from '../components/ConflictReview'
import ReconciliationReport from '../components/ReconciliationReport'

type Step = 'trigger' | 'review' | 'report'

const inputStyle: React.CSSProperties = {
  padding: '10px 14px',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'var(--bg)',
  color: 'var(--text-h)',
  fontSize: 15,
  width: '100%',
  boxSizing: 'border-box',
  outline: 'none',
}

const labelStyle: React.CSSProperties = {
  fontSize: 14,
  fontWeight: 500,
  color: 'var(--text-h)',
  display: 'block',
  marginBottom: 6,
}

export default function Reconciliation() {
  const navigate = useNavigate()
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [tenantId, setTenantId] = useState('')
  const [dateDebut, setDateDebut] = useState('')
  const [dateFin, setDateFin] = useState('')
  const [step, setStep] = useState<Step>('trigger')
  const [runId, setRunId] = useState<string | null>(null)
  const [conflicts, setConflicts] = useState<Conflict[]>([])
  const [totalConflicts, setTotalConflicts] = useState(0)
  const [report, setReport] = useState<Report | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    listTenants()
      .then(setTenants)
      .catch(err => setError(err instanceof Error ? err.message : 'Erreur de chargement'))
  }, [])

  const advanceAfter = async (id: string, previousTotal: number) => {
    const pending = await getConflicts(id)
    if (pending.length === 0) {
      setReport(await getReport(id))
      setStep('report')
    } else {
      setConflicts(pending)
      setTotalConflicts(Math.max(previousTotal, pending.length))
      setStep('review')
    }
  }

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    try {
      const run = await runReconciliation({
        tenant_id: tenantId,
        date_debut: dateDebut || null,
        date_fin: dateFin || null,
      })
      setRunId(run.run_id)
      await advanceAfter(run.run_id, 0)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors du lancement')
    } finally {
      setLoading(false)
    }
  }

  const handleDecide = async (decision: 'confirmer' | 'rejeter' | 'ecart_accepte') => {
    if (!runId || conflicts.length === 0) return
    setLoading(true)
    setError(null)
    try {
      await resolveConflict(runId, conflicts[0].transaction.id, decision)
      await advanceAfter(runId, totalConflicts)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur lors de la décision')
    } finally {
      setLoading(false)
    }
  }

  const handleRestart = () => {
    setStep('trigger')
    setRunId(null)
    setConflicts([])
    setTotalConflicts(0)
    setReport(null)
    setError(null)
  }

  const handleLogout = () => {
    clearToken()
    navigate('/login')
  }

  const selectedTenant = tenants.find(t => t.id === tenantId)

  if (step === 'review' && conflicts.length > 0) {
    return (
      <ConflictReview
        conflict={conflicts[0]}
        index={totalConflicts - conflicts.length + 1}
        total={totalConflicts}
        onDecide={handleDecide}
        deciding={loading}
        error={error}
        tenantName={selectedTenant?.name}
      />
    )
  }

  if (step === 'report' && report) {
    return <ReconciliationReport report={report} onRestart={handleRestart} tenantName={selectedTenant?.name} />
  }

  return (
    <div style={{ minHeight: '100svh', background: 'var(--bg)' }}>
      {/* Top nav */}
      <nav style={{
        borderBottom: '1px solid var(--border)',
        padding: '0 24px',
        height: 56,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
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
          <span style={{ fontWeight: 700, fontSize: 16, color: 'var(--text-h)', letterSpacing: '-0.2px' }}>
            Comptis
          </span>
        </div>
        <button
          onClick={handleLogout}
          style={{
            padding: '6px 14px', borderRadius: 8,
            border: '1px solid var(--border)',
            background: 'transparent',
            color: 'var(--text)',
            fontSize: 13, fontWeight: 500, cursor: 'pointer',
          }}
        >
          Déconnexion
        </button>
      </nav>

      {/* Page content */}
      <div style={{ maxWidth: 560, margin: '0 auto', padding: '48px 24px' }}>
        {/* Header */}
        <div style={{ marginBottom: 32 }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            padding: '4px 12px', borderRadius: 20,
            background: 'var(--accent-bg)',
            border: '1px solid var(--accent-border)',
            marginBottom: 12,
          }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#aa3bff' }} />
            <span style={{ fontSize: 12, fontWeight: 600, color: '#aa3bff', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Rapprochement
            </span>
          </div>
          <h1 style={{ fontSize: 30, fontWeight: 700, color: 'var(--text-h)', margin: '0 0 8px', letterSpacing: '-0.5px' }}>
            Nouveau rapprochement
          </h1>
          <p style={{ color: 'var(--text)', fontSize: 15, margin: 0 }}>
            Sélectionnez un client et une période pour lancer l'analyse.
          </p>
        </div>

        {/* Form card */}
        <div style={{
          background: 'var(--bg)',
          border: '1px solid var(--border)',
          borderRadius: 16,
          padding: '28px 24px',
          boxShadow: '0 2px 12px rgba(0,0,0,0.05)',
        }}>
          {error && (
            <div style={{
              display: 'flex', alignItems: 'flex-start', gap: 10,
              padding: '12px 14px', borderRadius: 8, marginBottom: 20,
              background: 'rgba(220,38,38,0.07)',
              border: '1px solid rgba(220,38,38,0.2)',
              color: '#dc2626', fontSize: 14,
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0, marginTop: 1 }}>
                <circle cx="12" cy="12" r="10" stroke="#dc2626" strokeWidth="2"/>
                <line x1="12" y1="8" x2="12" y2="12" stroke="#dc2626" strokeWidth="2" strokeLinecap="round"/>
                <circle cx="12" cy="16" r="1" fill="#dc2626"/>
              </svg>
              {error}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <div>
              <label style={labelStyle}>Client</label>
              <select
                value={tenantId}
                onChange={e => setTenantId(e.target.value)}
                style={{ ...inputStyle, appearance: 'none' }}
              >
                <option value="">Sélectionner un client…</option>
                {tenants.map(t => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
              {tenants.length === 0 && (
                <p style={{ margin: '6px 0 0', fontSize: 13, color: 'var(--text)' }}>
                  Aucun client disponible pour votre compte.
                </p>
              )}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div>
                <label style={labelStyle}>Date de début</label>
                <input
                  type="date"
                  value={dateDebut}
                  onChange={e => setDateDebut(e.target.value)}
                  style={inputStyle}
                />
              </div>
              <div>
                <label style={labelStyle}>Date de fin</label>
                <input
                  type="date"
                  value={dateFin}
                  onChange={e => setDateFin(e.target.value)}
                  style={inputStyle}
                />
              </div>
            </div>

            {!dateDebut && !dateFin && (
              <p style={{ margin: '-8px 0 0', fontSize: 13, color: 'var(--text)' }}>
                Sans dates : les 30 derniers jours sont analysés automatiquement.
              </p>
            )}

            <button
              onClick={() => void handleRun()}
              disabled={!tenantId || loading}
              style={{
                padding: '12px 20px',
                borderRadius: 10,
                border: 'none',
                background: !tenantId || loading
                  ? 'var(--border)'
                  : 'linear-gradient(135deg, #aa3bff 0%, #7c3aed 100%)',
                color: !tenantId || loading ? 'var(--text)' : '#fff',
                fontSize: 15, fontWeight: 600,
                cursor: !tenantId || loading ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                transition: 'opacity 0.15s',
                boxShadow: !tenantId || loading ? 'none' : '0 2px 8px rgba(170,59,255,0.3)',
              }}
            >
              {loading ? (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
                    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" strokeOpacity="0.3"/>
                    <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                  Analyse en cours…
                </>
              ) : (
                <>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                    <path d="M5 3l14 9-14 9V3z" fill="#fff"/>
                  </svg>
                  Lancer le rapprochement
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
