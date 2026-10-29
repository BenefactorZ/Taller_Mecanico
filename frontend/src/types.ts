export type Role = 'ADMINISTRADOR' | 'RECEPCIONISTA' | 'ASESOR_SERVICIO' | 'TECNICO' | 'CLIENTE' | 'SISTEMA' | 'INVITADO' | 'PERSONALIZADO'
// role = PERSONALIZADO cuando el empleado tiene un rol creado por el administrador; su nombre viene en role_name
export interface PermisoResumen { codigo: string; nombre: string }
// permisos: lo que la API le autoriza ahora mismo (de su rol de fábrica o de su rol personalizado)
export interface User { id: number; full_name: string; email: string; role: Role; role_name?: string | null; permisos?: PermisoResumen[]; branch: string | null; is_active: boolean }
// Cuenta tal como la lista la administración de empleados
export interface UsuarioAdmin { id: number; full_name: string; email: string; role: Role; role_code: string; role_name: string; branch: string | null; is_active: boolean; bin_status: number; protegido: boolean; es_usted: boolean; taller_registrado: boolean | null; rol_eliminado: boolean; created_at: string }
export interface PaginaUsuarios { items: UsuarioAdmin[]; total: number; pagina: number; tamano: number }
export interface Permiso { codigo: string; modulo: string; nombre: string; descripcion: string; delegable: boolean; en_desarrollo: boolean }
export const tienePermiso = (user: User | null, codigo: string): boolean => !!user?.permisos?.some((p) => p.codigo === codigo)
export interface RoleDefinition { id: number; code: string; name: string; description: string | null; bin_status: number; es_sistema: boolean; empleados: number; permisos: string[] }
export const STATUS_ELIMINADO = 2 // status.id del borrado lógico
export interface Taller { id: number; nombre: string; rfc: string | null; email_contacto: string | null; calle: string | null; colonia: string | null; codigo_postal: string | null; estado: string | null; municipio: string | null; tiene_foto: boolean }
// Taller tal como lo lista la administración de talleres: con su estatus y cuántos empleados y clientes tiene
export interface TallerAdmin extends Taller { bin_status: number; empleados: number; clientes: number; created_at: string }
export interface PaginaTalleres { items: TallerAdmin[]; total: number; pagina: number; tamano: number }

export type EstadoCustomer = 'ACTIVO' | 'INACTIVO'
// Un cliente tiene ID, nombre, teléfono y correo (los clientes anteriores a la separación pueden carecer de uno de los dos)
export interface Customer { id: number; nombre_completo: string; telefono: string | null; correo: string | null; taller_id: number; estado: EstadoCustomer }
export type ResultadoAlta = 'COINCIDENCIAS' | 'PENDIENTE_CONFIRMACION' | 'CREADO'
export interface RespuestaAlta { resultado: ResultadoAlta; customer: Customer | null; coincidencias: Customer[] }
export interface PaginaCustomers { items: Customer[]; total: number; numero: number; tamano: number; hay_mas: boolean }

export const ROLE_LABELS: Record<Role, string> = {
  ADMINISTRADOR: 'Administrador',
  RECEPCIONISTA: 'Recepcionista',
  ASESOR_SERVICIO: 'Asesor de servicio',
  TECNICO: 'Técnico',
  CLIENTE: 'Cliente',
  SISTEMA: 'Sistema',
  INVITADO: 'Invitado',
  PERSONALIZADO: 'Rol personalizado'
}

// Icono de cada rol de fábrica; los personalizados usan el genérico
export const ROL_ICONOS: Record<string, string> = {
  ADMINISTRADOR: 'mdi-shield-account-outline', RECEPCIONISTA: 'mdi-clipboard-text-outline', ASESOR_SERVICIO: 'mdi-account-tie-outline',
  TECNICO: 'mdi-wrench-outline', CLIENTE: 'mdi-account-outline', SISTEMA: 'mdi-cog-outline', INVITADO: 'mdi-account-clock-outline'
}

/** Nombre del rol para mostrar: el del rol personalizado si lo tiene, o el de fábrica. */
export const etiquetaRol = (user: User): string => (user.role === 'PERSONALIZADO' ? user.role_name || ROLE_LABELS.PERSONALIZADO : ROLE_LABELS[user.role])

// Administración de clientes: el cliente con su taller y cuántos vehículos tiene. `INACTIVO` se muestra como «Suspendido»
export interface ClienteAdmin { id: number; nombre_completo: string; telefono: string | null; correo: string | null; datos_incompletos: boolean; estado: EstadoCustomer; taller_id: number; taller: string; vehiculos: number; created_at: string }
export interface PaginaClientesAdmin { items: ClienteAdmin[]; total: number; pagina: number; tamano: number }
export interface Movimiento { id: number; accion: string; detalle: string; usuario: string; fecha: string }
export const etiquetaEstadoCliente = (estado: EstadoCustomer) => (estado === 'ACTIVO' ? 'Activo' : 'Suspendido')

export interface Vehiculo { id: number; customer_id: number; cliente: string; taller_id: number; taller: string; vin: string; placa: string; marca: string; modelo: string; anio: number; color: string; kilometraje: number | null; tiene_foto: boolean; estado: string; created_at: string }
export interface PaginaVehiculos { items: Vehiculo[]; total: number; pagina: number; tamano: number }
