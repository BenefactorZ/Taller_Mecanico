<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import AppShell from '../components/AppShell.vue'
import FiltroSuspendidos from '../components/FiltroSuspendidos.vue'
import FotoTaller from '../components/FotoTaller.vue'
import { api } from '../api'
import { STATUS_ELIMINADO, type PaginaTalleres, type TallerAdmin } from '../types'

const TAMANO = 8
const filtros = reactive({ buscar: '', eliminados: false })
const pagina = ref(1)
const resultado = ref<PaginaTalleres | null>(null)
const loading = ref(true); const error = ref(''); const aviso = ref(''); const snackbar = ref(false)
const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`
const eliminado = (t: TallerAdmin) => t.bin_status === STATUS_ELIMINADO
const paginas = computed(() => (resultado.value ? Math.max(1, Math.ceil(resultado.value.total / resultado.value.tamano)) : 1))
const domicilio = (t: TallerAdmin) => [t.calle, t.colonia, t.codigo_postal && `C.P. ${t.codigo_postal}`, t.municipio, t.estado].filter(Boolean).join(', ')

async function cargar() {
  loading.value = true; error.value = ''
  try {
    const consulta = new URLSearchParams({ pagina: String(pagina.value), tamano: String(TAMANO), solo_eliminados: String(filtros.eliminados) })
    if (filtros.buscar.trim()) consulta.set('buscar', filtros.buscar.trim())
    resultado.value = await api<PaginaTalleres>(`/talleres/administracion?${consulta}`)
  } catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible cargar los talleres' }
  finally { loading.value = false }
}

// La búsqueda espera a que se deje de escribir; el interruptor recarga al instante y siempre desde la primera página
let temporizador: ReturnType<typeof setTimeout> | undefined
watch(() => filtros.buscar, () => { clearTimeout(temporizador); temporizador = setTimeout(() => { pagina.value = 1; void cargar() }, 350) })
watch(() => filtros.eliminados, () => { pagina.value = 1; void cargar() })
onBeforeUnmount(() => clearTimeout(temporizador))
onMounted(cargar)

// ---- Eliminar (borrado lógico) y restaurar ----
// El taller se conserva aparte del estado del diálogo para que su nombre no desaparezca durante la animación de cierre
const confirmando = ref(false); const aEliminar = ref<TallerAdmin | null>(null); const procesando = ref(false); const errorAccion = ref('')
function pedirEliminar(t: TallerAdmin) { aEliminar.value = t; errorAccion.value = ''; confirmando.value = true }
async function eliminar() {
  if (!aEliminar.value) return
  procesando.value = true; errorAccion.value = ''
  try {
    await api(`/talleres/${aEliminar.value.id}`, { method: 'DELETE' })
    aviso.value = `El taller «${aEliminar.value.nombre}» se eliminó. Puede restaurarlo cuando quiera.`; snackbar.value = true; confirmando.value = false
    if (resultado.value && resultado.value.items.length === 1 && pagina.value > 1 && !filtros.eliminados) pagina.value--
    await cargar()
  } catch (e) { errorAccion.value = e instanceof Error ? e.message : 'No fue posible eliminar el taller' }
  finally { procesando.value = false }
}
async function restaurar(t: TallerAdmin) {
  error.value = ''
  try { await api(`/talleres/${t.id}/restaurar`, { method: 'POST' }); aviso.value = `El taller «${t.nombre}» se restauró.`; snackbar.value = true; await cargar() }
  catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible restaurar el taller' }
}
</script>

<template>
  <AppShell section="Talleres" title="Talleres">
    <div class="page-head">
      <div class="page-head__icon"><v-icon icon="mdi-garage-open-variant" /></div>
      <div class="page-head__grow"><span class="eyebrow">Administración · Talleres</span><h1>Talleres</h1><p>Consulte los talleres registrados, corrija sus datos, domicilio o foto, y elimínelos (la eliminación es lógica y se puede restaurar).</p></div>
      <v-btn class="submit-btn d-none d-sm-flex" color="primary" size="large" prepend-icon="mdi-plus" to="/talleres/nuevo">Nuevo taller</v-btn>
    </div>

    <v-card class="panel-card" elevation="0">
      <div class="emp-filtros">
        <v-text-field v-model="filtros.buscar" class="emp-filtros__buscar" label="Buscar por nombre, RFC o municipio" name="talleres-buscar" autocomplete="nope" prepend-inner-icon="mdi-magnify" clearable hide-details />
        <FiltroSuspendidos v-model="filtros.eliminados" />
      </div>
      <div class="emp-atajos"><span v-if="resultado" class="muted-note">{{ plural(resultado.total, filtros.eliminados ? 'taller suspendido' : 'taller', filtros.eliminados ? 'talleres suspendidos' : 'talleres') }}</span></div>

      <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mt-4" closable @click:close="error = ''">{{ error }}</v-alert>

      <div v-if="loading && !resultado" class="role-list mt-4"><v-skeleton-loader v-for="n in 4" :key="n" type="list-item-two-line" /></div>
      <div v-else-if="resultado && !resultado.items.length" class="empty-state empty-state--lg"><v-icon icon="mdi-garage-variant" /><p>{{ filtros.buscar.trim() ? 'No hay talleres con esa búsqueda.' : 'Aún no hay talleres registrados.' }}</p></div>
      <div v-else-if="resultado" class="role-table mt-4" :class="{ 'is-loading': loading }">
        <div v-for="t in resultado.items" :key="t.id" class="role-row taller-row" :class="{ 'is-deleted': eliminado(t) }">
          <FotoTaller :id="t.id" :tiene="t.tiene_foto" :tamano="64" />
          <div class="role-row__body">
            <strong>{{ t.nombre }}</strong>
            <code>{{ t.rfc || 'Sin RFC' }}</code>
            <p v-if="domicilio(t)"><v-icon icon="mdi-map-marker-outline" size="14" /> {{ domicilio(t) }}</p>
            <p v-if="t.email_contacto"><v-icon icon="mdi-email-outline" size="14" /> {{ t.email_contacto }}</p>
            <p v-if="!t.rfc || !t.tiene_foto || !t.codigo_postal"><v-chip size="x-small" label color="warning" variant="tonal" prepend-icon="mdi-alert-outline">Datos incompletos: edítelo para completarlo</v-chip></p>
          </div>
          <div class="taller-row__cuentas">
            <v-chip size="small" label variant="tonal" prepend-icon="mdi-account-group-outline" title="Empleados con este taller como sucursal">{{ plural(t.empleados, 'empleado', 'empleados') }}</v-chip>
            <v-chip size="small" label variant="tonal" prepend-icon="mdi-account-search-outline">{{ plural(t.clientes, 'cliente', 'clientes') }}</v-chip>
          </div>
          <v-chip size="small" label variant="tonal" :color="eliminado(t) ? 'error' : 'success'">{{ eliminado(t) ? 'Suspendido' : 'Activo' }}</v-chip>
          <div class="role-row__actions">
            <v-btn v-if="eliminado(t)" size="small" variant="tonal" color="primary" prepend-icon="mdi-restore" @click="restaurar(t)">Restaurar</v-btn>
            <template v-else>
              <v-btn size="small" variant="text" icon="mdi-pencil-outline" title="Editar" :to="`/talleres/${t.id}/editar`" />
              <v-btn size="small" variant="text" color="error" icon="mdi-delete-outline" title="Eliminar" @click="pedirEliminar(t)" />
            </template>
          </div>
        </div>
      </div>
      <v-pagination v-if="paginas > 1" v-model="pagina" class="mt-4" :length="paginas" :total-visible="5" density="comfortable" rounded="lg" @update:model-value="cargar" />
    </v-card>

    <v-dialog v-model="confirmando" max-width="480">
      <v-card class="dialog-card">
        <v-card-title class="dialog-title dialog-title--danger"><v-icon icon="mdi-garage-alert-variant" />Eliminar taller</v-card-title>
        <v-card-text>
          <p>¿Eliminar el taller <strong>{{ aEliminar?.nombre }}</strong> ({{ aEliminar?.rfc || 'sin RFC' }})?</p>
          <v-alert v-if="aEliminar && aEliminar.empleados" type="warning" variant="tonal" density="compact" class="mt-3">
            {{ plural(aEliminar.empleados, 'empleado tiene', 'empleados tienen') }} este taller como sucursal y <strong>no podrán operar clientes</strong> mientras esté eliminado.
          </v-alert>
          <p class="muted-note">No se borra de la base de datos: el taller, sus clientes y su historial se conservan, y puede restaurarse en cualquier momento.</p>
          <v-alert v-if="errorAccion" type="error" variant="tonal" density="comfortable" class="mt-3">{{ errorAccion }}</v-alert>
          <div class="form-actions"><v-btn variant="text" :disabled="procesando" @click="confirmando = false">Cancelar</v-btn><v-btn color="error" :loading="procesando" prepend-icon="mdi-delete-outline" @click="eliminar">Eliminar</v-btn></div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar" color="success" location="top right" timeout="4000"><v-icon icon="mdi-check-circle" class="mr-2" />{{ aviso }}</v-snackbar>
  </AppShell>
</template>
