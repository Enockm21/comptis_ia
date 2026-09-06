import { useEffect, useState } from 'react'
import { authHeaders } from '../lib/auth'
import { cn } from '@/lib/utils'

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

const STATUS_MAP: Record<string, { classes: string; label: string }> = {
  active:   { classes: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400', label: 'Actif' },
  inactive: { classes: 'bg-[var(--code-bg)] text-[var(--text)]', label: 'Inactif' },
  error:    { classes: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400', label: 'Erreur' },
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
    <div className="px-9 py-8 max-w-[900px]">
      <div className="mb-8">
        <h1 className="text-[22px] font-bold text-[var(--text-h)] m-0 mb-1 tracking-[-0.4px]">Intégrations</h1>
        <p className="text-[14px] text-[var(--text)] m-0">Connexions aux sources de données comptables</p>
      </div>

      {/* PNICompta card */}
      <div className="mb-6">
        <h2 className="text-[15px] font-semibold text-[var(--text-h)] m-0 mb-3.5">Sources connectées</h2>
        <div className="border border-[var(--border)] rounded-[14px] overflow-hidden bg-[var(--card-bg)]">
          <div className="flex items-center gap-4 px-5 py-4.5">
            <div className="w-11 h-11 rounded-[10px] bg-blue-50 border border-blue-200 flex items-center justify-center shrink-0 dark:bg-blue-900/20 dark:border-blue-800">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <rect x="2" y="3" width="20" height="14" rx="2" stroke="#3b82f6" strokeWidth="2"/>
                <path d="M8 21h8M12 17v4" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </div>
            <div className="flex-1">
              <p className="m-0 font-semibold text-[var(--text-h)] text-[14px]">PNICompta</p>
              <p className="m-0 text-[12px] text-[var(--text)]">Logiciel de comptabilité — factures, transactions</p>
            </div>
            <span className="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400">
              Connecté
            </span>
          </div>
        </div>
      </div>

      {/* Dynamic integrations */}
      {!loading && integrations.length > 0 && (
        <div className="mb-6">
          <h2 className="text-[15px] font-semibold text-[var(--text-h)] m-0 mb-3.5">Autres intégrations</h2>
          <div className="border border-[var(--border)] rounded-[14px] overflow-hidden">
            {integrations.map((intg, i) => {
              const s = STATUS_MAP[intg.status] ?? STATUS_MAP.inactive
              return (
                <div
                  key={intg.id}
                  className={cn(
                    'flex items-center gap-4 px-5 py-4 bg-[var(--card-bg)]',
                    i < integrations.length - 1 && 'border-b border-[var(--border)]'
                  )}
                >
                  <div className="flex-1">
                    <p className="m-0 font-semibold text-[var(--text-h)] text-[14px]">{intg.name}</p>
                    <p className="m-0 text-[12px] text-[var(--text)]">{intg.type}</p>
                  </div>
                  {intg.last_sync && (
                    <span className="text-[12px] text-[var(--text)]">
                      Sync : {new Date(intg.last_sync).toLocaleDateString('fr-FR')}
                    </span>
                  )}
                  <span className={cn('px-2.5 py-1 rounded-full text-[11px] font-semibold', s.classes)}>
                    {s.label}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Coming soon */}
      <div className="mt-8">
        <h2 className="text-[15px] font-semibold text-[var(--text-h)] m-0 mb-3.5">Prochainement</h2>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
          {['Sage 50', 'QuickBooks', 'Pennylane', 'FEC import', 'API REST publique'].map(name => (
            <div
              key={name}
              className="border border-dashed border-[var(--border)] rounded-xl px-5 py-4 bg-[var(--card-bg)] opacity-60"
            >
              <p className="m-0 font-semibold text-[var(--text-h)] text-[13px]">{name}</p>
              <p className="mt-1 m-0 text-[11px] text-[var(--text)]">Bientôt disponible</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
