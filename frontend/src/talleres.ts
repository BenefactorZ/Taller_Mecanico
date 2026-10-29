// Reglas del alta de taller: reflejan las del servidor (backend/app/talleres/validaciones.py). El servidor es la autoridad.
const RFC = /^[A-ZÑ&]{3,4}\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[A-Z0-9]{3}$/
const DIAS_POR_MES = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31] // febrero admite 29: el RFC sólo trae 2 dígitos del año
export const FOTO_MAX_BYTES = 15 * 1024 * 1024
export const FOTO_MAX_TEXTO = '15 MB'

export const limpiar = (valor: string) => valor.split(/\s+/).filter(Boolean).join(' ')

export function validarRfc(valor: string): true | string {
  const rfc = valor.trim().toUpperCase()
  const mensaje = 'RFC no válido: 12 caracteres (persona moral) o 13 (persona física), por ejemplo ABC010203AB1'
  if (!RFC.test(rfc)) return mensaje
  const cuerpo = /\d/.test(rfc[3]) ? rfc.slice(3) : rfc.slice(4)
  const mes = Number(cuerpo.slice(2, 4)); const dia = Number(cuerpo.slice(4, 6))
  return dia <= DIAS_POR_MES[mes - 1] ? true : 'El RFC trae una fecha que no existe en el calendario'
}

export const validarTexto = (etiqueta: string, minimo: number, maximo: number) => (valor: string): true | string => {
  const largo = limpiar(valor ?? '').length
  if (largo < minimo) return minimo <= 1 ? `${etiqueta} es obligatorio` : `${etiqueta}: escriba al menos ${minimo} caracteres`
  return largo <= maximo ? true : `${etiqueta}: máximo ${maximo} caracteres`
}

export const validarCorreo = (valor: string): true | string => (/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(valor.trim()) ? true : 'Ingrese un correo válido')
export const validarCp = (valor: string): true | string => (/^\d{5}$/.test(valor) ? true : 'El código postal tiene 5 dígitos')
export const requerido = (etiqueta: string) => (valor: string | null): true | string => (valor ? true : `${etiqueta} es obligatorio`)

/** Identifica la imagen por sus bytes iniciales (no por la extensión): JPG, PNG o WebP. */
export async function tipoDeFoto(archivo: File): Promise<'jpg' | 'png' | 'webp' | null> {
  const b = new Uint8Array(await archivo.slice(0, 12).arrayBuffer())
  if (b[0] === 0xff && b[1] === 0xd8 && b[2] === 0xff) return 'jpg'
  if (b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47) return 'png'
  if (b[0] === 0x52 && b[1] === 0x49 && b[2] === 0x46 && b[3] === 0x46 && b[8] === 0x57 && b[9] === 0x45 && b[10] === 0x42 && b[11] === 0x50) return 'webp'
  return null
}

export async function validarFoto(archivo: File | null, objeto = 'la foto del taller'): Promise<string> {
  if (!archivo) return `Seleccione ${objeto}`
  if (archivo.size > FOTO_MAX_BYTES) return `La foto pesa ${(archivo.size / 1024 / 1024).toFixed(1)} MB; el máximo es ${FOTO_MAX_TEXTO}`
  if (archivo.size === 0) return 'El archivo está vacío'
  return (await tipoDeFoto(archivo)) ? '' : 'La foto debe ser JPG, PNG o WebP'
}
