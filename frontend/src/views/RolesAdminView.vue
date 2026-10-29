<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import { api } from '../api'
import { ROL_ICONOS, STATUS_ELIMINADO, type Permiso, type RoleDefinition } from '../types'

type FormRef = { validate: () => Promise<{ valid: boolean }>; resetValidation: () => void }
const roles = ref<RoleDefinition[]>([])
const loading = ref(true); const mostrarEliminados = ref(false); const error = ref(''); const aviso = ref(''); const snackbar = ref(false)
const eliminado = (rol: RoleDefinition) => rol.bin_status === STATUS_ELIMINADO
const sistema = computed(() => roles.value.filter((r) => r.es_sistema))
const personalizados = computed(() => roles.value.filter((r) => !r.es_sistema))
const activos = computed(() => personalizados.value.filter((r) => !eliminado(r)).length)
const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`

async function cargar() {
  loading.value = true; error.value = ''
  try { roles.value = await api<RoleDefinition[]>(`/roles?incluir_eliminados=${mostrarEliminados.value}`) }
  catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible cargar los roles' }
  finally { loading.value = false }
}
onMounted(async () => {
  try { catalogo.value = await api<Permiso[]>('/permisos') } catch { catalogo.value = [] }
  await cargar()
})

// ---- Permisos ----
const catalogo = ref<Permiso[]>([])
const grupos = computed(() => {
  const porModulo = new Map<string, Permiso[]>()
  for (const permiso of catalogo.value) porModulo.set(permiso.modulo, [...(porModulo.get(permiso.modulo) ?? []), permiso])
  return [...porModulo].map(([modulo, permisos]) => ({ modulo, permisos }))
})
const dialogoPermisos = ref(false); const rolPermisos = ref<RoleDefinition | null>(null); const seleccion = ref<string[]>([])
const errorPermisos = ref(''); const guardandoPermisos = ref(false)
// Los de administración nunca se delegan, y los roles de fábrica son de sólo lectura
const bloqueado = (permiso: Permiso) => !!rolPermisos.value?.es_sistema || !permiso.delegable
function abrirPermisos(rol: RoleDefinition) { rolPermisos.value = rol; seleccion.value = [...rol.permisos]; errorPermisos.value = ''; dialogoPermisos.value = true }
async function guardarPermisos() {
  if (!rolPermisos.value) return
  guardandoPermisos.value = true; errorPermisos.value = ''
  try {
    await api(`/roles/${rolPermisos.value.id}/permisos`, { method: 'PUT', body: JSON.stringify({ permisos: seleccion.value }) })
    aviso.value = `Los permisos del rol «${rolPermisos.value.name}» se guardaron.`; snackbar.value = true; dialogoPermisos.value = false; await cargar()
  } catch (e) { errorPermisos.value = e instanceof Error ? e.message : 'No fue posible guardar los permisos' }
  finally { guardandoPermisos.value = false }
}

// ---- Editar (sólo roles personalizados) ----
const edicion = ref(false); const formRef = ref<FormRef | null>(null)
const form = ref({ id: 0, code: '', name: '', description: '' }); const errorEdicion = ref(''); const guardando = ref(false)
const nameRules = [(v: string) => v.trim().length >= 3 || 'Ingrese el nombre del rol (mínimo 3 caracteres)', (v: string) => v.trim().length <= 80 || 'Máximo 80 caracteres']
const descRules = [(v: string) => (v ?? '').length <= 250 || 'Máximo 250 caracteres']
function editar(rol: RoleDefinition) { form.value = { id: rol.id, code: rol.code, name: rol.name, description: rol.description ?? '' }; errorEdicion.value = ''; edicion.value = true; formRef.value?.resetValidation() }
async function guardar() {
  errorEdicion.value = ''
  if (!(await formRef.value?.validate())?.valid) { errorEdicion.value = 'Revise los campos marcados en rojo.'; return }
  guardando.value = true
  try {
    await api(`/roles/${form.value.id}`, { method: 'PATCH', body: JSON.stringify({ name: form.value.name, description: form.value.description.trim() || null }) })
    edicion.value = false; aviso.value = `El rol «${form.value.name.trim()}» se actualizó.`; snackbar.value = true; await cargar()
  } catch (e) { errorEdicion.value = e instanceof Error ? e.message : 'No fue posible actualizar el rol' }
  finally { guardando.value = false }
}

// ---- Eliminar (borrado lógico) y restaurar ----
// El rol se conserva aparte del estado del diálogo para que su nombre no desaparezca durante la animación de cierre
const confirmando = ref(false); const rolAEliminar = ref<RoleDefinition | null>(null); const procesando = ref(false); const errorAccion = ref('')
function pedirEliminar(rol: RoleDefinition) { rolAEliminar.value = rol; errorAccion.value = ''; confirmando.value = true }
async function eliminar() {
  if (!rolAEliminar.value) return
  procesando.value = true; errorAccion.value = ''
  try {
    await api(`/roles/${rolAEliminar.value.id}`, { method: 'DELETE' })
    aviso.value = `El rol «${rolAEliminar.value.name}» se eliminó. Puede restaurarlo cuando quiera.`; snackbar.value = true; confirmando.value = false; await cargar()
  } catch (e) { errorAccion.value = e instanceof Error ? e.message : 'No fue posible eliminar el rol' }
  finally { procesando.value = false }
}
async function restaurar(rol: RoleDefinition) {
  error.value = ''
  try { await api(`/roles/${rol.id}/restaurar`, { method: 'POST' }); aviso.value = `El rol «${rol.name}» se restauró.`; snackbar.value = true; await cargar() }
  catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible restaurar el rol' }
}
</script>

<template>
  <AppShell section="Administración" title="Administrar roles">
    <div class="page-head">
      <div class="page-head__icon"><v-icon icon="mdi-badge-account-horizontal-outline" /></div>
      <div class="page-head__grow"><span class="eyebrow">Administración · Roles</span><h1>Administrar roles</h1><p>Todos los roles del sistema. Los de fábrica son de sólo lectura; los personalizados se editan o se eliminan (borrado lógico: se conservan y pueden restaurarse).</p></div>
      <v-btn class="submit-btn d-none d-sm-flex" color="primary" size="large" prepend-icon="mdi-plus" to="/roles/nuevo">Nuevo rol</v-btn>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mb-4" closable @click:close="error = ''">{{ error }}</v-alert>

    <div v-if="loading" class="panel-card"><div class="role-list"><v-skeleton-loader v-for="n in 4" :key="n" type="list-item-two-line" /></div></div>
    <template v-else>
      <v-card class="panel-card mb-5" elevation="0">
        <header class="panel-card__header">
          <div><h2>Roles del sistema</h2><p>De fábrica: sus permisos están definidos en el código. {{ plural(sistema.length, 'rol', 'roles') }}.</p></div>
          <v-chip size="small" variant="tonal" color="primary" prepend-icon="mdi-lock-outline">Sólo lectura</v-chip>
        </header>
        <div class="role-table">
          <div v-for="rol in sistema" :key="rol.id" class="role-row role-row--system">
            <div class="tone-icon tone-blue"><v-icon :icon="ROL_ICONOS[rol.code] ?? 'mdi-badge-account-outline'" size="22" /></div>
            <div class="role-row__body"><strong>{{ rol.name }}</strong><code>{{ rol.code }}</code><p>{{ rol.description || 'Sin descripción' }}</p></div>
            <v-chip size="small" label variant="tonal" prepend-icon="mdi-account-multiple-outline">{{ plural(rol.empleados, 'usuario', 'usuarios') }}</v-chip>
            <v-chip size="small" label variant="tonal" color="primary" prepend-icon="mdi-lock-outline">Sistema</v-chip>
            <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-shield-key-outline" @click="abrirPermisos(rol)">{{ plural(rol.permisos.length, 'permiso', 'permisos') }}</v-btn>
          </div>
        </div>
      </v-card>

      <v-card class="panel-card" elevation="0">
        <header class="panel-card__header">
          <div><h2>Roles personalizados</h2><p>{{ plural(activos, 'activo', 'activos') }}<template v-if="mostrarEliminados && personalizados.length > activos"> · {{ plural(personalizados.length - activos, 'eliminado', 'eliminados') }}</template>. Aparecen al dar de alta empleados.</p></div>
          <v-switch v-model="mostrarEliminados" class="switch-eliminados" label="Mostrar eliminados" color="primary" density="compact" hide-details inset @update:model-value="cargar" />
        </header>
        <div v-if="!personalizados.length" class="empty-state empty-state--lg">
          <v-icon icon="mdi-badge-account-horizontal-outline" /><p>{{ mostrarEliminados ? 'No hay roles personalizados.' : 'Aún no hay roles personalizados.' }}</p>
          <v-btn color="primary" variant="tonal" to="/roles/nuevo">Crear el primero</v-btn>
        </div>
        <div v-else class="role-table">
          <div v-for="rol in personalizados" :key="rol.id" class="role-row" :class="{ 'is-deleted': eliminado(rol) }">
            <div class="tone-icon" :class="eliminado(rol) ? 'tone-gray' : 'tone-orange'"><v-icon icon="mdi-badge-account-outline" size="22" /></div>
            <div class="role-row__body">
              <strong>{{ rol.name }}</strong>
              <code>{{ rol.code }}</code>
              <p>{{ rol.description || 'Sin descripción' }}</p>
            </div>
            <v-chip size="small" label variant="tonal" prepend-icon="mdi-account-multiple-outline">{{ plural(rol.empleados, 'empleado', 'empleados') }}</v-chip>
            <v-chip size="small" label variant="tonal" :color="rol.permisos.length ? 'primary' : 'warning'" prepend-icon="mdi-shield-key-outline">{{ plural(rol.permisos.length, 'permiso', 'permisos') }}</v-chip>
            <v-chip size="small" label variant="tonal" :color="eliminado(rol) ? 'error' : 'success'">{{ eliminado(rol) ? 'Eliminado' : 'Activo' }}</v-chip>
            <div class="role-row__actions">
              <template v-if="eliminado(rol)"><v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-restore" @click="restaurar(rol)">Restaurar</v-btn></template>
              <template v-else>
                <v-btn size="small" variant="text" color="primary" icon="mdi-shield-key-outline" title="Definir permisos" @click="abrirPermisos(rol)" />
                <v-btn size="small" variant="text" icon="mdi-pencil-outline" title="Editar" @click="editar(rol)" />
                <v-btn size="small" variant="text" color="error" icon="mdi-delete-outline" title="Eliminar" @click="pedirEliminar(rol)" />
              </template>
            </div>
          </div>
        </div>
      </v-card>
    </template>

    <v-dialog v-model="dialogoPermisos" max-width="700" scrollable>
      <v-card class="dialog-card">
        <v-card-title class="dialog-title"><v-icon icon="mdi-shield-key-outline" />Permisos de «{{ rolPermisos?.name }}»</v-card-title>
        <v-card-text>
          <v-alert v-if="rolPermisos?.es_sistema" type="info" variant="tonal" density="compact" icon="mdi-lock-outline" class="mb-3">Rol del sistema: sus permisos están definidos en el código y no se pueden cambiar.</v-alert>
          <template v-else>
            <p class="muted-note mb-3">Marque lo que podrán hacer las personas con este rol. Los cambios aplican de inmediato, sin que tengan que volver a ingresar.</p>
            <v-alert v-if="rolPermisos && rolPermisos.empleados > 0" type="warning" variant="tonal" density="compact" class="mb-3">{{ plural(rolPermisos.empleados, 'empleado tiene', 'empleados tienen') }} este rol.</v-alert>
          </template>
          <section v-for="grupo in grupos" :key="grupo.modulo" class="perm-group">
            <h4>{{ grupo.modulo }}</h4>
            <label v-for="permiso in grupo.permisos" :key="permiso.codigo" class="perm-row" :class="{ 'is-locked': bloqueado(permiso) }">
              <v-checkbox-btn v-model="seleccion" :value="permiso.codigo" :disabled="bloqueado(permiso)" density="comfortable" color="primary" />
              <span class="perm-row__text"><strong>{{ permiso.nombre }}</strong><small>{{ permiso.descripcion }}</small></span>
              <v-chip v-if="permiso.en_desarrollo" size="x-small" label color="warning" variant="tonal">En desarrollo</v-chip>
              <v-chip v-if="!permiso.delegable && !rolPermisos?.es_sistema" size="x-small" label variant="tonal" prepend-icon="mdi-lock-outline">Sólo administrador</v-chip>
            </label>
          </section>
        </v-card-text>
        <v-card-text class="perm-footer">
          <v-alert v-if="errorPermisos" type="error" variant="tonal" density="comfortable" class="mb-3">{{ errorPermisos }}</v-alert>
          <div class="form-actions">
            <span class="perm-footer__count">{{ plural(seleccion.length, 'permiso seleccionado', 'permisos seleccionados') }}</span>
            <v-btn variant="text" @click="dialogoPermisos = false">{{ rolPermisos?.es_sistema ? 'Cerrar' : 'Cancelar' }}</v-btn>
            <v-btn v-if="!rolPermisos?.es_sistema" class="submit-btn" color="primary" :loading="guardandoPermisos" prepend-icon="mdi-content-save-outline" @click="guardarPermisos">Guardar permisos</v-btn>
          </div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-dialog v-model="edicion" max-width="520">
      <v-card class="dialog-card">
        <v-card-title class="dialog-title"><v-icon icon="mdi-pencil-outline" />Editar rol</v-card-title>
        <v-card-text>
          <v-form ref="formRef" autocomplete="off" @submit.prevent="guardar">
            <v-text-field :model-value="form.code" label="Clave del rol" prepend-inner-icon="mdi-key-outline" readonly hint="La clave no se puede cambiar" persistent-hint />
            <v-text-field v-model="form.name" class="mt-3" label="Nombre del rol" name="rol-editar-nombre" autocomplete="nope" prepend-inner-icon="mdi-badge-account-outline" :rules="nameRules" />
            <v-textarea v-model="form.description" label="Descripción" name="rol-editar-descripcion" prepend-inner-icon="mdi-text-box-outline" rows="3" auto-grow counter="250" :rules="descRules" />
            <v-alert v-if="errorEdicion" type="error" variant="tonal" density="comfortable" class="mt-2">{{ errorEdicion }}</v-alert>
            <div class="form-actions"><v-btn variant="text" @click="edicion = false">Cancelar</v-btn><v-btn class="submit-btn" type="submit" color="primary" :loading="guardando" prepend-icon="mdi-content-save-outline">Guardar cambios</v-btn></div>
          </v-form>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-dialog v-model="confirmando" max-width="460">
      <v-card class="dialog-card">
        <v-card-title class="dialog-title dialog-title--danger"><v-icon icon="mdi-delete-alert-outline" />Eliminar rol</v-card-title>
        <v-card-text>
          <p>¿Eliminar el rol <strong>{{ rolAEliminar?.name }}</strong> (<code>{{ rolAEliminar?.code }}</code>)?</p>
          <p class="muted-note">No se borra de la base de datos: queda marcado como eliminado y puede restaurarse. Deja de ofrecerse al dar de alta empleados.</p>
          <v-alert v-if="rolAEliminar && rolAEliminar.empleados > 0" type="warning" variant="tonal" density="comfortable" class="mt-3">
            {{ plural(rolAEliminar.empleados, 'empleado tiene', 'empleados tienen') }} este rol y lo conservará{{ rolAEliminar.empleados === 1 ? '' : 'n' }}.
          </v-alert>
          <v-alert v-if="errorAccion" type="error" variant="tonal" density="comfortable" class="mt-3">{{ errorAccion }}</v-alert>
          <div class="form-actions"><v-btn variant="text" :disabled="procesando" @click="confirmando = false">Cancelar</v-btn><v-btn color="error" :loading="procesando" prepend-icon="mdi-delete-outline" @click="eliminar">Eliminar</v-btn></div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar" color="success" location="top right" timeout="4000"><v-icon icon="mdi-check-circle" class="mr-2" />{{ aviso }}</v-snackbar>
  </AppShell>
</template>
