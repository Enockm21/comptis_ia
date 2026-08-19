import { useState } from 'react'
import { useTenant } from '../lib/TenantContext'
import { fetchWithAuth } from '../lib/http'

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

const EMPTY = (tenantId: string): CA3Data => ({
  tenant_id: tenantId,
  periode_debut: '',
  periode_fin: '',
  raison_sociale: '',
  adresse: '',
  code_postal_ville: '',
  siret: '',
  numero_tva: '',
  a1_ventes: '0',
  l08_base: '0', l08_taxe: '0',
  l09_base: '0', l09_taxe: '0',
  l9b_base: '0', l9b_taxe: '0',
  l16_brute: '0',
  l19_immos: '0',
  l20_autres: '0',
  l22_report: '0',
  l23_total_ded: '0',
  tva_due: '0',
  credit_tva: '0',
})

// ── Styles ─────────────────────────────────────────────────────────────────

const fieldRow: React.CSSProperties = { display: 'flex', gap: 8, marginBottom: 8 }

const inputSm: React.CSSProperties = {
  flex: 1, padding: '5px 8px', borderRadius: 6,
  border: '1px solid var(--border)', background: 'var(--bg)',
  color: 'var(--text-h)', fontSize: 13, outline: 'none',
}

const labelSm: React.CSSProperties = {
  fontSize: 11, fontWeight: 600, color: 'var(--text)',
  textTransform: 'uppercase', letterSpacing: '0.04em',
  width: 130, flexShrink: 0, display: 'flex', alignItems: 'center',
}

const sectionTitle: React.CSSProperties = {
  fontSize: 11, fontWeight: 700, color: '#7c3aed',
  textTransform: 'uppercase', letterSpacing: '0.06em',
  margin: '14px 0 8px', borderBottom: '1px solid var(--border)', paddingBottom: 4,
}

const btn = (primary = false): React.CSSProperties => ({
  padding: '8px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
  fontSize: 13, fontWeight: 600,
  background: primary ? 'linear-gradient(135deg,#aa3bff,#7c3aed)' : 'var(--card-bg)',
  color: primary ? '#fff' : 'var(--text-h)',
  border: primary ? 'none' : '1px solid var(--border)',
})

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
    <div style={{ padding: 32 }}>
      <p style={{ color: 'var(--text)', fontSize: 14 }}>Sélectionnez un dossier.</p>
    </div>
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
      // Stringify all numeric fields
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
      // Auto-preview
      await generatePdf(d)
    } catch (e: any) {
      setMsg('Erreur : ' + e.message)
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
    } catch (e: any) {
      setMsg('Erreur PDF : ' + e.message)
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
    } catch (e: any) {
      setMsg('Erreur sauvegarde : ' + e.message)
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

  const Field = ({ label, field, readOnly = false }: { label: string; field: keyof CA3Data; readOnly?: boolean }) => (
    <div style={fieldRow}>
      <span style={labelSm}>{label}</span>
      <input
        style={{ ...inputSm, background: readOnly ? 'var(--code-bg)' : 'var(--bg)', fontWeight: readOnly ? 600 : 400 }}
        value={form?.[field] ?? ''}
        readOnly={readOnly}
        onChange={e => set(field, e.target.value)}
      />
    </div>
  )

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      {/* ── Left: PDF viewer ─────────────────────────────────────── */}
      <div style={{ flex: 1, background: '#404040', display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {pdfUrl ? (
          <iframe
            src={pdfUrl + '#toolbar=0'}
            style={{ flex: 1, border: 'none', width: '100%' }}
            title="CA3 PDF"
          />
        ) : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 12 }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" opacity={0.4}>
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="#fff" strokeWidth="1.5"/>
              <polyline points="14,2 14,8 20,8" stroke="#fff" strokeWidth="1.5"/>
            </svg>
            <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: 13 }}>
              Chargez une déclaration pour voir le PDF
            </p>
          </div>
        )}
      </div>

      {/* ── Right: Form ──────────────────────────────────────────── */}
      <div style={{
        width: 380, flexShrink: 0, borderLeft: '1px solid var(--border)',
        background: 'var(--bg)', display: 'flex', flexDirection: 'column',
        overflowY: 'auto',
      }}>
        {/* Header */}
        <div style={{ padding: '16px 18px 12px', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-h)', margin: '0 0 10px', letterSpacing: '-0.2px' }}>
            Déclaration CA3
          </h2>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              type="month"
              value={month}
              onChange={e => setMonth(e.target.value)}
              style={{ ...inputSm, flex: 1 }}
            />
            <button onClick={handleLoad} disabled={loading} style={btn(true)}>
              {loading ? '…' : 'Charger'}
            </button>
          </div>
        </div>

        {/* Form fields */}
        {form && (
          <div style={{ padding: '12px 18px', flex: 1 }}>

            <p style={sectionTitle}>Identification</p>
            <Field label="Raison sociale" field="raison_sociale" />
            <Field label="Adresse" field="adresse" />
            <Field label="Code postal ville" field="code_postal_ville" />
            <Field label="SIRET" field="siret" />
            <Field label="N° TVA intra" field="numero_tva" />

            <p style={sectionTitle}>Période</p>
            <div style={fieldRow}>
              <span style={labelSm}>Début</span>
              <input type="date" style={inputSm} value={form.periode_debut}
                onChange={e => set('periode_debut', e.target.value)} />
            </div>
            <div style={fieldRow}>
              <span style={labelSm}>Fin</span>
              <input type="date" style={inputSm} value={form.periode_fin}
                onChange={e => set('periode_fin', e.target.value)} />
            </div>

            <p style={sectionTitle}>Opérations (page 2)</p>
            <Field label="A1 Ventes HT (0979)" field="a1_ventes" />
            <div style={{ marginBottom: 6, fontSize: 11, color: 'var(--text)', fontStyle: 'italic' }}>
              Ligne 08 – TVA 20% (0207)
            </div>
            <div style={fieldRow}>
              <span style={labelSm}>Base HT</span>
              <input style={inputSm} value={form.l08_base} onChange={e => set('l08_base', e.target.value)} />
              <input style={{ ...inputSm, flex: 0.6, background: 'var(--code-bg)' }} value={form.l08_taxe}
                onChange={e => set('l08_taxe', e.target.value)} placeholder="Taxe" />
            </div>
            <div style={{ marginBottom: 6, fontSize: 11, color: 'var(--text)', fontStyle: 'italic' }}>
              Ligne 9B – TVA 10% (0151)
            </div>
            <div style={fieldRow}>
              <span style={labelSm}>Base HT</span>
              <input style={inputSm} value={form.l9b_base} onChange={e => set('l9b_base', e.target.value)} />
              <input style={{ ...inputSm, flex: 0.6 }} value={form.l9b_taxe}
                onChange={e => set('l9b_taxe', e.target.value)} placeholder="Taxe" />
            </div>
            <div style={{ marginBottom: 6, fontSize: 11, color: 'var(--text)', fontStyle: 'italic' }}>
              Ligne 09 – TVA 5,5% (0105)
            </div>
            <div style={fieldRow}>
              <span style={labelSm}>Base HT</span>
              <input style={inputSm} value={form.l09_base} onChange={e => set('l09_base', e.target.value)} />
              <input style={{ ...inputSm, flex: 0.6 }} value={form.l09_taxe}
                onChange={e => set('l09_taxe', e.target.value)} placeholder="Taxe" />
            </div>
            <Field label="Ligne 16 TVA brute" field="l16_brute" readOnly />

            <p style={sectionTitle}>TVA déductible (page 3)</p>
            <Field label="L19 Immos (0703)" field="l19_immos" />
            <Field label="L20 Autres (0702)" field="l20_autres" />
            <Field label="L22 Report (8001)" field="l22_report" />
            <Field label="L23 Total déduc." field="l23_total_ded" readOnly />

            <p style={sectionTitle}>Résultat</p>
            <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
              <div style={{ flex: 1, background: form.tva_due !== '0' && form.tva_due !== '0.00' ? '#fff3f3' : 'var(--card-bg)',
                border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px' }}>
                <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text)', textTransform: 'uppercase', marginBottom: 2 }}>TVA due (8900)</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#ef4444' }}>{Number(form.tva_due).toFixed(0)} €</div>
              </div>
              <div style={{ flex: 1, background: form.credit_tva !== '0' && form.credit_tva !== '0.00' ? '#f0fdf4' : 'var(--card-bg)',
                border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px' }}>
                <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--text)', textTransform: 'uppercase', marginBottom: 2 }}>Crédit TVA (0705)</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#10b981' }}>{Number(form.credit_tva).toFixed(0)} €</div>
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        <div style={{ padding: '12px 18px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {msg && <p style={{ fontSize: 12, color: '#ef4444', margin: 0 }}>{msg}</p>}
          {saved && <p style={{ fontSize: 12, color: '#10b981', margin: 0 }}>✓ Déclaration sauvegardée</p>}

          {form && (
            <>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => generatePdf()} disabled={loading} style={{ ...btn(false), flex: 1, fontSize: 12 }}>
                  {loading ? '…' : '⟳ Actualiser PDF'}
                </button>
                <button onClick={handleDownload} disabled={loading} style={{ ...btn(false), flex: 1, fontSize: 12 }}>
                  ↓ Télécharger
                </button>
              </div>
              <button onClick={handleSave} disabled={saving} style={btn(true)}>
                {saving ? 'Enregistrement…' : 'Enregistrer en base'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
