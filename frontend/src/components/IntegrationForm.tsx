import { useState, type FormEvent } from 'react'
import { type UpsertIntegrationBody } from '../lib/api'

interface Props {
  initialName?: string
  onSave: (name: string, body: UpsertIntegrationBody) => Promise<void>
  onCancel: () => void
}

export default function IntegrationForm({ initialName, onSave, onCancel }: Props) {
  const [name, setName] = useState(initialName ?? '')
  const [apiUrl, setApiUrl] = useState('')
  const [mcpUrl, setMcpUrl] = useState('')
  const [token, setToken] = useState('')
  const [showToken, setShowToken] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await onSave(name, {
        api_url: apiUrl || null,
        mcp_url: mcpUrl || null,
        token: token || undefined,
      })
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur inconnue')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ border: '1px solid #ccc', padding: 16, borderRadius: 8 }}>
      <div>
        <label>Nom *</label>
        <input
          value={name}
          onChange={e => setName(e.target.value)}
          disabled={!!initialName}
          required
          placeholder="pnicompta"
        />
      </div>
      <div>
        <label>API URL</label>
        <input value={apiUrl} onChange={e => setApiUrl(e.target.value)} placeholder="https://host/api" />
      </div>
      <div>
        <label>MCP URL (optionnel)</label>
        <input value={mcpUrl} onChange={e => setMcpUrl(e.target.value)} placeholder="https://host/mcp" />
      </div>
      <div>
        <label>Token</label>
        <input
          type={showToken ? 'text' : 'password'}
          value={token}
          onChange={e => setToken(e.target.value)}
          placeholder="cpt_... (laisser vide pour conserver)"
        />
        <button type="button" onClick={() => setShowToken(v => !v)}>
          {showToken ? 'Masquer' : 'Afficher'}
        </button>
      </div>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      <button type="submit" disabled={saving}>{saving ? 'Sauvegarde...' : 'Sauvegarder'}</button>
      <button type="button" onClick={onCancel}>Annuler</button>
    </form>
  )
}
