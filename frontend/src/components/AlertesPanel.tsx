import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTenant } from '../lib/TenantContext'
import { fetchWithAuth } from '../lib/http'
import { cn } from '@/lib/utils'

interface Alerte {
  type: string
  titre: string
  detail: string
  priorite: string
  action_url: string
}

export default function AlertesPanel() {
  const { selected } = useTenant()
  const navigate = useNavigate()
  const [alertes, setAlertes] = useState<Alerte[]>([])
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!selected) return
    fetchWithAuth(`/alertes?tenant_id=${selected.id}`)
      .then(r => r.ok ? r.json() : [])
      .then(setAlertes)
      .catch(() => {})
  }, [selected])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const haute = alertes.filter(a => a.priorite === 'haute').length
  const total = alertes.length

  if (total === 0) return null

  return (
    <div ref={ref} className="relative px-2.5 mb-1">
      <button
        onClick={() => setOpen(o => !o)}
        className={cn(
          'w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-[13px] transition-colors',
          open ? 'bg-[var(--code-bg)]' : 'hover:bg-[var(--code-bg)]',
          haute > 0 ? 'text-amber-600 dark:text-amber-400' : 'text-[var(--text)]'
        )}
      >
        <span className="relative shrink-0">
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" stroke="currentColor" strokeWidth="2"/>
            <path d="M13.73 21a2 2 0 0 1-3.46 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          {total > 0 && (
            <span className={cn(
              'absolute -top-1 -right-1 w-4 h-4 rounded-full text-[9px] font-bold flex items-center justify-center text-white leading-none',
              haute > 0 ? 'bg-amber-500' : 'bg-[var(--accent)]'
            )}>
              {total > 9 ? '9+' : total}
            </span>
          )}
        </span>
        <span className="font-medium">Alertes</span>
      </button>

      {open && (
        <div className="absolute left-full top-0 ml-2 w-[300px] bg-[var(--card-bg)] border border-[var(--border)] rounded-xl shadow-lg z-50 overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--border)]">
            <p className="m-0 text-[12px] font-semibold text-[var(--text)] uppercase tracking-[0.05em]">
              {total} alerte{total > 1 ? 's' : ''}
            </p>
          </div>
          <div className="divide-y divide-[var(--border)] max-h-72 overflow-y-auto">
            {alertes.map((a, i) => (
              <button
                key={i}
                onClick={() => { setOpen(false); navigate(a.action_url) }}
                className="w-full text-left px-4 py-3 hover:bg-[var(--code-bg)] transition-colors"
              >
                <div className="flex items-start gap-2">
                  <span className={cn(
                    'w-2 h-2 rounded-full shrink-0 mt-1.5',
                    a.priorite === 'haute' ? 'bg-amber-500' : 'bg-[var(--accent)]'
                  )} />
                  <div>
                    <p className="m-0 text-[12px] font-semibold text-[var(--text-h)]">{a.titre}</p>
                    <p className="m-0 text-[11px] text-[var(--text)] mt-0.5 leading-relaxed">{a.detail}</p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
