// Reglas de formato del cliente: reflejan las del servidor (backend/app/customers/normalizacion.py). El servidor es la autoridad.
const CORREO = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

export const limpiarNombre = (valor: string) => valor.split(/\s+/).filter(Boolean).join(' ')

export function normalizarContacto(valor: string): string {
  const texto = valor.trim()
  return texto.includes('@') ? texto.toLowerCase() : texto.replace(/[\s().-]/g, '')
}

export const esContacto = (valor: string) => valor.includes('@') || /^\+?[\d\s().-]{7,}$/.test(valor.trim())

export function validarNombre(valor: string): true | string {
  const nombre = limpiarNombre(valor)
  if (nombre.length > 140) return 'Use hasta 140 caracteres'
  return nombre.split(' ').length >= 2 && nombre.length >= 3 ? true : 'Ingrese el nombre completo (nombre y apellido)'
}

/** Teléfono sin espacios, paréntesis, puntos ni guiones (se conserva un + inicial). */
export const normalizarTelefono = (valor: string) => (valor ?? '').trim().replace(/[\s().-]/g, '')
export const normalizarCorreo = (valor: string) => (valor ?? '').trim().toLowerCase()

export function validarTelefono(valor: string): true | string {
  const telefono = normalizarTelefono(valor)
  if (!telefono) return 'Ingrese el teléfono'
  return /^\+?\d{10,15}$/.test(telefono) ? true : 'El teléfono debe tener de 10 a 15 dígitos'
}

export function validarCorreo(valor: string): true | string {
  const correo = normalizarCorreo(valor)
  if (!correo) return 'Ingrese el correo'
  if (correo.length > 254) return 'Use hasta 254 caracteres'
  return CORREO.test(correo) ? true : 'El correo no tiene un formato válido'
}

export const iniciales = (nombre: string) => limpiarNombre(nombre).split(' ').slice(0, 2).map((parte) => parte[0]).join('').toUpperCase()
