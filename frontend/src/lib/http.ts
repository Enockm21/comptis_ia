import { clearToken } from './auth'

function handleUnauthorized(): void {
  clearToken()
  if (window.location.pathname !== '/login') {
    window.location.href = '/login'
  }
}

export async function json<T>(res: Response): Promise<T> {
  if (res.status === 401) handleUnauthorized()
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: { message?: string } })?.detail?.message ?? `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export function checkOk(res: Response): void {
  if (res.status === 401) handleUnauthorized()
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}
