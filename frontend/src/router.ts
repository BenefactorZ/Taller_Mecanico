import { createRouter, createWebHistory } from 'vue-router'
import LoginView from './views/LoginView.vue'
import RecoveryView from './views/RecoveryView.vue'
import DashboardView from './views/DashboardView.vue'
import EmployeeView from './views/EmployeeView.vue'
import EmpleadosView from './views/EmpleadosView.vue'
import RoleView from './views/RoleView.vue'
import RegisterView from './views/RegisterView.vue'
import RolesAdminView from './views/RolesAdminView.vue'
import TallerNuevoView from './views/TallerNuevoView.vue'
import TalleresAdminView from './views/TalleresAdminView.vue'
import ClientesView from './views/ClientesView.vue'
import ClienteNuevoView from './views/ClienteNuevoView.vue'
import ClienteFichaView from './views/ClienteFichaView.vue'
import ClientesAdminView from './views/ClientesAdminView.vue'
import VehiculosView from './views/VehiculosView.vue'
import VehiculoNuevoView from './views/VehiculoNuevoView.vue'
import { auth } from './auth'
import { api } from './api'
import { tienePermiso, type User } from './types'

declare module 'vue-router' { interface RouteMeta { requiresAuth?: boolean; permiso?: string; title?: string } }
const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/', redirect: '/panel' },
  { path: '/ingresar', component: LoginView, meta: { title: 'Ingresar' } },
  { path: '/registro', component: RegisterView, meta: { title: 'Crear cuenta' } },
  { path: '/recuperar', component: RecoveryView, meta: { title: 'Recuperar contraseña' } },
  { path: '/panel', component: DashboardView, meta: { requiresAuth: true, title: 'Panel' } },
  { path: '/empleados', component: EmpleadosView, meta: { requiresAuth: true, permiso: 'empleados.administrar', title: 'Empleados' } },
  { path: '/empleados/nuevo', component: EmployeeView, meta: { requiresAuth: true, permiso: 'empleados.alta', title: 'Alta de empleado' } },
  { path: '/roles', component: RolesAdminView, meta: { requiresAuth: true, permiso: 'roles.administrar', title: 'Administrar roles' } },
  { path: '/roles/nuevo', component: RoleView, meta: { requiresAuth: true, permiso: 'roles.administrar', title: 'Alta de rol' } },
  { path: '/talleres', component: TalleresAdminView, meta: { requiresAuth: true, permiso: 'talleres.administrar', title: 'Talleres' } },
  { path: '/talleres/nuevo', component: TallerNuevoView, meta: { requiresAuth: true, permiso: 'talleres.alta', title: 'Alta de taller' } },
  { path: '/talleres/:id(\\d+)/editar', component: TallerNuevoView, meta: { requiresAuth: true, permiso: 'talleres.administrar', title: 'Editar taller' } },
  { path: '/clientes', component: ClientesView, meta: { requiresAuth: true, permiso: 'clientes.consultar', title: 'Clientes' } },
  { path: '/clientes/nuevo', component: ClienteNuevoView, meta: { requiresAuth: true, permiso: 'clientes.alta', title: 'Nuevo cliente' } },
  { path: '/clientes/administracion', component: ClientesAdminView, meta: { requiresAuth: true, permiso: 'clientes.administrar', title: 'Administrar clientes' } },
  { path: '/vehiculos', component: VehiculosView, meta: { requiresAuth: true, permiso: 'vehiculos.consultar', title: 'Vehículos' } },
  { path: '/vehiculos/nuevo', component: VehiculoNuevoView, meta: { requiresAuth: true, permiso: 'vehiculos.registrar', title: 'Registrar vehículo' } },
  { path: '/clientes/:id(\\d+)', component: ClienteFichaView, meta: { requiresAuth: true, permiso: 'clientes.consultar', title: 'Ficha de cliente' } },
  { path: '/:pathMatch(.*)*', redirect: '/panel' }
] })
// Los permisos pueden haber cambiado desde el último inicio de sesión: al cargar la página se vuelven a pedir una vez.
// (La API aplica siempre los vigentes; esto sólo mantiene el menú y las rutas al día.)
let sesionActualizada = false
router.beforeEach(async (to) => {
  if (auth.user() && !sesionActualizada) {
    sesionActualizada = true
    try { auth.set(auth.token() as string, await api<User>('/auth/me')) } catch { /* sin conexión: se usa la sesión guardada */ }
  }
  const user = auth.user()
  if (to.meta.requiresAuth && !user) return '/ingresar'
  if (to.meta.permiso && !tienePermiso(user, to.meta.permiso)) return '/panel'
  if ((to.path === '/ingresar' || to.path === '/recuperar' || to.path === '/registro') && user) return '/panel'
})
router.afterEach((to) => { document.title = to.meta.title ? `${to.meta.title} · Taller Mecánico` : 'Taller Mecánico' })
export default router
