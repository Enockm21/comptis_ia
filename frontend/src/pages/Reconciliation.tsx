import { useEffect, useState } from 'react'
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

export default function Reconciliation() {
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
      .catch(err => setError(err instanceof Error ? err.message : 'Erreur de chargement des tenants'))
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
  }

  if (step === 'review' && conflicts.length > 0) {
    return (
      <ConflictReview
        conflict={conflicts[0]}
        index={totalConflicts - conflicts.length + 1}
        total={totalConflicts}
        onDecide={handleDecide}
        deciding={loading}
      />
    )
  }

  if (step === 'report' && report) {
    return <ReconciliationReport report={report} onRestart={handleRestart} />
  }

  return (
    <div style={{ maxWidth: 500, margin: '40px auto', padding: 24 }}>
      <h1>Lancer un rapprochement</h1>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <div>
        <label>Tenant</label>
        <select value={tenantId} onChange={e => setTenantId(e.target.value)}>
          <option value="">-- choisir --</option>
          {tenants.map(t => (
            <option key={t.id} value={t.id}>{t.name}</option>
          ))}
        </select>
      </div>
      <div>
        <label>Date début (optionnel)</label>
        <input type="date" value={dateDebut} onChange={e => setDateDebut(e.target.value)} />
      </div>
      <div>
        <label>Date fin (optionnel)</label>
        <input type="date" value={dateFin} onChange={e => setDateFin(e.target.value)} />
      </div>
      <button onClick={() => void handleRun()} disabled={!tenantId || loading}>
        {loading ? 'Lancement...' : 'Lancer le rapprochement'}
      </button>
    </div>
  )
}
