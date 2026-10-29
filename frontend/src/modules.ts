import { tienePermiso, type User } from './types'

export type ModuleStatus = 'activo' | 'diseno' | 'pendiente'
// `permisos`: basta con tener uno para ver el módulo; sin `permisos`, lo ven todos. `to` puede depender de lo que pueda hacer la persona.
export interface ModuleInfo { key: string; title: string; description: string; icon: string; tone: string; status: ModuleStatus; permisos?: string[]; to?: string | ((user: User) => string) }

export const MODULES: ModuleInfo[] = [
  { key: 'clientes', title: 'Clientes', description: 'Alta, consulta y administración de clientes: modificación con trazabilidad y suspensión.', icon: 'mdi-account-search-outline', tone: 'violet', status: 'activo', permisos: ['clientes.consultar', 'clientes.alta', 'clientes.administrar'], to: (user) => (tienePermiso(user, 'clientes.consultar') ? '/clientes' : tienePermiso(user, 'clientes.administrar') ? '/clientes/administracion' : '/clientes/nuevo') },
  { key: 'vehiculos', title: 'Vehículos', description: 'Registro de vehículos con VIN, placa y foto, asociados a un cliente.', icon: 'mdi-car-outline', tone: 'orange', status: 'activo', permisos: ['vehiculos.registrar', 'vehiculos.consultar'], to: (user) => (tienePermiso(user, 'vehiculos.consultar') ? '/vehiculos' : '/vehiculos/nuevo') },
  { key: 'acceso', title: 'Acceso y seguridad', description: 'Inicio de sesión con JWT y recuperación de contraseña por código.', icon: 'mdi-shield-lock-outline', tone: 'green', status: 'activo' },
  { key: 'empleados', title: 'Empleados', description: 'Alta y administración de empleados: rol, sucursal y cuentas sin rol.', icon: 'mdi-account-group-outline', tone: 'red', status: 'activo', permisos: ['empleados.administrar', 'empleados.alta'], to: (user) => (tienePermiso(user, 'empleados.administrar') ? '/empleados' : '/empleados/nuevo') },
  { key: 'roles', title: 'Roles y permisos', description: 'Alta, edición y eliminación lógica de roles, y sus permisos.', icon: 'mdi-badge-account-horizontal-outline', tone: 'orange', status: 'activo', permisos: ['roles.administrar'], to: '/roles' },
  { key: 'talleres', title: 'Talleres', description: 'Alta y administración de talleres: datos, domicilio, foto y eliminación lógica.', icon: 'mdi-garage-variant', tone: 'blue', status: 'activo', permisos: ['talleres.administrar', 'talleres.alta'], to: (user) => (tienePermiso(user, 'talleres.administrar') ? '/talleres' : '/talleres/nuevo') },
  { key: 'recepcion', title: 'Recepción de vehículos', description: 'Registro de entrada del vehículo al taller.', icon: 'mdi-car-arrow-right', tone: 'blue', status: 'pendiente', permisos: ['recepciones.registrar'] },
  { key: 'ordenes', title: 'Órdenes de trabajo', description: 'Seguimiento y corrección de órdenes.', icon: 'mdi-clipboard-list-outline', tone: 'blue', status: 'pendiente', permisos: ['ordenes.consultar', 'ordenes.corregir'] },
  { key: 'diagnosticos', title: 'Diagnósticos', description: 'Registro técnico de fallas por orden.', icon: 'mdi-car-wrench', tone: 'orange', status: 'pendiente', permisos: ['diagnosticos.registrar'] },
  { key: 'notificaciones', title: 'Notificaciones', description: 'Avisos al cliente sobre su vehículo.', icon: 'mdi-bell-ring-outline', tone: 'violet', status: 'pendiente', permisos: ['notificaciones.consultar'] }
]

/** El módulo se muestra si no exige permisos o la persona tiene al menos uno de ellos. */
export const visible = (user: User, modulo: ModuleInfo): boolean => !modulo.permisos || modulo.permisos.some((p) => tienePermiso(user, p))
export const rutaDe = (user: User, modulo: ModuleInfo): string | undefined => (typeof modulo.to === 'function' ? modulo.to(user) : modulo.to)

export const STATUS_META: Record<ModuleStatus, { label: string; color: string; icon: string }> = {
  activo: { label: 'Disponible', color: 'success', icon: 'mdi-check-circle' },
  diseno: { label: 'En diseño', color: 'info', icon: 'mdi-pencil-ruler' },
  pendiente: { label: 'Pendiente', color: 'warning', icon: 'mdi-progress-clock' }
}
