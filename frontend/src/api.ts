import { auth } from './auth'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'
const FALLBACK_ERROR = 'No fue posible completar la operación'

// FastAPI devuelve un texto en errores de negocio y una lista de detalles en errores de validación (422)
function errorMessage(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    const message = (detail[0] as { msg?: string }).msg
    if (message) return message.replace(/^Value error, /, '')
  }
  return FALLBACK_ERROR
}

/** Descarga un archivo protegido (p. ej. la foto de un taller): el navegador no puede mandar el token en un <img>, así que se pide aquí. */
/** Error de la API: además del mensaje trae el estado HTTP y, si la regla lo informa, su código (COINCIDENCIA, CLIENTE_SUSPENDIDO…). */
export class ApiError extends Error {
  constructor(message: string, readonly status: number, readonly codigo?: string) { super(message) }
}

export async function apiBlob(path: string): Promise<Blob> {
  const token = auth.token()
  let response: Response
  try { response = await fetch(`${BASE_URL}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} }) }
  catch { throw new Error('No hay conexión con el servidor. Verifique que la API esté en ejecución.') }
  if (!response.ok) throw new Error(FALLBACK_ERROR)
  return response.blob()
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  // Con FormData (subida de archivos) el navegador fija el Content-Type con su boundary; no se debe forzar
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const token = auth.token()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  let response: Response
  try {
    response = await fetch(`${BASE_URL}${path}`, { ...options, headers })
  } catch {
    throw new Error('No hay conexión con el servidor. Verifique que la API esté en ejecución.')
  }
  const data = await response.json().catch(() => ({}))
  if (response.status === 401 && token) {
    auth.clear()
    window.location.assign('/ingresar')
  }
  if (!response.ok) throw new ApiError(errorMessage(data.detail), response.status, typeof data.codigo === 'string' ? data.codigo : undefined)
  return data as T
}
