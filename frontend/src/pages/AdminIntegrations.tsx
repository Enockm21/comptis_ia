import { useEffect, useState } from 'react'
import { api, type Integration, type UpsertIntegrationBody } from '../lib/api'
import IntegrationForm from '../components/IntegrationForm'

export default function AdminIntegrations() {
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [error, setError] = useState<string | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [editingName, setEditingName] = useState<string | null>(null)

  const load = async () => {
    try {
      const items = await api.listIntegrations()
      setIntegrations(items)
      setError(null)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erreur de chargement')
    }
  }

  useEffect(() => { void load() }, [])

  const handleSave = async (name: string, body: UpsertIntegrationBody) => {
    await api.upsertIntegration(name, body)
    setShowForm(false)
    setEditingName(null)
    await load()
  }

  const handleDelete = async (name: string) => {
    if (!confirm(`Supprimer l'intégration "${name}" ?`)) return
    await api.deleteIntegration(name)
    await load()
  }

  return (
    <div style={{ maxWidth: 800, margin: '40px auto', padding: 24 }}>
      <h1>Intégrations</h1>
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {integrations.map(integ => (
        <div key={integ.name} style={{ border: '1px solid #ddd', padding: 16, marginBottom: 12, borderRadius: 8 }}>
          {editingName === integ.name ? (
            <IntegrationForm
              initialName={integ.name}
              onSave={handleSave}
              onCancel={() => setEditingName(null)}
            />
          ) : (
            <>
              <h3>{integ.name}</h3>
              <p>API URL : {integ.api_url ?? '—'}</p>
              <p>MCP URL : {integ.mcp_url ?? '—'}</p>
              <p>Token : {integ.token_set ? '●●●●●●●● (défini)' : 'non défini'}</p>
              <button onClick={() => setEditingName(integ.name)}>Modifier</button>
              <button onClick={() => void handleDelete(integ.name)} style={{ marginLeft: 8, color: 'red' }}>
                Supprimer
              </button>
            </>
          )}
        </div>
      ))}

      {showForm ? (
        <IntegrationForm onSave={handleSave} onCancel={() => setShowForm(false)} />
      ) : (
        <button onClick={() => setShowForm(true)}>+ Nouvelle intégration</button>
      )}
    </div>
  )
}
