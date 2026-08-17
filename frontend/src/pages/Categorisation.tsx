import { useEffect, useState } from 'react'
import { useTenant } from '../lib/TenantContext'
import { listEcritures, type Ecriture } from '../lib/ecritures'
import { listPlanComptable, type Compte } from '../lib/plan-comptable'
import { authHeaders } from '../lib/auth'

const fmt = new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' })

async function categoriser(ecriture: Ecriture, compteNumero: string, tenantId: string): Promise<void> {
  const res = await fetch('/categorization/validate', {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({
      tenant_id: tenantId,
      compte_code: compteNumero,
      ecriture: {
        id: ecriture.id,
        libelle: ecriture.transaction_id,
        montant: parseFloat(ecriture.montant),
        tiers: '',
        date: ecriture.date,
      },
    }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export default function Categorisation() {
  const { selected, loading } = useTenant()
  const [ecritures, setEcritures] = useState<Ecriture[]>([])
  const [comptes, setComptes] = useState<Compte[]>([])
  const [fetching, setFetching] = useState(false)
  const [current, setCurrent] = useState(0)
  const [selectedCompte, setSelectedCompte] = useState('')  // numero du compte
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  useEffect(() => {
    if (!selected) return
    setFetching(true)
    setError(null)
    Promise.all([
      listEcritures(selected.id, 'a_categoriser'),
      listPlanComptable(selected.id),
    ])
      .then(([e, c]) => {
        setEcritures(e)
        setComptes(c)
        setCurrent(0)
        setSelectedCompte('')
        setDone(e.length === 0)
      })
      .catch(e => setError(String(e)))
      .finally(() => setFetching(false))
  }, [selected])

  const ecriture = ecritures[current]

  const handleSubmit = async () => {
    if (!ecriture || !selectedCompte || !selected) return
    setSubmitting(true)
    setError(null)
    try {
      await categoriser(ecriture, selectedCompte, selected.id)
      const next = current + 1
      if (next >= ecritures.length) {
        setDone(true)
      } else {
        setCurrent(next)
        setSelectedCompte('')
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading || fetching) return <div style={{ padding: 40, color: 'var(--text)' }}>Chargement…</div>
  if (!selected) return <div style={{ padding: 40, color: 'var(--text)' }}>Aucun client sélectionné.</div>

  return (
    <div style={{ padding: '32px 36px', maxWidth: 760 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-h)', margin: '0 0 4px', letterSpacing: '-0.4px' }}>Catégorisation</h1>
        <p style={{ fontSize: 14, color: 'var(--text)', margin: 0 }}>{selected.name}</p>
      </div>

      {error && (
        <div style={{ background: '#fee2e2', color: '#991b1b', borderRadius: 8, padding: '10px 16px', marginBottom: 16, fontSize: 13 }}>
          {error}
        </div>
      )}

      {done ? (
        <div style={{
          border: '1px solid var(--border)', borderRadius: 16, padding: 48,
          textAlign: 'center', background: 'var(--card-bg)',
        }}>
          <div style={{
            width: 56, height: 56, borderRadius: '50%',
            background: '#d1fae5', display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 16px',
          }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M20 6L9 17l-5-5" stroke="#065f46" strokeWidth="2.5" strokeLinecap="round"/>
            </svg>
          </div>
          <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--text-h)', margin: '0 0 6px' }}>
            Tout est catégorisé !
          </p>
          <p style={{ fontSize: 14, color: 'var(--text)', margin: 0 }}>
            Aucune écriture en attente de catégorisation.
          </p>
        </div>
      ) : ecriture ? (
        <>
          {/* Progress */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 12, color: 'var(--text)' }}>
                {current + 1} / {ecritures.length} écritures
              </span>
              <span style={{ fontSize: 12, color: 'var(--text)' }}>
                {Math.round(((current) / ecritures.length) * 100)}%
              </span>
            </div>
            <div style={{ height: 4, background: 'var(--border)', borderRadius: 2 }}>
              <div style={{
                height: '100%', borderRadius: 2,
                background: 'linear-gradient(90deg, #aa3bff, #7c3aed)',
                width: `${(current / ecritures.length) * 100}%`,
                transition: 'width 0.3s',
              }} />
            </div>
          </div>

          {/* Ecriture card */}
          <div style={{
            border: '1px solid var(--border)', borderRadius: 16,
            background: 'var(--card-bg)', overflow: 'hidden', marginBottom: 20,
          }}>
            <div style={{ padding: '18px 24px', borderBottom: '1px solid var(--border)', background: 'var(--code-bg)' }}>
              <p style={{ margin: 0, fontSize: 12, color: 'var(--text)', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 600 }}>
                Écriture à catégoriser
              </p>
            </div>
            <div style={{ padding: '20px 24px', display: 'grid', gap: 14 }}>
              <Row label="Transaction" value={ecriture.transaction_id} mono />
              <Row label="Facture" value={ecriture.facture_id ?? '—'} mono />
              <Row label="Montant" value={fmt.format(parseFloat(ecriture.montant))} bold />
              <Row label="Date" value={new Date(ecriture.date).toLocaleDateString('fr-FR')} />
            </div>
          </div>

          {/* Compte selector */}
          <div style={{
            border: '1px solid var(--border)', borderRadius: 12,
            background: 'var(--card-bg)', padding: '20px 24px', marginBottom: 16,
          }}>
            <label style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-h)', display: 'block', marginBottom: 10 }}>
              Affecter au compte
            </label>
            <select
              value={selectedCompte}
              onChange={e => setSelectedCompte(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'var(--code-bg)',
                color: selectedCompte ? 'var(--text-h)' : 'var(--text)',
                fontSize: 13,
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="">Sélectionner un compte…</option>
              {comptes.map(c => (
                <option key={c.id} value={c.numero}>
                  {c.numero} — {c.libelle}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleSubmit}
            disabled={!selectedCompte || submitting}
            style={{
              width: '100%',
              padding: '12px',
              borderRadius: 10,
              border: 'none',
              background: selectedCompte && !submitting
                ? 'linear-gradient(135deg, #aa3bff, #7c3aed)'
                : 'var(--border)',
              color: selectedCompte && !submitting ? '#fff' : 'var(--text)',
              fontSize: 14,
              fontWeight: 600,
              cursor: selectedCompte && !submitting ? 'pointer' : 'not-allowed',
              boxShadow: selectedCompte ? '0 2px 8px rgba(170,59,255,0.25)' : 'none',
              transition: 'background 0.2s',
            }}
          >
            {submitting ? 'Enregistrement…' : 'Valider la catégorisation →'}
          </button>
        </>
      ) : null}
    </div>
  )
}

function Row({ label, value, mono, bold }: { label: string; value: string; mono?: boolean; bold?: boolean }) {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'baseline' }}>
      <span style={{ fontSize: 12, color: 'var(--text)', width: 100, flexShrink: 0, textAlign: 'right' }}>{label}</span>
      <span style={{
        fontSize: mono ? 12 : 14,
        color: 'var(--text-h)',
        fontFamily: mono ? 'monospace' : 'inherit',
        fontWeight: bold ? 700 : 400,
        wordBreak: 'break-all',
      }}>
        {value}
      </span>
    </div>
  )
}
