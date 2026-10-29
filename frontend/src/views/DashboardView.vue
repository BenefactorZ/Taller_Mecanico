<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import { api } from '../api'
import { auth } from '../auth'
import { MODULES, STATUS_META, rutaDe, visible } from '../modules'
import { etiquetaRol, tienePermiso, type RoleDefinition } from '../types'

const user = auth.user()!
const can = (permiso: string) => tienePermiso(user, permiso)
const administraRoles = can('roles.administrar')
const permisos = user.permisos ?? []
// Accesos directos del banner, en orden de importancia: registrar cliente, administrar vehículos, administrar clientes, registrar vehículo y el resto.
// El banner muestra los dos primeros que la persona pueda usar.
const ACCIONES = [
  { permiso: 'clientes.alta', texto: 'Registrar cliente', detalle: 'Dar de alta un cliente nuevo.', icono: 'mdi-account-plus-outline', tone: 'violet', to: '/clientes/nuevo' },
  { permiso: 'vehiculos.consultar', texto: 'Administrar vehículos', detalle: 'Buscar, modificar, eliminar y restaurar vehículos.', icono: 'mdi-car-cog', tone: 'orange', to: '/vehiculos' },
  { permiso: 'clientes.administrar', texto: 'Administrar clientes', detalle: 'Buscar, modificar y suspender clientes.', icono: 'mdi-account-cog-outline', tone: 'violet', to: '/clientes/administracion' },
  { permiso: 'vehiculos.registrar', texto: 'Registrar vehículo', detalle: 'Asociar un vehículo a un cliente.', icono: 'mdi-car-arrow-right', tone: 'orange', to: '/vehiculos/nuevo' },
  { permiso: 'clientes.consultar', texto: 'Consultar clientes', icono: 'mdi-account-search-outline', to: '/clientes' },
  { permiso: 'empleados.alta', texto: 'Nuevo empleado', icono: 'mdi-account-plus-outline', to: '/empleados/nuevo' },
  { permiso: 'roles.administrar', texto: 'Nuevo rol', icono: 'mdi-badge-account-horizontal-outline', to: '/roles/nuevo' },
  { permiso: 'talleres.alta', texto: 'Nuevo taller', icono: 'mdi-garage-variant', to: '/talleres/nuevo' }
]
const disponibles = ACCIONES.filter((accion) => can(accion.permiso))
const acciones = disponibles.slice(0, 2)
const esInvitado = user.role === 'INVITADO'
const sinPermisos = user.role === 'PERSONALIZADO' && permisos.length === 0
const roleLabel = etiquetaRol(user)
const firstName = user.full_name.split(/\s+/)[0]
const now = new Date()
const hour = now.getHours()
const greeting = hour >= 6 && hour < 12 ? 'Buenos días' : hour >= 12 && hour < 19 ? 'Buenas tardes' : 'Buenas noches'
const todayText = now.toLocaleDateString('es-MX', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
const today = todayText.charAt(0).toUpperCase() + todayText.slice(1)
const modules = MODULES.filter((module) => visible(user, module))
const activeCount = modules.filter((module) => module.status === 'activo').length
const expires = auth.expiresAt()
const stats = [
  { label: 'Rol activo', value: roleLabel, hint: 'Permisos validados por la API', icon: 'mdi-shield-account-outline', tone: 'red' },
  { label: 'Sucursal', value: user.branch ?? 'Todas', hint: user.branch ? 'Asignación vigente' : 'Alcance corporativo', icon: 'mdi-store-outline', tone: 'orange' },
  { label: 'Módulos disponibles', value: `${activeCount} de ${modules.length}`, hint: 'Según sus permisos', icon: 'mdi-view-grid-outline', tone: 'blue' },
  { label: 'Sesión vence', value: expires ? expires.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' }) : '—', hint: 'Token firmado por el servidor', icon: 'mdi-timer-sand', tone: 'green' }
]

const customRoles = ref<RoleDefinition[]>([])
const rolesLoading = ref(administraRoles)
const rolesError = ref('')
onMounted(async () => {
  if (!administraRoles) return
  try { customRoles.value = (await api<RoleDefinition[]>('/roles')).filter((rol) => !rol.es_sistema) }
  catch (e) { rolesError.value = e instanceof Error ? e.message : 'No fue posible cargar los roles' }
  finally { rolesLoading.value = false }
})
</script>

<template>
  <AppShell section="General" title="Panel de trabajo">
    <section class="hero-banner">
      <div class="hero-banner__copy">
        <span class="hero-banner__kicker"><v-icon icon="mdi-calendar-today-outline" size="16" />{{ today }}</span>
        <h1>{{ greeting }}, {{ firstName }}</h1>
        <p>Ingresó como <strong>{{ roleLabel }}</strong><template v-if="user.branch"> en la sucursal <strong>{{ user.branch }}</strong></template>. Aquí tiene un resumen de lo que puede hacer hoy.</p>
        <div v-if="acciones.length" class="hero-banner__actions">
          <v-btn v-for="(accion, i) in acciones" :key="accion.to" :color="i === 0 ? 'white' : undefined" :class="{ 'hero-btn': i === 0 }" :variant="i === 0 ? 'elevated' : 'outlined'" size="large" :prepend-icon="accion.icono" :to="accion.to" :style="i === 0 ? undefined : 'color: #fff'">{{ accion.texto }}</v-btn>
        </div>
      </div>
      <div class="hero-banner__art"><v-icon icon="mdi-car-cog" /></div>
    </section>

    <v-alert v-if="esInvitado" class="mt-6" type="info" variant="tonal" density="comfortable" icon="mdi-account-clock-outline" title="Su cuenta es de invitado">
      Se registró correctamente, pero todavía no tiene un rol. Un administrador debe asignárselo antes de que pueda usar los módulos del taller.
    </v-alert>

    <v-alert v-if="sinPermisos" class="mt-6" type="info" variant="tonal" density="comfortable" icon="mdi-badge-account-outline" :title="`Su rol es «${roleLabel}»`">
      Su rol no tiene permisos asignados, por eso aún no puede usar los módulos del taller. Un administrador debe definirlos.
    </v-alert>

    <div class="dash-grid dash-grid--tareas">
      <v-card class="panel-card" elevation="0">
        <header class="panel-card__header">
          <div><h2>Módulos del sistema</h2><p>Estado de cada módulo disponible para su rol.</p></div>
          <v-chip size="small" variant="tonal" color="primary">{{ modules.length }} módulos</v-chip>
        </header>
        <div class="module-grid">
          <v-card v-for="module in modules" :key="module.key" class="module-card" :class="{ 'module-card--link': rutaDe(user, module) }" :to="rutaDe(user, module)" elevation="0" :ripple="!!rutaDe(user, module)">
            <div class="tone-icon" :class="`tone-${module.tone}`"><v-icon :icon="module.icon" /></div>
            <div class="module-card__body">
              <h3>{{ module.title }}</h3>
              <p>{{ module.description }}</p>
              <v-chip size="x-small" variant="tonal" label :color="STATUS_META[module.status].color" :prepend-icon="STATUS_META[module.status].icon">{{ STATUS_META[module.status].label }}</v-chip>
            </div>
            <v-icon v-if="rutaDe(user, module)" class="module-card__arrow" icon="mdi-arrow-top-right" size="18" />
          </v-card>
        </div>
      </v-card>

    </div>

    <h2 class="info-title">Información</h2>
    <section class="stat-grid">
      <article v-for="stat in stats" :key="stat.label" class="stat-card">
        <div class="tone-icon" :class="`tone-${stat.tone}`"><v-icon :icon="stat.icon" /></div>
        <div><small>{{ stat.label }}</small><strong>{{ stat.value }}</strong><span>{{ stat.hint }}</span></div>
      </article>
    </section>

    <div class="info-grid">
      <aside class="side-stack side-stack--row">
        <v-card v-if="administraRoles" class="panel-card" elevation="0">
          <header class="panel-card__header">
            <div><h2>Roles personalizados</h2><p>Catálogo registrado por administración.</p></div>
            <v-btn icon="mdi-plus" size="small" color="primary" variant="tonal" to="/roles/nuevo" title="Nuevo rol" />
          </header>
          <div v-if="rolesLoading" class="role-list"><v-skeleton-loader v-for="n in 3" :key="n" type="list-item-two-line" /></div>
          <v-alert v-else-if="rolesError" type="warning" variant="tonal" density="compact">{{ rolesError }}</v-alert>
          <div v-else-if="customRoles.length" class="role-list">
            <div v-for="role in customRoles.slice(0, 5)" :key="role.id" class="role-item">
              <div class="tone-icon tone-orange"><v-icon icon="mdi-badge-account-outline" size="20" /></div>
              <div><strong>{{ role.name }}</strong><code>{{ role.code }}</code><p v-if="role.description">{{ role.description }}</p></div>
            </div>
            <small v-if="customRoles.length > 5" class="muted-note">y {{ customRoles.length - 5 }} roles más</small>
          </div>
          <div v-else class="empty-state"><v-icon icon="mdi-badge-account-horizontal-outline" /><p>Aún no hay roles personalizados.</p><v-btn size="small" variant="tonal" color="primary" to="/roles/nuevo">Crear el primero</v-btn></div>
        </v-card>

        <v-card v-else class="panel-card" elevation="0">
          <header class="panel-card__header"><div><h2>Sus permisos</h2><p>Operaciones que la API le autoriza.</p></div></header>
          <ul v-if="permisos.length" class="check-list"><li v-for="permiso in permisos" :key="permiso.codigo"><v-icon icon="mdi-check-circle" size="18" />{{ permiso.nombre }}</li></ul>
          <p v-else class="muted-note">Todavía no tiene permisos asignados.</p>
        </v-card>

        <v-card class="panel-card session-card" elevation="0">
          <div class="session-card__icon"><v-icon icon="mdi-shield-lock-outline" /></div>
          <h2>Sesión protegida</h2>
          <p>Cada solicitud se valida en el servidor con su token. Modificar la URL no concede permisos adicionales.</p>
          <div class="session-card__meta"><span><v-icon icon="mdi-email-outline" size="16" />{{ user.email }}</span></div>
        </v-card>
      </aside>
    </div>
  </AppShell>
</template>
