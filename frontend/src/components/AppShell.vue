<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDisplay } from 'vuetify'
import { auth } from '../auth'
import { MODULES, visible } from '../modules'
import { etiquetaRol, tienePermiso } from '../types'

defineProps<{ section: string; title: string }>()
const router = useRouter()
const { mdAndUp } = useDisplay()
const drawer = ref(mdAndUp.value)
watch(mdAndUp, (desktop) => { drawer.value = desktop })

const user = auth.user()!
// El menú muestra sólo lo que la persona puede usar, según sus permisos
const can = (permiso: string) => tienePermiso(user, permiso)
const verAdministracion = can('empleados.alta') || can('empleados.administrar') || can('roles.administrar')
const verClientes = can('clientes.consultar') || can('clientes.alta') || can('clientes.administrar')
const verVehiculos = can('vehiculos.consultar') || can('vehiculos.registrar')
const roleLabel = etiquetaRol(user)
const initials = user.full_name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
const upcoming = MODULES.filter((module) => module.status !== 'activo' && visible(user, module))
function logout() { auth.clear(); router.push('/ingresar') }
</script>

<template>
  <v-navigation-drawer v-model="drawer" class="shell-drawer" theme="tallerDark" :permanent="mdAndUp" :temporary="!mdAndUp" width="272" border="0">
    <div class="shell-brand"><div class="brand-mark"><v-icon icon="mdi-car-wrench" /></div><div><strong>Taller Mecánico</strong><small>Gestión operativa</small></div></div>
    <v-list class="shell-nav" nav density="comfortable" color="primary">
      <v-list-subheader>General</v-list-subheader>
      <v-list-item to="/panel" prepend-icon="mdi-view-dashboard-outline" title="Panel" />
      <template v-if="verAdministracion">
        <v-list-subheader>Administración</v-list-subheader>
        <v-list-item v-if="can('empleados.administrar')" to="/empleados" exact prepend-icon="mdi-account-group-outline" title="Empleados" />
        <v-list-item v-if="can('empleados.alta')" to="/empleados/nuevo" prepend-icon="mdi-account-plus-outline" title="Nuevo empleado" />
        <v-list-item v-if="can('roles.administrar')" to="/roles" exact prepend-icon="mdi-shield-edit-outline" title="Roles y permisos" />
        <v-list-item v-if="can('roles.administrar')" to="/roles/nuevo" prepend-icon="mdi-badge-account-horizontal-outline" title="Nuevo rol" />
      </template>
      <template v-if="can('talleres.administrar') || can('talleres.alta')">
        <v-list-subheader>Talleres</v-list-subheader>
        <v-list-item v-if="can('talleres.administrar')" to="/talleres" exact prepend-icon="mdi-garage-open-variant" title="Talleres" />
        <v-list-item v-if="can('talleres.alta')" to="/talleres/nuevo" prepend-icon="mdi-garage-variant" title="Nuevo taller" />
      </template>
      <template v-if="verClientes">
        <v-list-subheader>Clientes</v-list-subheader>
        <v-list-item v-if="can('clientes.consultar')" to="/clientes" exact prepend-icon="mdi-account-search-outline" title="Consultar clientes" />
        <v-list-item v-if="can('clientes.alta')" to="/clientes/nuevo" prepend-icon="mdi-account-plus-outline" title="Nuevo cliente" />
        <v-list-item v-if="can('clientes.administrar')" to="/clientes/administracion" prepend-icon="mdi-account-cog-outline" title="Administrar clientes" />
      </template>
      <template v-if="verVehiculos">
        <v-list-subheader>Vehículos</v-list-subheader>
        <v-list-item v-if="can('vehiculos.consultar')" to="/vehiculos" exact prepend-icon="mdi-car-outline" title="Vehículos" />
        <v-list-item v-if="can('vehiculos.registrar')" to="/vehiculos/nuevo" prepend-icon="mdi-car-arrow-right" title="Registrar vehículo" />
      </template>
      <template v-if="upcoming.length">
        <v-list-subheader>Próximamente</v-list-subheader>
        <v-list-item v-for="module in upcoming" :key="module.key" class="shell-nav__soon" :prepend-icon="module.icon" :title="module.title">
          <template #append><v-icon class="soon-icon" icon="mdi-clock-outline" size="15" title="Próximamente" /></template>
        </v-list-item>
      </template>
    </v-list>
    <template #append>
      <div class="shell-user">
        <v-avatar class="avatar-initials" size="40">{{ initials }}</v-avatar>
        <div class="shell-user__meta"><strong>{{ user.full_name }}</strong><small>{{ roleLabel }}</small></div>
        <v-btn icon="mdi-logout" size="small" variant="text" title="Cerrar sesión" @click="logout" />
      </div>
    </template>
  </v-navigation-drawer>

  <v-app-bar class="shell-bar" elevation="0" height="68">
    <v-app-bar-nav-icon v-if="!mdAndUp" @click="drawer = !drawer" />
    <div class="shell-bar__title"><small>{{ section }}</small><strong>{{ title }}</strong></div>
    <v-spacer />
    <v-chip class="mr-3 d-none d-sm-flex" color="success" variant="tonal" size="small" prepend-icon="mdi-shield-check">Sesión protegida</v-chip>
    <v-menu location="bottom end" offset="8">
      <template #activator="{ props }">
        <v-btn v-bind="props" class="mr-3" icon variant="text"><v-avatar class="avatar-initials" size="38">{{ initials }}</v-avatar></v-btn>
      </template>
      <v-card class="user-menu" min-width="260">
        <div class="user-menu__head"><v-avatar class="avatar-initials" size="44">{{ initials }}</v-avatar><div><strong>{{ user.full_name }}</strong><small>{{ user.email }}</small></div></div>
        <v-divider />
        <v-list density="compact" nav>
          <v-list-item prepend-icon="mdi-badge-account-outline" :title="roleLabel" subtitle="Rol asignado" />
          <v-list-item prepend-icon="mdi-store-outline" :title="user.branch ?? 'Todas las sucursales'" subtitle="Sucursal" />
          <v-list-item prepend-icon="mdi-logout" title="Cerrar sesión" base-color="error" @click="logout" />
        </v-list>
      </v-card>
    </v-menu>
  </v-app-bar>

  <v-main class="shell-main">
    <div class="shell-content"><slot /></div>
  </v-main>
</template>
