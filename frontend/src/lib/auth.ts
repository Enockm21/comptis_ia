export function getToken(): string | null {
  return localStorage.getItem('comptis_token')
}

export function setToken(token: string): void {
  localStorage.setItem('comptis_token', token)
}

function getRefreshToken(): string | null {
  return localStorage.getItem('comptis_refresh_token')
}

function setRefreshToken(token: string): void {
  localStorage.setItem('comptis_refresh_token', token)
}

export function clearToken(): void {
  localStorage.removeItem('comptis_token')
  localStorage.removeItem('comptis_refresh_token')
}

export function authHeaders(): HeadersInit {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function tryRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false
  try {
    const res = await fetch('/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!res.ok) return false
    const body = (await res.json()) as { access_token: string }
    setToken(body.access_token)
    return true
  } catch {
    return false
  }
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as { detail?: { message?: string } })?.detail?.message ?? `HTTP ${res.status}`)
  }
  const body = (await res.json()) as { access_token: string; refresh_token?: string }
  setToken(body.access_token)
  if (body.refresh_token) setRefreshToken(body.refresh_token)
}
