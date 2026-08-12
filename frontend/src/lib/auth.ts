export function getToken(): string | null {
  return localStorage.getItem('comptis_token')
}

export function setToken(token: string): void {
  localStorage.setItem('comptis_token', token)
}

export function authHeaders(): HeadersInit {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}
