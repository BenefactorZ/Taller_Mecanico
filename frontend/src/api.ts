import { auth } from './auth'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  const token = auth.token()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail ?? 'No fue posible completar la operación')
  return data as T
}
