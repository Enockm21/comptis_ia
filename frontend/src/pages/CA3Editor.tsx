import { useState } from 'react'
import { useTenant } from '../lib/TenantContext'
import { fetchWithAuth } from '../lib/http'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// ── Types ──────────────────────────────────────────────────────────────────

interface CA3Data {
  tenant_id: string
  periode_debut: string
  periode_fin: string
  raison_sociale: string
  adresse: string
  code_postal_ville: string
  siret: string
  numero_tva: string
  a1_ventes: string
  l08_base: string
  l08_taxe: string
  l09_base: string
  l09_taxe: string
  l9b_base: string
  l9b_taxe: string
  l16_brute: string
  l19_immos: string
  l20_autres: string
  l22_report: string
  l23_total_ded: string
  tva_due: string
  credit_tva: string
}

// ── Helpers ────────────────────────────────────────────────────────────────

function monthStart(m: string) { return m + '-01' }
function monthEnd(m: string) {
  const [y, mo] = m.split('-').map(Number)
  return new Date(y, mo, 0).toISOString().slice(0, 10)
}

function recompute(d: CA3Data): CA3Data {
  const l16 = (parseFloat(d.l08_taxe) || 0) + (parseFloat(d.l9b_taxe) || 0) + (parseFloat(d.l09_taxe) || 0)
  const l23 = (parseFloat(d.l19_immos) || 0) + (parseFloat(d.l20_autres) || 0) + (parseFloat(d.l22_report) || 0)
  const due = Math.max(0, l16 - l23)
  const credit = Math.max(0, l23 - l16)
  return {
    ...d,
    l16_brute: l16.toFixed(2),
    l23_total_ded: l23.toFixed(2),
    tva_due: due.toFixed(2),
    credit_tva: credit.toFixed(2),
  }
}

// ── Component ──────────────────────────────────────────────────────────────

export default function CA3Editor() {
  const { selected: tenant } = useTenant()
  const [month, setMonth] = useState(() => {
    const d = new Date(); d.setMonth(d.getMonth() - 1)
    return d.toISOString().slice(0, 7)
  })
  const [form, setForm] = useState<CA3Data | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  if (!tenant) return (
    <div className="p-8 text-[var(--text)] text-[14px]">Sélectionnez un dossier.</div>
  )

  const set = (field: keyof CA3Data, val: string) =>
    setForm(f => f ? recompute({ ...f, [field]: val }) : null)

  const handleLoad = async () => {
    setLoading(true); setMsg(null)
    try {
      const params = new URLSearchParams({
        tenant_id: tenant.id,
        date_debut: monthStart(month),
        date_fin: monthEnd(month),
      })
      const res = await fetchWithAuth(`/tva/ca3-compute?${params}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      const d: CA3Data = {
        tenant_id: tenant.id,
        periode_debut: json.periode_debut,
        periode_fin: json.periode_fin,
        raison_sociale: json.raison_sociale || '',
        adresse: json.adresse || '',
        code_postal_ville: json.code_postal_ville || '',
        siret: json.siret || '',
        numero_tva: json.numero_tva || '',
        a1_ventes: String(json.a1_ventes || 0),
        l08_base: String(json.l08_base || 0),
        l08_taxe: String(json.l08_taxe || 0),
        l09_base: String(json.l09_base || 0),
        l09_taxe: String(json.l09_taxe || 0),
        l9b_base: String(json.l9b_base || 0),
        l9b_taxe: String(json.l9b_taxe || 0),
        l16_brute: String(json.l16_brute || 0),
        l19_immos: String(json.l19_immos || 0),
        l20_autres: String(json.l20_autres || 0),
        l22_report: String(json.l22_report || 0),
        l23_total_ded: String(json.l23_total_ded || 0),
        tva_due: String(json.tva_due || 0),
        credit_tva: String(json.credit_tva || 0),
      }
      setForm(d)
      await generatePdf(d)
    } catch (e: unknown) {
      setMsg('Erreur : ' + (e instanceof Error ? e.message : String(e)))
    } finally {
      setLoading(false)
    }
  }

  const generatePdf = async (data?: CA3Data) => {
    const d = data || form
    if (!d) return
    setLoading(true)
    try {
      const res = await fetchWithAuth('/tva/ca3-fill', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(d),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      if (pdfUrl) URL.revokeObjectURL(pdfUrl)
      setPdfUrl(url)
    } catch (e: unknown) {
      setMsg('Erreur PDF : ' + (e instanceof Error ? e.message : String(e)))
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!form) return
    setSaving(true); setSaved(false); setMsg(null)
    try {
      const res = await fetchWithAuth('/tva/ca3-declarations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (e: unknown) {
      setMsg('Erreur sauvegarde : ' + (e instanceof Error ? e.message : String(e)))
    } finally {
      setSaving(false)
    }
  }

  const handleDownload = async () => {
    await generatePdf()
    if (pdfUrl) {
      const a = document.createElement('a')
      a.href = pdfUrl
      a.download = `CA3_${month}.pdf`
      a.click()
    }
  }

  // Shared input classes
  const inputCls = 'flex-1 px-2 py-1.5 rounded-md border border-[var(--border)] bg-[var(--bg)] text-[var(--text-h)] text-[13px] outline-none min-w-0'
  const inputROCls = cn(inputCls, 'bg-[var(--code-bg)] font-semibold')
  const labelCls = 'text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.04em] w-[130px] shrink-0 flex items-center'

  const Field = ({ label, field, readOnly = false }: { label: string; field: keyof CA3Data; readOnly?: boolean }) => (
    <div className="flex gap-2 mb-2">
      <span className={labelCls}>{label}</span>
      <input
        className={readOnly ? inputROCls : inputCls}
        value={form?.[field] ?? ''}
        readOnly={readOnly}
        onChange={e => set(field, e.target.value)}
      />
    </div>
  )

  const SectionTitle = ({ children }: { children: string }) => (
    <p className="text-[11px] font-bold text-[#7c3aed] uppercase tracking-[0.06em] mt-3.5 mb-2 border-b border-[var(--border)] pb-1">
      {children}
    </p>
  )

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Left: PDF viewer ─────────────────────────────────────── */}
      <div className="flex-1 bg-[#404040] flex flex-col min-w-0">
        {pdfUrl ? (
          <iframe
            src={pdfUrl + '#toolbar=0'}
            className="flex-1 border-none w-full"
            title="CA3 PDF"
          />
        ) : (
          <div className="flex-1 flex items-center justify-center flex-col gap-3">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" opacity={0.4}>
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="#fff" strokeWidth="1.5"/>
              <polyline points="14,2 14,8 20,8" stroke="#fff" strokeWidth="1.5"/>
            </svg>
            <p className="text-white/50 text-[13px] m-0">
              Chargez une déclaration pour voir le PDF
            </p>
          </div>
        )}
      </div>

      {/* ── Right: Form ──────────────────────────────────────────── */}
      <div className="w-[380px] shrink-0 border-l border-[var(--border)] bg-[var(--bg)] flex flex-col overflow-y-auto">

        {/* Header */}
        <div className="px-[18px] pt-4 pb-3 border-b border-[var(--border)]">
          <h2 className="text-[16px] font-bold text-[var(--text-h)] m-0 mb-2.5 tracking-[-0.2px]">
            Déclaration CA3
          </h2>
          <div className="flex gap-2 items-center">
            <input
              type="month"
              value={month}
              onChange={e => setMonth(e.target.value)}
              className={cn(inputCls, 'flex-1')}
            />
            <Button
              onClick={handleLoad}
              disabled={loading}
              size="sm"
              className="bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 hover:opacity-90 shrink-0"
            >
              {loading ? '…' : 'Charger'}
            </Button>
          </div>
        </div>

        {/* Form fields */}
        {form && (
          <div className="px-[18px] py-3 flex-1">

            <SectionTitle>Identification</SectionTitle>
            <Field label="Raison sociale" field="raison_sociale" />
            <Field label="Adresse" field="adresse" />
            <Field label="Code postal ville" field="code_postal_ville" />
            <Field label="SIRET" field="siret" />
            <Field label="N° TVA intra" field="numero_tva" />

            <SectionTitle>Période</SectionTitle>
            <div className="flex gap-2 mb-2">
              <span className={labelCls}>Début</span>
              <input type="date" className={inputCls} value={form.periode_debut}
                onChange={e => set('periode_debut', e.target.value)} />
            </div>
            <div className="flex gap-2 mb-2">
              <span className={labelCls}>Fin</span>
              <input type="date" className={inputCls} value={form.periode_fin}
                onChange={e => set('periode_fin', e.target.value)} />
            </div>

            <SectionTitle>Opérations (page 2)</SectionTitle>
            <Field label="A1 Ventes HT (0979)" field="a1_ventes" />

            <p className="mb-1.5 text-[11px] text-[var(--text)] italic">Ligne 08 – TVA 20% (0207)</p>
            <div className="flex gap-2 mb-2">
              <span className={labelCls}>Base HT</span>
              <input className={inputCls} value={form.l08_base} onChange={e => set('l08_base', e.target.value)} />
              <input className={cn(inputCls, 'flex-[0.6] bg-[var(--code-bg)]')} value={form.l08_taxe}
                onChange={e => set('l08_taxe', e.target.value)} placeholder="Taxe" />
            </div>

            <p className="mb-1.5 text-[11px] text-[var(--text)] italic">Ligne 9B – TVA 10% (0151)</p>
            <div className="flex gap-2 mb-2">
              <span className={labelCls}>Base HT</span>
              <input className={inputCls} value={form.l9b_base} onChange={e => set('l9b_base', e.target.value)} />
              <input className={cn(inputCls, 'flex-[0.6]')} value={form.l9b_taxe}
                onChange={e => set('l9b_taxe', e.target.value)} placeholder="Taxe" />
            </div>

            <p className="mb-1.5 text-[11px] text-[var(--text)] italic">Ligne 09 – TVA 5,5% (0105)</p>
            <div className="flex gap-2 mb-2">
              <span className={labelCls}>Base HT</span>
              <input className={inputCls} value={form.l09_base} onChange={e => set('l09_base', e.target.value)} />
              <input className={cn(inputCls, 'flex-[0.6]')} value={form.l09_taxe}
                onChange={e => set('l09_taxe', e.target.value)} placeholder="Taxe" />
            </div>

            <Field label="Ligne 16 TVA brute" field="l16_brute" readOnly />

            <SectionTitle>TVA déductible (page 3)</SectionTitle>
            <Field label="L19 Immos (0703)" field="l19_immos" />
            <Field label="L20 Autres (0702)" field="l20_autres" />
            <Field label="L22 Report (8001)" field="l22_report" />
            <Field label="L23 Total déduc." field="l23_total_ded" readOnly />

            <SectionTitle>Résultat</SectionTitle>
            <div className="flex gap-2 mb-2">
              <div className={cn(
                'flex-1 border border-[var(--border)] rounded-lg px-2.5 py-2',
                form.tva_due !== '0' && form.tva_due !== '0.00' ? 'bg-red-50 dark:bg-red-900/10' : 'bg-[var(--card-bg)]'
              )}>
                <div className="text-[10px] font-semibold text-[var(--text)] uppercase mb-0.5">TVA due (8900)</div>
                <div className="text-[18px] font-bold text-red-500 tabular-nums">{Number(form.tva_due).toFixed(0)} €</div>
              </div>
              <div className={cn(
                'flex-1 border border-[var(--border)] rounded-lg px-2.5 py-2',
                form.credit_tva !== '0' && form.credit_tva !== '0.00' ? 'bg-emerald-50 dark:bg-emerald-900/10' : 'bg-[var(--card-bg)]'
              )}>
                <div className="text-[10px] font-semibold text-[var(--text)] uppercase mb-0.5">Crédit TVA (0705)</div>
                <div className="text-[18px] font-bold text-emerald-600 tabular-nums">{Number(form.credit_tva).toFixed(0)} €</div>
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="px-[18px] py-3 border-t border-[var(--border)] flex flex-col gap-2">
          {msg && <p className="text-[12px] text-red-500 m-0">{msg}</p>}
          {saved && <p className="text-[12px] text-emerald-600 m-0 font-medium">✓ Déclaration sauvegardée</p>}

          {form && (
            <>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => generatePdf()}
                  disabled={loading}
                  className="flex-1 text-[12px]"
                >
                  {loading ? '…' : '⟳ Actualiser PDF'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDownload}
                  disabled={loading}
                  className="flex-1 text-[12px]"
                >
                  ↓ Télécharger
                </Button>
              </div>
              <Button
                onClick={handleSave}
                disabled={saving}
                className="w-full bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 hover:opacity-90 disabled:opacity-60"
              >
                {saving ? 'Enregistrement…' : 'Enregistrer en base'}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
