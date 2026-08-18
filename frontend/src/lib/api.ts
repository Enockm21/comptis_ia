import { checkOk, json, fetchWithAuth } from './http'

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

export const api = {
  async listIntegrations(): Promise<Integration[]> {
    const res = await fetchWithAuth(BASE)
    return json<Integration[]>(res)
  },

  async upsertIntegration(name: string, body: UpsertIntegrationBody): Promise<Integration> {
    const res = await fetchWithAuth(`${BASE}/${name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    return json<Integration>(res)
  },

  async deleteIntegration(name: string): Promise<void> {
    const res = await fetchWithAuth(`${BASE}/${name}`, { method: 'DELETE' })
    checkOk(res)
  },
}
