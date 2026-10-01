import { createRouter, createWebHistory } from 'vue-router'
import LoginView from './views/LoginView.vue'
import RecoveryView from './views/RecoveryView.vue'
import DashboardView from './views/DashboardView.vue'
import EmployeeView from './views/EmployeeView.vue'
import { auth } from './auth'
import type { Role } from './types'

declare module 'vue-router' { interface RouteMeta { requiresAuth?: boolean; roles?: Role[] } }
const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/', redirect: '/panel' },
  { path: '/ingresar', component: LoginView },
  { path: '/recuperar', component: RecoveryView },
  { path: '/panel', component: DashboardView, meta: { requiresAuth: true } },
  { path: '/empleados/nuevo', component: EmployeeView, meta: { requiresAuth: true, roles: ['ADMINISTRADOR'] } },
  { path: '/:pathMatch(.*)*', redirect: '/panel' }
] })
router.beforeEach((to) => {
  const user = auth.user()
  if (to.meta.requiresAuth && !user) return '/ingresar'
  if (to.meta.roles && (!user || !to.meta.roles.includes(user.role))) return '/panel'
  if ((to.path === '/ingresar' || to.path === '/recuperar') && user) return '/panel'
})
export default router
