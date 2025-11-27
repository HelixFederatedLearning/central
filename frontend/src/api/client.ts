export const API = '/v1'

export function setToken(t: string) { localStorage.setItem('token', t) }
export function getToken(): string | null { return localStorage.getItem('token') }

export async function http<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers as any || {}) }
  const t = getToken()
  if (t) headers['Authorization'] = `Bearer ${t}`
  const res = await fetch(`${API}${path}`, { ...opts, headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
