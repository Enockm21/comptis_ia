import { authHeaders } from './auth'

export interface Integration {
  name: string
  api_url: string | null
  mcp_url: string | null
  token_set: boolean
  updated_at: string
}

export interface UpsertIntegrationBody {
  api_url?: string | null
  mcp_url?: string | null
  token?: string | null
}

const BASE = '/admin/integrations'

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: { message?: string } })?.detail?.message ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  async listIntegrations(): Promise<Integration[]> {
    const res = await fetch(BASE, { headers: authHeaders() })
    return json<Integration[]>(res)
  },

  async upsertIntegration(name: string, body: UpsertIntegrationBody): Promise<Integration> {
    const res = await fetch(`${BASE}/${name}`, {
      method: 'PUT',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return json<Integration>(res)
  },

  async deleteIntegration(name: string): Promise<void> {
    const res = await fetch(`${BASE}/${name}`, {
      method: 'DELETE',
      headers: authHeaders(),
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
  },
}
