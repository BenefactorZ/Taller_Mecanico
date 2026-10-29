<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import AppShell from '../components/AppShell.vue'
import FiltroSuspendidos from '../components/FiltroSuspendidos.vue'
import { api } from '../api'
import { iniciales } from '../clientes'
import { ROL_ICONOS, STATUS_ELIMINADO, type PaginaUsuarios, type RoleDefinition, type Taller, type UsuarioAdmin } from '../types'

type FormRef = { validate: () => Promise<{ valid: boolean }>; resetValidation: () => void }
const TAMANO = 8
const filtros = reactive({ buscar: '', rol: null as string | null, eliminados: false })
const pagina = ref(1)
const resultado = ref<PaginaUsuarios | null>(null)
const loading = ref(true); const error = ref(''); const aviso = ref(''); const snackbar = ref(false)
const roles = ref<RoleDefinition[]>([]); const asignables = ref<RoleDefinition[]>([]); const talleres = ref<Taller[]>([])
const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`
const eliminado = (u: UsuarioAdmin) => u.bin_status === STATUS_ELIMINADO
const sinRol = (u: UsuarioAdmin) => u.role === 'INVITADO'
const paginas = computed(() => (resultado.value ? Math.max(1, Math.ceil(resultado.value.total / resultado.value.tamano)) : 1))
const opcionesRol = computed(() => roles.value.filter((r) => r.bin_status !== STATUS_ELIMINADO).map((r) => ({ title: r.name, value: r.code })))
const opcionesAsignables = computed(() => asignables.value.map((r) => ({ title: r.name, value: r.code, icon: ROL_ICONOS[r.code] ?? 'mdi-badge-account-outline', personalizado: !r.es_sistema, description: r.description || 'Rol personalizado' })))
const nombresTaller = computed(() => talleres.value.map((t) => t.nombre))

async function cargar() {
  loading.value = true; error.value = ''
  try {
    const consulta = new URLSearchParams({ pagina: String(pagina.value), tamano: String(TAMANO), solo_eliminados: String(filtros.eliminados) })
    if (filtros.buscar.trim()) consulta.set('buscar', filtros.buscar.trim())
    if (filtros.rol) consulta.set('rol', filtros.rol)
    resultado.value = await api<PaginaUsuarios>(`/users?${consulta}`)
  } catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible cargar las cuentas' }
  finally { loading.value = false }
}

// La búsqueda espera a que se deje de escribir; los demás filtros recargan al instante y siempre desde la primera página
let temporizador: ReturnType<typeof setTimeout> | undefined
watch(() => filtros.buscar, () => { clearTimeout(temporizador); temporizador = setTimeout(() => { pagina.value = 1; void cargar() }, 350) })
watch(() => [filtros.rol, filtros.eliminados], () => { pagina.value = 1; void cargar() })
onBeforeUnmount(() => clearTimeout(temporizador))
onMounted(async () => {
  await Promise.all([
    api<RoleDefinition[]>('/roles').then((r) => (roles.value = r)).catch(() => undefined),
    api<RoleDefinition[]>('/roles/asignables').then((r) => (asignables.value = r)).catch(() => undefined),
    api<Taller[]>('/talleres').then((t) => (talleres.value = t)).catch(() => undefined),
  ])
  await cargar()
})

// ---- Editar / asignar rol ----
const edicion = ref(false); const formRef = ref<FormRef | null>(null); const formKey = ref(0)
const editando = ref<UsuarioAdmin | null>(null)
const form = reactive({ full_name: '', branch: '', role: null as string | null }); const errorEdicion = ref(''); const guardando = ref(false)
const reglas = {
  nombre: [(v: string) => (v ?? '').trim().length >= 3 || 'Ingrese el nombre completo', (v: string) => (v ?? '').trim().length <= 140 || 'Máximo 140 caracteres'],
  sucursal: [(v: string) => !!(v ?? '').trim() || 'La sucursal es obligatoria', (v: string) => (v ?? '').trim().length <= 100 || 'Máximo 100 caracteres'],
  rol: [(v: string | null) => !!v || 'Seleccione un rol'],
}
function editar(u: UsuarioAdmin) {
  editando.value = u; errorEdicion.value = ''
  Object.assign(form, { full_name: u.full_name, branch: u.branch ?? '', role: sinRol(u) || u.rol_eliminado ? null : u.role_code })
  formKey.value++; edicion.value = true
}
async function guardar() {
  errorEdicion.value = ''
  if (!editando.value) return
  if (!(await formRef.value?.validate())?.valid) { errorEdicion.value = 'Revise los campos marcados en rojo.'; return }
  guardando.value = true
  try {
    await api(`/users/${editando.value.id}`, { method: 'PATCH', body: JSON.stringify({ full_name: form.full_name, branch: form.branch, role: form.role }) })
    aviso.value = sinRol(editando.value) ? `${form.full_name.trim()} ahora es empleado.` : `Se actualizó la cuenta de ${form.full_name.trim()}.`; snackbar.value = true; edicion.value = false; await cargar()
  } catch (e) { errorEdicion.value = e instanceof Error ? e.message : 'No fue posible guardar los cambios' }
  finally { guardando.value = false }
}

// ---- Eliminar (borrado lógico) y restaurar ----
// La cuenta se conserva aparte del estado del diálogo para que su nombre no desaparezca durante la animación de cierre
const confirmando = ref(false); const aEliminar = ref<UsuarioAdmin | null>(null); const procesando = ref(false); const errorAccion = ref('')
function pedirEliminar(u: UsuarioAdmin) { aEliminar.value = u; errorAccion.value = ''; confirmando.value = true }
async function eliminar() {
  if (!aEliminar.value) return
  procesando.value = true; errorAccion.value = ''
  try {
    await api(`/users/${aEliminar.value.id}`, { method: 'DELETE' })
    aviso.value = `La cuenta de ${aEliminar.value.full_name} se eliminó y ya no puede ingresar. Puede restaurarla cuando quiera.`; snackbar.value = true; confirmando.value = false
    if (resultado.value && resultado.value.items.length === 1 && pagina.value > 1 && !filtros.eliminados) pagina.value--
    await cargar()
  } catch (e) { errorAccion.value = e instanceof Error ? e.message : 'No fue posible eliminar la cuenta' }
  finally { procesando.value = false }
}
async function restaurar(u: UsuarioAdmin) {
  error.value = ''
  try { await api(`/users/${u.id}/restaurar`, { method: 'POST' }); aviso.value = `La cuenta de ${u.full_name} se restauró.`; snackbar.value = true; await cargar() }
  catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible restaurar la cuenta' }
}
</script>

<template>
  <AppShell section="Administración" title="Empleados">
    <div class="page-head">
      <div class="page-head__icon"><v-icon icon="mdi-account-group-outline" /></div>
      <div class="page-head__grow"><span class="eyebrow">Administración · Personal</span><h1>Empleados</h1><p>Consulte las cuentas, cambie el nombre, la sucursal o el rol de un empleado, asigne rol a quien se registró como invitado y elimine cuentas (la eliminación es lógica y se puede restaurar).</p></div>
      <v-btn class="submit-btn d-none d-sm-flex" color="primary" size="large" prepend-icon="mdi-account-plus-outline" to="/empleados/nuevo">Nuevo empleado</v-btn>
    </div>

    <v-card class="panel-card" elevation="0">
      <div class="emp-filtros">
        <v-text-field v-model="filtros.buscar" class="emp-filtros__buscar" label="Buscar por nombre o correo" name="empleados-buscar" autocomplete="nope" prepend-inner-icon="mdi-magnify" clearable hide-details />
        <v-select v-model="filtros.rol" class="emp-filtros__rol" label="Rol" :items="opcionesRol" clearable hide-details prepend-inner-icon="mdi-badge-account-outline" placeholder="Todos los roles" />
        <FiltroSuspendidos v-model="filtros.eliminados" />
      </div>
      <div class="emp-atajos">
        <v-chip :variant="filtros.rol === 'INVITADO' ? 'flat' : 'tonal'" :color="filtros.rol === 'INVITADO' ? 'warning' : undefined" size="small" prepend-icon="mdi-account-clock-outline" @click="filtros.rol = filtros.rol === 'INVITADO' ? null : 'INVITADO'">Cuentas sin rol (invitados)</v-chip>
        <span v-if="resultado" class="muted-note">{{ plural(resultado.total, filtros.eliminados ? 'cuenta suspendida' : 'cuenta', filtros.eliminados ? 'cuentas suspendidas' : 'cuentas') }}</span>
      </div>

      <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mt-4" closable @click:close="error = ''">{{ error }}</v-alert>

      <div v-if="loading && !resultado" class="role-list mt-4"><v-skeleton-loader v-for="n in 4" :key="n" type="list-item-two-line" /></div>
      <div v-else-if="resultado && !resultado.items.length" class="empty-state empty-state--lg"><v-icon icon="mdi-account-search-outline" /><p>No hay cuentas con esos filtros.</p></div>
      <div v-else-if="resultado" class="role-table mt-4" :class="{ 'is-loading': loading }">
        <div v-for="u in resultado.items" :key="u.id" class="role-row emp-row" :class="{ 'is-deleted': eliminado(u) }">
          <v-avatar class="avatar-initials" size="42">{{ iniciales(u.full_name) }}</v-avatar>
          <div class="role-row__body">
            <strong>{{ u.full_name }}<v-chip v-if="u.es_usted" class="ml-2" size="x-small" label color="primary" variant="tonal">Usted</v-chip></strong>
            <span class="emp-row__correo"><v-icon icon="mdi-email-outline" size="14" />{{ u.email }}</span>
            <p v-if="u.branch"><v-icon icon="mdi-store-outline" size="14" /> {{ u.branch }}
              <v-chip v-if="u.taller_registrado === false" class="ml-1" size="x-small" label color="warning" variant="tonal" prepend-icon="mdi-alert-outline">Sucursal sin taller registrado</v-chip>
            </p>
          </div>
          <v-chip v-if="sinRol(u)" size="small" label color="warning" variant="tonal" prepend-icon="mdi-account-clock-outline">Sin rol asignado</v-chip>
          <v-chip v-else size="small" label variant="tonal" :color="u.rol_eliminado ? 'error' : 'primary'" :prepend-icon="u.rol_eliminado ? 'mdi-alert-outline' : (ROL_ICONOS[u.role_code] ?? 'mdi-badge-account-outline')" :title="u.rol_eliminado ? 'Su rol fue eliminado: no le concede permisos' : undefined">{{ u.role_name }}</v-chip>
          <v-chip size="small" label variant="tonal" :color="eliminado(u) ? 'error' : 'success'">{{ eliminado(u) ? 'Suspendida' : 'Activa' }}</v-chip>
          <div class="role-row__actions">
            <v-chip v-if="u.protegido" size="small" label variant="tonal" prepend-icon="mdi-lock-outline" title="Cuenta del administrador o interna: no se administra desde aquí">Protegida</v-chip>
            <template v-else-if="eliminado(u)"><v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-restore" @click="restaurar(u)">Restaurar</v-btn></template>
            <template v-else-if="!u.es_usted">
              <v-btn v-if="sinRol(u)" size="small" variant="tonal" color="primary" prepend-icon="mdi-account-check-outline" @click="editar(u)">Asignar rol</v-btn>
              <v-btn v-else size="small" variant="text" icon="mdi-pencil-outline" title="Editar" @click="editar(u)" />
              <v-btn size="small" variant="text" color="error" icon="mdi-delete-outline" title="Eliminar" @click="pedirEliminar(u)" />
            </template>
          </div>
        </div>
      </div>
      <v-pagination v-if="paginas > 1" v-model="pagina" class="mt-4" :length="paginas" :total-visible="5" density="comfortable" rounded="lg" @update:model-value="cargar" />
    </v-card>

    <v-dialog v-model="edicion" max-width="540">
      <v-card class="dialog-card">
        <v-card-title class="dialog-title"><v-icon :icon="editando && sinRol(editando) ? 'mdi-account-check-outline' : 'mdi-pencil-outline'" />{{ editando && sinRol(editando) ? 'Asignar rol' : 'Editar empleado' }}</v-card-title>
        <v-card-text>
          <v-alert v-if="editando && sinRol(editando)" type="info" variant="tonal" density="compact" class="mb-3">Esta persona se registró como invitada. Al asignarle un rol y una sucursal pasa a ser empleada.</v-alert>
          <v-alert v-else-if="editando?.rol_eliminado" type="warning" variant="tonal" density="compact" class="mb-3">Su rol anterior fue eliminado y no le concede permisos. Elija uno nuevo.</v-alert>
          <v-form :key="formKey" ref="formRef" autocomplete="off" @submit.prevent="guardar">
            <v-text-field :model-value="editando?.email" label="Correo" prepend-inner-icon="mdi-email-outline" readonly hint="El correo no se puede cambiar" persistent-hint />
            <v-text-field v-model="form.full_name" class="mt-3" label="Nombre completo" name="empleado-editar-nombre" autocomplete="nope" prepend-inner-icon="mdi-account-outline" :rules="reglas.nombre" />
            <v-select v-model="form.role" label="Rol" :items="opcionesAsignables" item-title="title" item-value="value" prepend-inner-icon="mdi-badge-account-outline" placeholder="Seleccione un rol" no-data-text="No hay roles disponibles" :rules="reglas.rol">
              <template #item="{ props: itemProps, item }">
                <v-list-item v-bind="itemProps" :prepend-icon="item.raw.icon" :subtitle="item.raw.description">
                  <template v-if="item.raw.personalizado" #append><v-chip size="x-small" label color="primary" variant="tonal">Personalizado</v-chip></template>
                </v-list-item>
              </template>
            </v-select>
            <v-combobox v-model="form.branch" label="Sucursal" name="empleado-editar-sucursal" autocomplete="nope" :items="nombresTaller" prepend-inner-icon="mdi-store-outline" hint="Debe coincidir con el nombre de un taller registrado para que pueda operar en él" persistent-hint :rules="reglas.sucursal" />
            <v-alert v-if="errorEdicion" type="error" variant="tonal" density="comfortable" class="mt-4">{{ errorEdicion }}</v-alert>
            <div class="form-actions"><v-btn variant="text" @click="edicion = false">Cancelar</v-btn><v-btn class="submit-btn" type="submit" color="primary" :loading="guardando" prepend-icon="mdi-content-save-outline">Guardar cambios</v-btn></div>
          </v-form>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-dialog v-model="confirmando" max-width="460">
      <v-card class="dialog-card">
        <v-card-title class="dialog-title dialog-title--danger"><v-icon icon="mdi-account-remove-outline" />Eliminar cuenta</v-card-title>
        <v-card-text>
          <p>¿Eliminar la cuenta de <strong>{{ aEliminar?.full_name }}</strong> ({{ aEliminar?.email }})?</p>
          <p class="muted-note">No se borra de la base de datos: la cuenta queda eliminada, <strong>deja de poder ingresar de inmediato</strong> (también su sesión abierta) y puede restaurarse.</p>
          <v-alert v-if="errorAccion" type="error" variant="tonal" density="comfortable" class="mt-3">{{ errorAccion }}</v-alert>
          <div class="form-actions"><v-btn variant="text" :disabled="procesando" @click="confirmando = false">Cancelar</v-btn><v-btn color="error" :loading="procesando" prepend-icon="mdi-delete-outline" @click="eliminar">Eliminar</v-btn></div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar" color="success" location="top right" timeout="4000"><v-icon icon="mdi-check-circle" class="mr-2" />{{ aviso }}</v-snackbar>
  </AppShell>
</template>
