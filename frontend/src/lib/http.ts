import { clearToken, tryRefresh, authHeaders } from './auth'

let _refreshing: Promise<boolean> | null = null

async function handleUnauthorized(retryFn?: () => Promise<Response>): Promise<Response | null> {
  // Deduplicate concurrent refresh calls
  if (!_refreshing) _refreshing = tryRefresh().finally(() => { _refreshing = null })
  const refreshed = await _refreshing
  if (refreshed && retryFn) return retryFn()
  clearToken()
  if (window.location.pathname !== '/login') window.location.href = '/login'
  return null
}

export async function json<T>(res: Response, retryFn?: () => Promise<Response>): Promise<T> {
  if (res.status === 401) {
    const retried = await handleUnauthorized(retryFn)
    if (retried) return json<T>(retried)
    throw new Error('Session expirée')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: { message?: string } })?.detail?.message ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function checkOk(res: Response): void {
  if (res.status === 401) {
    handleUnauthorized()
    throw new Error('Session expirée')
  }
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export function fetchWithAuth(url: string, init: RequestInit = {}): Promise<Response> {
  const doFetch = () => fetch(url, { ...init, headers: { ...authHeaders(), ...(init.headers ?? {}) } })
  return doFetch().then(res => {
    if (res.status !== 401) return res
    return handleUnauthorized(doFetch).then(r => r ?? res)
  })
}
