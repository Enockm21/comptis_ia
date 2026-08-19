import { useState, useEffect } from 'react'
import { useTenant } from '../lib/TenantContext'
import { updateTenantInfo } from '../lib/tenants'

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '9px 12px',
  borderRadius: 8,
  border: '1px solid var(--border)',
  background: 'var(--bg)',
  color: 'var(--text-h)',
  fontSize: 14,
  outline: 'none',
  boxSizing: 'border-box',
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--text)',
  marginBottom: 5,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
}

const fieldStyle: React.CSSProperties = { marginBottom: 18 }

export default function Parametres() {
  const { selected: tenant, tenants, setSelected } = useTenant()

  const [form, setForm] = useState({
    siret: '',
    numero_tva: '',
    adresse: '',
    code_postal_ville: '',
  })
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (tenant) {
      setForm({
        siret: tenant.siret ?? '',
        numero_tva: tenant.numero_tva ?? '',
        adresse: tenant.adresse ?? '',
        code_postal_ville: tenant.code_postal_ville ?? '',
      })
    }
  }, [tenant?.id])

  if (!tenant) {
    return (
      <div style={{ padding: 32 }}>
        <p style={{ color: 'var(--text)', fontSize: 14 }}>Sélectionnez un dossier pour accéder aux paramètres.</p>
      </div>
    )
  }

  const handleSave = async () => {
    setSaving(true)
    setSaved(false)
    setError(null)
    try {
      const updated = await updateTenantInfo(tenant.id, {
        siret: form.siret || null,
        numero_tva: form.numero_tva || null,
        adresse: form.adresse || null,
        code_postal_ville: form.code_postal_ville || null,
      })
      // Refresh tenant in context
      const refreshed = tenants.map(t => t.id === updated.id ? updated : t)
      setSelected(refreshed.find(t => t.id === updated.id) ?? null)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch {
      setError('Erreur lors de la sauvegarde')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: '28px 32px', maxWidth: 680 }}>
      <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-h)', margin: '0 0 6px', letterSpacing: '-0.3px' }}>
        Paramètres
      </h1>
      <p style={{ fontSize: 14, color: 'var(--text)', margin: '0 0 28px' }}>
        Informations de la société — utilisées pour la génération des formulaires CA3.
      </p>

      {/* Tenant name (read-only) */}
      <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 12, padding: '16px 20px', marginBottom: 24 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 4 }}>
          Dossier actif
        </div>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-h)' }}>{tenant.name}</div>
        <div style={{ fontSize: 12, color: 'var(--text)', marginTop: 2 }}>ID : {tenant.id}</div>
      </div>

      {/* Company info form */}
      <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 12, padding: '20px 24px' }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-h)', margin: '0 0 20px', letterSpacing: '-0.2px' }}>
          Informations société
        </h2>

        <div style={fieldStyle}>
          <label style={labelStyle}>Numéro SIRET</label>
          <input
            style={inputStyle}
            value={form.siret}
            onChange={e => setForm(f => ({ ...f, siret: e.target.value }))}
            placeholder="480 013 069 00020"
            maxLength={20}
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>N° TVA intracommunautaire</label>
          <input
            style={inputStyle}
            value={form.numero_tva}
            onChange={e => setForm(f => ({ ...f, numero_tva: e.target.value }))}
            placeholder="FR 14 480 013 069"
            maxLength={20}
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Adresse</label>
          <input
            style={inputStyle}
            value={form.adresse}
            onChange={e => setForm(f => ({ ...f, adresse: e.target.value }))}
            placeholder="102 RUE DU LAC, IMMEUBLE LES ERABLES"
            maxLength={255}
          />
        </div>

        <div style={fieldStyle}>
          <label style={labelStyle}>Code postal et ville</label>
          <input
            style={inputStyle}
            value={form.code_postal_ville}
            onChange={e => setForm(f => ({ ...f, code_postal_ville: e.target.value }))}
            placeholder="31670 LABEGE"
            maxLength={100}
          />
        </div>

        {error && (
          <p style={{ color: '#ef4444', fontSize: 13, margin: '0 0 12px' }}>{error}</p>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 8 }}>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              padding: '9px 20px',
              borderRadius: 9,
              border: 'none',
              background: 'linear-gradient(135deg, #aa3bff, #7c3aed)',
              color: '#fff',
              fontSize: 14,
              fontWeight: 600,
              cursor: saving ? 'default' : 'pointer',
              opacity: saving ? 0.7 : 1,
            }}
          >
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </button>
          {saved && (
            <span style={{ fontSize: 13, color: '#10b981', fontWeight: 500 }}>
              ✓ Sauvegardé
            </span>
          )}
        </div>
      </div>

      {/* Preview for CA3 */}
      {(form.siret || form.numero_tva) && (
        <div style={{ background: 'var(--card-bg)', border: '1px solid var(--border)', borderRadius: 12, padding: '16px 20px', marginTop: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>
            Apercu CA3
          </div>
          <div style={{ fontFamily: 'monospace', fontSize: 13, color: 'var(--text-h)', lineHeight: 1.8 }}>
            <div style={{ fontWeight: 700 }}>{tenant.name}</div>
            {form.adresse && <div>{form.adresse}</div>}
            {form.code_postal_ville && <div>{form.code_postal_ville}</div>}
            {form.siret && <div style={{ marginTop: 6 }}>SIRET : {form.siret}</div>}
            {form.numero_tva && <div>TVA : {form.numero_tva}</div>}
          </div>
        </div>
      )}
    </div>
  )
}
