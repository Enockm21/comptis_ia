import { useEffect, useState } from 'react'
import { useTenant } from '../lib/TenantContext'
import { listEcritures, type Ecriture } from '../lib/ecritures'
import { listPlanComptable, type Compte } from '../lib/plan-comptable'
import { authHeaders } from '../lib/auth'
import { Button } from '@/components/ui/button'

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
  const [selectedCompte, setSelectedCompte] = useState('')
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

  if (loading || fetching) return <div className="p-10 text-[var(--text)]">Chargement…</div>
  if (!selected) return <div className="p-10 text-[var(--text)]">Aucun client sélectionné.</div>

  return (
    <div className="px-9 py-8 max-w-[760px]">
      <div className="mb-7">
        <h1 className="text-[22px] font-bold text-[var(--text-h)] m-0 mb-1 tracking-[-0.4px]">Catégorisation</h1>
        <p className="text-[14px] text-[var(--text)] m-0">{selected.name}</p>
      </div>

      {error && (
        <div className="bg-red-50 text-red-800 rounded-lg px-4 py-2.5 mb-4 text-[13px] dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      {done ? (
        <div className="border border-[var(--border)] rounded-2xl py-12 px-8 text-center bg-[var(--card-bg)]">
          <div className="w-14 h-14 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-4 dark:bg-emerald-900/30">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M20 6L9 17l-5-5" stroke="#065f46" strokeWidth="2.5" strokeLinecap="round"/>
            </svg>
          </div>
          <p className="text-[16px] font-semibold text-[var(--text-h)] m-0 mb-1.5">Tout est catégorisé !</p>
          <p className="text-[14px] text-[var(--text)] m-0">Aucune écriture en attente de catégorisation.</p>
        </div>
      ) : ecriture ? (
        <>
          {/* Progress */}
          <div className="mb-5">
            <div className="flex justify-between mb-1.5">
              <span className="text-[12px] text-[var(--text)]">{current + 1} / {ecritures.length} écritures</span>
              <span className="text-[12px] text-[var(--text)]">{Math.round((current / ecritures.length) * 100)}%</span>
            </div>
            <div className="h-1 bg-[var(--border)] rounded-full">
              <div
                className="h-full rounded-full bg-gradient-to-r from-[#aa3bff] to-[#7c3aed] transition-[width] duration-300"
                style={{ width: `${(current / ecritures.length) * 100}%` }}
              />
            </div>
          </div>

          {/* Ecriture card */}
          <div className="border border-[var(--border)] rounded-2xl bg-[var(--card-bg)] overflow-hidden mb-5">
            <div className="px-6 py-4 border-b border-[var(--border)] bg-[var(--code-bg)]">
              <p className="m-0 text-[12px] text-[var(--text)] uppercase tracking-[0.07em] font-semibold">
                Écriture à catégoriser
              </p>
            </div>
            <div className="px-6 py-5 grid gap-3.5">
              <Row label="Transaction" value={ecriture.transaction_id} mono />
              <Row label="Facture" value={ecriture.facture_id ?? '—'} mono />
              <Row label="Montant" value={fmt.format(parseFloat(ecriture.montant))} bold />
              <Row label="Date" value={new Date(ecriture.date).toLocaleDateString('fr-FR')} />
            </div>
          </div>

          {/* Compte selector */}
          <div className="border border-[var(--border)] rounded-xl bg-[var(--card-bg)] px-6 py-5 mb-4">
            <label className="text-[13px] font-semibold text-[var(--text-h)] block mb-2.5">
              Affecter au compte
            </label>
            <select
              value={selectedCompte}
              onChange={e => setSelectedCompte(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--code-bg)] text-[13px] outline-none cursor-pointer text-[var(--text-h)]"
            >
              <option value="">Sélectionner un compte…</option>
              {comptes.map(c => (
                <option key={c.id} value={c.numero}>
                  {c.numero} — {c.libelle}
                </option>
              ))}
            </select>
          </div>

          <Button
            onClick={handleSubmit}
            disabled={!selectedCompte || submitting}
            className="w-full py-3 text-[14px] font-semibold bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 shadow-[0_2px_8px_rgba(170,59,255,0.25)] hover:opacity-90 disabled:opacity-50 disabled:shadow-none"
          >
            {submitting ? 'Enregistrement…' : 'Valider la catégorisation →'}
          </Button>
        </>
      ) : null}
    </div>
  )
}

function Row({ label, value, mono, bold }: { label: string; value: string; mono?: boolean; bold?: boolean }) {
  return (
    <div className="flex gap-3 items-baseline">
      <span className="text-[12px] text-[var(--text)] w-[100px] shrink-0 text-right">{label}</span>
      <span className={`text-[var(--text-h)] break-all ${mono ? 'text-[12px] font-mono' : 'text-[14px]'} ${bold ? 'font-bold' : ''}`}>
        {value}
      </span>
    </div>
  )
}
