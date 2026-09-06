import { useState, useEffect } from 'react'
import { useTenant } from '../lib/TenantContext'
import { updateTenantInfo } from '../lib/tenants'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

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
      <div className="p-8 text-[var(--text)] text-[14px]">
        Sélectionnez un dossier pour accéder aux paramètres.
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
      const refreshed = tenants.map(t => t.id === updated.id ? updated : t)
      const found = refreshed.find(t => t.id === updated.id)
      if (found) setSelected(found)
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch {
      setError('Erreur lors de la sauvegarde')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="px-8 py-7 max-w-[680px]">
      <h1 className="text-[22px] font-bold text-[var(--text-h)] m-0 mb-1.5 tracking-[-0.3px]">Paramètres</h1>
      <p className="text-[14px] text-[var(--text)] m-0 mb-7">
        Informations de la société — utilisées pour la génération des formulaires CA3.
      </p>

      {/* Tenant name (read-only) */}
      <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl px-5 py-4 mb-6">
        <div className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em] mb-1">
          Dossier actif
        </div>
        <div className="text-[16px] font-bold text-[var(--text-h)]">{tenant.name}</div>
        <div className="text-[12px] text-[var(--text)] mt-0.5">ID : {tenant.id}</div>
      </div>

      {/* Company info form */}
      <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl px-6 py-5">
        <h2 className="text-[15px] font-semibold text-[var(--text-h)] m-0 mb-5 tracking-[-0.2px]">
          Informations société
        </h2>

        <div className="grid gap-4">
          <div>
            <label className="block text-[12px] font-semibold text-[var(--text)] mb-1.5 uppercase tracking-[0.05em]">
              Numéro SIRET
            </label>
            <Input
              value={form.siret}
              onChange={e => setForm(f => ({ ...f, siret: e.target.value }))}
              placeholder="480 013 069 00020"
              maxLength={20}
              className="bg-[var(--bg)] border-[var(--border)] text-[var(--text-h)]"
            />
          </div>

          <div>
            <label className="block text-[12px] font-semibold text-[var(--text)] mb-1.5 uppercase tracking-[0.05em]">
              N° TVA intracommunautaire
            </label>
            <Input
              value={form.numero_tva}
              onChange={e => setForm(f => ({ ...f, numero_tva: e.target.value }))}
              placeholder="FR 14 480 013 069"
              maxLength={20}
              className="bg-[var(--bg)] border-[var(--border)] text-[var(--text-h)]"
            />
          </div>

          <div>
            <label className="block text-[12px] font-semibold text-[var(--text)] mb-1.5 uppercase tracking-[0.05em]">
              Adresse
            </label>
            <Input
              value={form.adresse}
              onChange={e => setForm(f => ({ ...f, adresse: e.target.value }))}
              placeholder="102 RUE DU LAC, IMMEUBLE LES ERABLES"
              maxLength={255}
              className="bg-[var(--bg)] border-[var(--border)] text-[var(--text-h)]"
            />
          </div>

          <div>
            <label className="block text-[12px] font-semibold text-[var(--text)] mb-1.5 uppercase tracking-[0.05em]">
              Code postal et ville
            </label>
            <Input
              value={form.code_postal_ville}
              onChange={e => setForm(f => ({ ...f, code_postal_ville: e.target.value }))}
              placeholder="31670 LABEGE"
              maxLength={100}
              className="bg-[var(--bg)] border-[var(--border)] text-[var(--text-h)]"
            />
          </div>
        </div>

        {error && <p className="text-red-500 text-[13px] mt-4 mb-0">{error}</p>}

        <div className="flex items-center gap-3 mt-6">
          <Button
            onClick={handleSave}
            disabled={saving}
            className="bg-gradient-to-br from-[#aa3bff] to-[#7c3aed] text-white border-0 hover:opacity-90 disabled:opacity-60"
          >
            {saving ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
          {saved && (
            <span className="text-[13px] text-emerald-600 font-medium">✓ Sauvegardé</span>
          )}
        </div>
      </div>

      {/* Preview for CA3 */}
      {(form.siret || form.numero_tva) && (
        <div className="bg-[var(--card-bg)] border border-[var(--border)] rounded-xl px-5 py-4 mt-4">
          <div className="text-[11px] font-semibold text-[var(--text)] uppercase tracking-[0.05em] mb-2.5">
            Aperçu CA3
          </div>
          <div className="font-mono text-[13px] text-[var(--text-h)] leading-relaxed">
            <div className="font-bold">{tenant.name}</div>
            {form.adresse && <div>{form.adresse}</div>}
            {form.code_postal_ville && <div>{form.code_postal_ville}</div>}
            {form.siret && <div className="mt-1.5">SIRET : {form.siret}</div>}
            {form.numero_tva && <div>TVA : {form.numero_tva}</div>}
          </div>
        </div>
      )}
    </div>
  )
}
