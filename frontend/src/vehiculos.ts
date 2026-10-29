// Reglas del registro de vehículos: reflejan las del servidor (backend/app/vehiculos/validaciones.py). El servidor es la autoridad.
const VIN = /^[A-HJ-NPR-Z0-9]{17}$/ // ISO 3779: 17 caracteres, sin I, O ni Q
const PLACA = /^(?=.*[A-Z])(?=.*\d)[A-Z0-9]{5,7}$/ // placa ya normalizada: 5 a 7 caracteres entre letras y números
export const ANIO_MINIMO = 1981 // el VIN de 17 caracteres es obligatorio desde el modelo 1981
export const KILOMETRAJE_MAXIMO = 2_000_000
export const anioMaximo = () => new Date().getFullYear() + 1

/** VIN y placa se guardan en mayúsculas y sin espacios, guiones ni puntos. */
export const normalizarCodigo = (valor: string) => (valor ?? '').replace(/[\s.-]/g, '').toUpperCase()

export const validarVin = (valor: string): true | string =>
  VIN.test(normalizarCodigo(valor)) ? true : 'El VIN debe tener 17 caracteres (letras y números, sin I, O ni Q). Ej. 1HGCM82633A004352'
export const validarPlaca = (valor: string): true | string =>
  PLACA.test(normalizarCodigo(valor)) ? true : 'La placa debe tener de 5 a 7 caracteres entre letras y números. Ej. ABC-123-D'

export const validarTexto = (etiqueta: string, minimo: number, maximo: number) => (valor: string): true | string => {
  const largo = (valor ?? '').split(/\s+/).filter(Boolean).join(' ').length
  if (largo < minimo) return minimo <= 1 ? `${etiqueta} es obligatorio` : `${etiqueta}: escriba al menos ${minimo} caracteres`
  return largo <= maximo ? true : `${etiqueta}: máximo ${maximo} caracteres`
}

export function validarAnio(valor: string): true | string {
  const texto = (valor ?? '').trim()
  if (!/^\d{4}$/.test(texto)) return 'Escriba el año con 4 dígitos'
  const anio = Number(texto)
  return anio >= ANIO_MINIMO && anio <= anioMaximo() ? true : `El año debe estar entre ${ANIO_MINIMO} y ${anioMaximo()}`
}

export function validarKilometraje(valor: string): true | string {
  const texto = (valor ?? '').trim()
  if (!texto) return true // es opcional
  if (!/^\d+$/.test(texto)) return 'Use sólo números enteros'
  return Number(texto) <= KILOMETRAJE_MAXIMO ? true : `El máximo es ${KILOMETRAJE_MAXIMO.toLocaleString('es-MX')} km`
}
