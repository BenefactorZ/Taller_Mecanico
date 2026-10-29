<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import AppShell from '../components/AppShell.vue'
import FiltroSuspendidos from '../components/FiltroSuspendidos.vue'
import { api, ApiError } from '../api'
import { auth } from '../auth'
import { iniciales, limpiarNombre, normalizarCorreo, normalizarTelefono, validarCorreo, validarNombre, validarTelefono } from '../clientes'
import { etiquetaEstadoCliente, tienePermiso, type ClienteAdmin, type Movimiento, type PaginaClientesAdmin, type Taller } from '../types'

type FormRef = { validate: () => Promise<{ valid: boolean }>; resetValidation: () => void }
const TAMANO = 8
const usuario = auth.user()
const puedeSuspender = tienePermiso(usuario, 'clientes.suspender') // sólo el administrador
const veTodosLosTalleres = usuario?.role === 'ADMINISTRADOR'
const puedeRegistrarVehiculo = tienePermiso(usuario, 'vehiculos.registrar')

const filtros = reactive({ buscar: '', estado: 'ACTIVO' as string | null, taller: null as number | null })
const pagina = ref(1)
const resultado = ref<PaginaClientesAdmin | null>(null)
const talleres = ref<Taller[]>([])
const loading = ref(true); const error = ref(''); const aviso = ref(''); const snackbar = ref(false)
const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`
const suspendido = (c: ClienteAdmin) => c.estado === 'INACTIVO'
const paginas = computed(() => (resultado.value ? Math.max(1, Math.ceil(resultado.value.total / resultado.value.tamano)) : 1))
const fecha = (iso: string) => new Date(iso.endsWith('Z') ? iso : `${iso}Z`).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' })

async function cargar() {
  loading.value = true; error.value = ''
  try {
    const consulta = new URLSearchParams({ pagina: String(pagina.value), tamano: String(TAMANO) })
    if (filtros.buscar.trim()) consulta.set('buscar', filtros.buscar.trim())
    if (filtros.estado) consulta.set('estado', filtros.estado)
    if (filtros.taller) consulta.set('taller_id', String(filtros.taller))
    resultado.value = await api<PaginaClientesAdmin>(`/administracion/clientes?${consulta}`)
  } catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible cargar los clientes' }
  finally { loading.value = false }
}

// La búsqueda espera a que se deje de escribir; los demás filtros recargan al instante y siempre desde la primera página
let temporizador: ReturnType<typeof setTimeout> | undefined
watch(() => filtros.buscar, () => { clearTimeout(temporizador); temporizador = setTimeout(() => { pagina.value = 1; void cargar() }, 350) })
watch(() => [filtros.estado, filtros.taller], () => { pagina.value = 1; void cargar() })
onBeforeUnmount(() => clearTimeout(temporizador))
onMounted(async () => {
  if (veTodosLosTalleres) talleres.value = await api<Taller[]>('/talleres').catch(() => [])
  await cargar()
})

// ---- Actualizar datos: ventana modal con la información del cliente (el taller asignado no se puede cambiar) ----
const edicion = ref(false); const formRef = ref<FormRef | null>(null); const formKey = ref(0)
const editando = ref<ClienteAdmin | null>(null)
const form = reactive({ nombre_completo: '', telefono: '', correo: '' })
const errorEdicion = ref(''); const coincidencia = ref(false); const guardando = ref(false)
const hayCambios = computed(() => !!editando.value && (limpiarNombre(form.nombre_completo) !== editando.value.nombre_completo
  || normalizarTelefono(form.telefono) !== (editando.value.telefono ?? '') || normalizarCorreo(form.correo) !== (editando.value.correo ?? '')))
const reglas = { nombre: [(v: string) => validarNombre(v ?? '')], telefono: [(v: string) => validarTelefono(v ?? '')], correo: [(v: string) => validarCorreo(v ?? '')] }

function actualizar(c: ClienteAdmin) {
  editando.value = c; errorEdicion.value = ''; coincidencia.value = false
  Object.assign(form, { nombre_completo: c.nombre_completo, telefono: c.telefono ?? '', correo: c.correo ?? '' })
  formKey.value++; edicion.value = true
}
async function guardar(confirmar = false) {
  errorEdicion.value = ''
  if (!editando.value) return
  if (!(await formRef.value?.validate())?.valid) { errorEdicion.value = 'Revise los campos marcados en rojo.'; return }
  guardando.value = true
  try {
    const c = await api<ClienteAdmin>(`/administracion/clientes/${editando.value.id}`, {
      method: 'PUT', body: JSON.stringify({ nombre_completo: form.nombre_completo, telefono: form.telefono, correo: form.correo, taller_id: editando.value.taller_id, confirmar }),
    })
    aviso.value = `Se actualizaron los datos de ${c.nombre_completo}. El cambio quedó registrado en su historial.`; snackbar.value = true; edicion.value = false; await cargar()
  } catch (e) {
    coincidencia.value = e instanceof ApiError && e.codigo === 'COINCIDENCIA'
    errorEdicion.value = e instanceof Error ? e.message : 'No fue posible guardar los cambios'
  } finally { guardando.value = false }
}

// ---- Suspender (sólo administrador) y reactivar ----
const suspendiendo = ref(false); const aSuspender = ref<ClienteAdmin | null>(null); const motivo = ref(''); const errorSuspension = ref(''); const procesando = ref(false)
function pedirSuspension(c: ClienteAdmin) { aSuspender.value = c; motivo.value = ''; errorSuspension.value = ''; suspendiendo.value = true }
async function suspender() {
  if (!aSuspender.value) return
  if (motivo.value.trim().length < 3) { errorSuspension.value = 'Escriba el motivo (al menos 3 caracteres)'; return }
  procesando.value = true; errorSuspension.value = ''
  try {
    await api(`/administracion/clientes/${aSuspender.value.id}/suspender`, { method: 'POST', body: JSON.stringify({ motivo: motivo.value }) })
    aviso.value = `${aSuspender.value.nombre_completo} quedó suspendido.`; snackbar.value = true; suspendiendo.value = false; await cargar()
  } catch (e) { errorSuspension.value = e instanceof Error ? e.message : 'No fue posible suspender al cliente' }
  finally { procesando.value = false }
}
async function reactivar(c: ClienteAdmin) {
  error.value = ''
  try { await api(`/administracion/clientes/${c.id}/reactivar`, { method: 'POST' }); aviso.value = `${c.nombre_completo} se reactivó.`; snackbar.value = true; await cargar() }
  catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible reactivar al cliente' }
}

// ---- Historial (trazabilidad) ----
const verHistorial = ref(false); const historialDe = ref<ClienteAdmin | null>(null); const movimientos = ref<Movimiento[]>([]); const cargandoHistorial = ref(false); const errorHistorial = ref('')
const ACCIONES: Record<string, { texto: string; icono: string }> = {
  ALTA_CUSTOMER: { texto: 'Alta del cliente', icono: 'mdi-account-plus-outline' },
  ACTUALIZAR_CUSTOMER: { texto: 'Datos actualizados', icono: 'mdi-pencil-outline' },
  SUSPENDER_CUSTOMER: { texto: 'Cliente suspendido', icono: 'mdi-account-lock-outline' },
  REACTIVAR_CUSTOMER: { texto: 'Cliente reactivado', icono: 'mdi-account-check-outline' },
  ALTA_VEHICULO: { texto: 'Vehículo registrado', icono: 'mdi-car-outline' },
}
async function abrirHistorial(c: ClienteAdmin) {
  historialDe.value = c; movimientos.value = []; errorHistorial.value = ''; cargandoHistorial.value = true; verHistorial.value = true
  try { movimientos.value = await api<Movimiento[]>(`/administracion/clientes/${c.id}/historial`) }
  catch (e) { errorHistorial.value = e instanceof Error ? e.message : 'No fue posible cargar el historial' }
  finally { cargandoHistorial.value = false }
}
</script>

<template>
  <AppShell section="Clientes" title="Administrar clientes">
    <div class="page-head">
      <div class="page-head__icon"><v-icon icon="mdi-account-cog-outline" /></div>
      <div class="page-head__grow"><span class="eyebrow">Administración · Clientes</span><h1>Administrar clientes</h1><p>Consulte los clientes (ID, nombre, teléfono y correo), actualice sus datos con trazabilidad y revise su historial.<template v-if="puedeSuspender"> Como administrador también puede suspenderlos y reactivarlos.</template></p></div>
      <v-btn v-if="puedeRegistrarVehiculo" class="submit-btn d-none d-sm-flex" color="primary" size="large" prepend-icon="mdi-car-arrow-right" to="/vehiculos/nuevo">Registrar vehículo</v-btn>
    </div>

    <v-card class="panel-card" elevation="0">
      <div class="emp-filtros">
        <v-text-field v-model="filtros.buscar" class="emp-filtros__buscar" label="Buscar por nombre, teléfono o correo" name="clientes-buscar" autocomplete="nope" prepend-inner-icon="mdi-magnify" clearable hide-details />
        <FiltroSuspendidos :model-value="filtros.estado === 'INACTIVO'" @update:model-value="(v: boolean) => (filtros.estado = v ? 'INACTIVO' : 'ACTIVO')" />
        <v-select v-if="veTodosLosTalleres" v-model="filtros.taller" class="emp-filtros__rol" label="Taller" :items="talleres" item-title="nombre" item-value="id" clearable hide-details prepend-inner-icon="mdi-garage-variant" placeholder="Todos los talleres" />
      </div>
      <div class="emp-atajos"><span v-if="resultado" class="muted-note">{{ plural(resultado.total, filtros.estado === 'INACTIVO' ? 'cliente suspendido' : 'cliente', filtros.estado === 'INACTIVO' ? 'clientes suspendidos' : 'clientes') }}</span></div>

      <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mt-4" closable @click:close="error = ''">{{ error }}</v-alert>

      <div v-if="loading && !resultado" class="role-list mt-4"><v-skeleton-loader v-for="n in 4" :key="n" type="list-item-two-line" /></div>
      <div v-else-if="resultado && !resultado.items.length" class="empty-state empty-state--lg"><v-icon icon="mdi-account-search-outline" /><p>No hay clientes con esos filtros.</p></div>
      <div v-else-if="resultado" class="role-table mt-4" :class="{ 'is-loading': loading }">
        <div v-for="c in resultado.items" :key="c.id" class="role-row cli-row" :class="{ 'is-deleted': suspendido(c) }">
          <v-avatar class="avatar-initials" size="42">{{ iniciales(c.nombre_completo) }}</v-avatar>
          <div class="role-row__body">
            <strong>{{ c.nombre_completo }}</strong>
            <span class="emp-row__correo"><v-icon icon="mdi-phone-outline" size="14" />{{ c.telefono ?? 'Sin teléfono' }}</span>
            <span class="emp-row__correo"><v-icon icon="mdi-email-outline" size="14" />{{ c.correo ?? 'Sin correo' }}</span>
            <p><v-icon icon="mdi-pound" size="14" /> ID {{ c.id }} · <v-icon icon="mdi-garage-variant" size="14" /> {{ c.taller }}
              <v-chip v-if="c.datos_incompletos" class="ml-1" size="x-small" label color="warning" variant="tonal" prepend-icon="mdi-alert-outline">Datos incompletos: actualícelo</v-chip>
            </p>
          </div>
          <div class="cli-row__chips">
            <v-chip size="small" label variant="tonal" prepend-icon="mdi-car-outline">{{ plural(c.vehiculos, 'vehículo', 'vehículos') }}</v-chip>
            <v-chip size="small" label variant="tonal" :color="suspendido(c) ? 'warning' : 'success'">{{ etiquetaEstadoCliente(c.estado) }}</v-chip>
          </div>
          <div class="role-row__actions">
            <v-btn size="small" variant="text" icon="mdi-history" title="Historial" @click="abrirHistorial(c)" />
            <v-btn v-if="!suspendido(c) && puedeRegistrarVehiculo" size="small" variant="text" icon="mdi-car-arrow-right" title="Registrar vehículo" :to="`/vehiculos/nuevo?cliente=${c.id}`" />
            <v-btn v-if="!suspendido(c)" size="small" variant="text" icon="mdi-pencil-outline" title="Actualizar datos" @click="actualizar(c)" />
            <template v-if="puedeSuspender">
              <v-btn v-if="suspendido(c)" size="small" variant="tonal" color="primary" prepend-icon="mdi-account-check-outline" @click="reactivar(c)">Reactivar</v-btn>
              <v-btn v-else size="small" variant="text" color="warning" icon="mdi-account-lock-outline" title="Suspender" @click="pedirSuspension(c)" />
            </template>
          </div>
        </div>
      </div>
      <v-pagination v-if="paginas > 1" v-model="pagina" class="mt-4" :length="paginas" :total-visible="5" density="comfortable" rounded="lg" @update:model-value="cargar" />
    </v-card>

    <!-- Actualizar datos: toda la información del cliente; sólo el taller asignado queda bloqueado -->
    <v-dialog v-model="edicion" max-width="560">
      <v-card class="dialog-card">
        <v-card-title class="dialog-title"><v-icon icon="mdi-account-edit-outline" />Actualizar datos del cliente</v-card-title>
        <v-card-text>
          <dl v-if="editando" class="summary-list">
            <div><dt><v-icon icon="mdi-pound" size="16" />ID</dt><dd>{{ editando.id }}</dd></div>
            <div><dt><v-icon icon="mdi-check-decagram-outline" size="16" />Estado</dt><dd>{{ etiquetaEstadoCliente(editando.estado) }}</dd></div>
            <div><dt><v-icon icon="mdi-calendar-outline" size="16" />Cliente desde</dt><dd>{{ fecha(editando.created_at) }}</dd></div>
            <div><dt><v-icon icon="mdi-car-outline" size="16" />Vehículos</dt><dd>{{ editando.vehiculos }}</dd></div>
          </dl>
          <v-form :key="formKey" ref="formRef" autocomplete="off" class="mt-4" @submit.prevent="guardar(false)">
            <v-text-field :model-value="editando?.taller" class="modal-locked" label="Taller asignado" prepend-inner-icon="mdi-garage-variant" append-inner-icon="mdi-lock-outline" readonly disabled hint="El taller asignado no se puede cambiar" persistent-hint />
            <v-text-field v-model="form.nombre_completo" class="mt-4" label="Nombre completo *" name="cliente-editar-nombre" autocomplete="nope" prepend-inner-icon="mdi-account-outline" :rules="reglas.nombre" />
            <v-text-field v-model="form.telefono" label="Teléfono *" name="cliente-editar-telefono" autocomplete="nope" inputmode="tel" prepend-inner-icon="mdi-phone-outline" hint="De 10 a 15 dígitos" persistent-hint :rules="reglas.telefono" />
            <v-text-field v-model="form.correo" class="mt-3" label="Correo *" name="cliente-editar-correo" type="email" autocomplete="nope" prepend-inner-icon="mdi-email-outline" hint="Ej. cliente@correo.com" persistent-hint :rules="reglas.correo" />
            <v-alert v-if="errorEdicion" :type="coincidencia ? 'warning' : 'error'" variant="tonal" density="comfortable" class="mt-4">
              {{ errorEdicion }}
              <template v-if="coincidencia" #append><v-btn size="small" variant="flat" color="warning" :loading="guardando" @click="guardar(true)">Guardar de todos modos</v-btn></template>
            </v-alert>
            <div class="form-actions"><v-btn variant="text" @click="edicion = false">Cancelar</v-btn><v-btn class="submit-btn" type="submit" color="primary" :loading="guardando" :disabled="!hayCambios" prepend-icon="mdi-content-save-outline">Guardar cambios</v-btn></div>
          </v-form>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-dialog v-model="suspendiendo" max-width="480">
      <v-card class="dialog-card">
        <v-card-title class="dialog-title dialog-title--danger"><v-icon icon="mdi-account-lock-outline" />Suspender cliente</v-card-title>
        <v-card-text>
          <p>¿Suspender a <strong>{{ aSuspender?.nombre_completo }}</strong> ({{ aSuspender?.taller }})?</p>
          <p class="muted-note">Un cliente suspendido no puede modificarse ni recibir vehículos hasta que un administrador lo reactive. Sus datos y vehículos se conservan.</p>
          <v-textarea v-model="motivo" class="mt-3" label="Motivo *" rows="2" auto-grow counter="200" maxlength="200" prepend-inner-icon="mdi-text-box-outline" :error-messages="errorSuspension ? [errorSuspension] : []" @update:model-value="errorSuspension = ''" />
          <div class="form-actions"><v-btn variant="text" :disabled="procesando" @click="suspendiendo = false">Cancelar</v-btn><v-btn color="warning" :loading="procesando" prepend-icon="mdi-account-lock-outline" @click="suspender">Suspender</v-btn></div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-dialog v-model="verHistorial" max-width="560" scrollable>
      <v-card class="dialog-card">
        <v-card-title class="dialog-title"><v-icon icon="mdi-history" />Historial de {{ historialDe?.nombre_completo }}</v-card-title>
        <v-card-text>
          <v-skeleton-loader v-if="cargandoHistorial" type="list-item-two-line, list-item-two-line" />
          <v-alert v-else-if="errorHistorial" type="error" variant="tonal" density="comfortable">{{ errorHistorial }}</v-alert>
          <p v-else-if="!movimientos.length" class="muted-note">Todavía no hay movimientos registrados.</p>
          <ul v-else class="historial">
            <li v-for="m in movimientos" :key="m.id">
              <span class="historial__icon"><v-icon :icon="ACCIONES[m.accion]?.icono ?? 'mdi-circle-small'" size="18" /></span>
              <div class="historial__body">
                <strong>{{ ACCIONES[m.accion]?.texto ?? m.accion }}</strong>
                <p v-if="m.detalle">{{ m.detalle }}</p>
                <small>{{ m.usuario }} · {{ fecha(m.fecha) }}</small>
              </div>
            </li>
          </ul>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn variant="text" @click="verHistorial = false">Cerrar</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar" color="success" location="top right" timeout="4000"><v-icon icon="mdi-check-circle" class="mr-2" />{{ aviso }}</v-snackbar>
  </AppShell>
</template>
