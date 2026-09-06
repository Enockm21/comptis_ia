import { type ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { clearToken } from '../lib/auth'
import { useTenant } from '../lib/TenantContext'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/dashboard', label: 'Tableau de bord', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <rect x="3" y="3" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="2"/>
      <rect x="14" y="3" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="2"/>
      <rect x="3" y="14" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="2"/>
      <rect x="14" y="14" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="2"/>
    </svg>
  )},
  { to: '/rapprochement', label: 'Rapprochement', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M8 7l-5 5 5 5M16 7l5 5-5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
      <line x1="3" y1="12" x2="21" y2="12" stroke="currentColor" strokeWidth="2"/>
    </svg>
  )},
  { to: '/ecritures', label: 'Écritures', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" stroke="currentColor" strokeWidth="2"/>
      <rect x="9" y="3" width="6" height="4" rx="1" stroke="currentColor" strokeWidth="2"/>
      <line x1="9" y1="12" x2="15" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <line x1="9" y1="16" x2="13" y2="16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  )},
  { to: '/plan-comptable', label: 'Plan comptable', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" stroke="currentColor" strokeWidth="2"/>
    </svg>
  )},
  { to: '/categorisation', label: 'Catégorisation', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" stroke="currentColor" strokeWidth="2"/>
      <circle cx="7" cy="7" r="1.5" fill="currentColor"/>
    </svg>
  )},
  { to: '/tva', label: 'TVA', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M9 14l6-6M10 9h.01M15 14h.01" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeDasharray="2 3"/>
      <rect x="2" y="3" width="20" height="18" rx="2" stroke="currentColor" strokeWidth="2"/>
    </svg>
  )},
  { to: '/integrations', label: 'Intégrations', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="9" cy="12" r="3" stroke="currentColor" strokeWidth="2"/>
      <circle cx="18" cy="6" r="2" stroke="currentColor" strokeWidth="2"/>
      <circle cx="18" cy="18" r="2" stroke="currentColor" strokeWidth="2"/>
      <line x1="12" y1="10.5" x2="16.5" y2="7" stroke="currentColor" strokeWidth="2"/>
      <line x1="12" y1="13.5" x2="16.5" y2="17" stroke="currentColor" strokeWidth="2"/>
    </svg>
  )},
  { to: '/ca3', label: 'Déclaration CA3', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="currentColor" strokeWidth="2"/>
      <polyline points="14,2 14,8 20,8" stroke="currentColor" strokeWidth="2"/>
      <line x1="8" y1="13" x2="16" y2="13" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
      <line x1="8" y1="17" x2="12" y2="17" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
    </svg>
  )},
  { to: '/parametres', label: 'Paramètres', icon: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2"/>
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" stroke="currentColor" strokeWidth="2"/>
    </svg>
  )},
]

export default function Shell({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const { tenants, selected, setSelected } = useTenant()

  const handleLogout = () => {
    clearToken()
    navigate('/login')
  }

  return (
    <div className="flex min-h-svh bg-[var(--bg)]">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 border-r border-[var(--border)] flex flex-col sticky top-0 h-svh overflow-y-auto">

        {/* Logo */}
        <div className="flex items-center gap-2.5 px-5 py-[18px] border-b border-[var(--border)]">
          <div className="w-8 h-8 rounded-[9px] bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] flex items-center justify-center shrink-0 shadow-[0_2px_8px_rgba(170,59,255,0.3)]">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M9 7H6a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-3" stroke="#fff" strokeWidth="2.5" strokeLinecap="round"/>
              <path d="M15 3h6v6M10 14 21 3" stroke="#fff" strokeWidth="2.5" strokeLinecap="round"/>
            </svg>
          </div>
          <span className="font-bold text-[17px] text-[var(--text-h)] tracking-[-0.3px]">
            Comptis
          </span>
        </div>

        {/* Tenant selector */}
        {tenants.length > 0 && (
          <div className="px-4 py-3.5 border-b border-[var(--border)]">
            <p className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.08em] mb-2">
              Client actif
            </p>
            <select
              value={selected?.id ?? ''}
              onChange={e => {
                const t = tenants.find(x => x.id === e.target.value)
                if (t) setSelected(t)
              }}
              className="w-full px-2.5 py-1.5 rounded-lg border border-[var(--border)] bg-[var(--code-bg)] text-[var(--text-h)] text-[13px] font-medium cursor-pointer outline-none"
            >
              {tenants.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 p-2.5">
          {NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => cn(
                'flex items-center gap-2.5 px-3 py-2.5 rounded-lg mb-0.5 no-underline text-[14px] transition-[background,color] duration-100',
                isActive
                  ? 'font-semibold text-[var(--accent)] bg-[var(--accent-bg)]'
                  : 'font-normal text-[var(--text)] hover:bg-[var(--code-bg)]'
              )}
            >
              <span className="shrink-0 opacity-85">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Logout */}
        <div className="px-3.5 py-3 border-t border-[var(--border)]">
          <button
            onClick={handleLogout}
            className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-transparent text-[var(--text)] text-[13px] font-medium cursor-pointer flex items-center gap-2 transition-[background] duration-100 hover:bg-[var(--code-bg)]"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <polyline points="16,17 21,12 16,7" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <line x1="21" y1="12" x2="9" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            Déconnexion
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto min-w-0">
        {children}
      </main>
    </div>
  )
}
