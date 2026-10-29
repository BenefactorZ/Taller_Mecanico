<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import AppShell from '../components/AppShell.vue'
import FiltroSuspendidos from '../components/FiltroSuspendidos.vue'
import FotoProtegida from '../components/FotoProtegida.vue'
import { api } from '../api'
import { auth } from '../auth'
import { FOTO_MAX_TEXTO, validarFoto } from '../talleres'
import { ANIO_MINIMO, anioMaximo, normalizarCodigo, validarAnio, validarKilometraje, validarPlaca, validarTexto, validarVin } from '../vehiculos'
import { tienePermiso, type PaginaVehiculos, type Vehiculo } from '../types'

const TAMANO = 8
const usuario = auth.user()
const puedeRegistrar = tienePermiso(usuario, 'vehiculos.registrar')
const veTaller = usuario?.role === 'ADMINISTRADOR'
const filtros = reactive({ buscar: '', eliminados: false })
const pagina = ref(1)
const resultado = ref<PaginaVehiculos | null>(null)
const loading = ref(true); const error = ref('')
const plural = (n: number, uno: string, varios: string) => `${n} ${n === 1 ? uno : varios}`
const paginas = computed(() => (resultado.value ? Math.max(1, Math.ceil(resultado.value.total / resultado.value.tamano)) : 1))

async function cargar() {
  loading.value = true; error.value = ''
  try {
    const consulta = new URLSearchParams({ pagina: String(pagina.value), tamano: String(TAMANO) })
    if (filtros.buscar.trim()) consulta.set('buscar', filtros.buscar.trim())
    if (filtros.eliminados) consulta.set('estado', 'ELIMINADO')
    resultado.value = await api<PaginaVehiculos>(`/vehiculos?${consulta}`)
  } catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible cargar los vehículos' }
  finally { loading.value = false }
}
let temporizador: ReturnType<typeof setTimeout> | undefined
watch(() => filtros.buscar, () => { clearTimeout(temporizador); temporizador = setTimeout(() => { pagina.value = 1; void cargar() }, 350) })
watch(() => filtros.eliminados, () => { pagina.value = 1; void cargar() })
onBeforeUnmount(() => clearTimeout(temporizador))
onMounted(cargar)

// ---- Modificar: el cliente y el taller quedan bloqueados; la imagen sólo se cambia si se elige otra ----
type FormRef = { validate: () => Promise<{ valid: boolean }> }
const edicion = ref(false); const editando = ref<Vehiculo | null>(null); const formRef = ref<FormRef | null>(null); const formKey = ref(0)
const form = reactive({ vin: '', placa: '', marca: '', modelo: '', anio: '', color: '', kilometraje: '' })
const guardando = ref(false); const errorEdicion = ref(''); const aviso = ref(''); const snackbar = ref(false)
const foto = ref<File | null>(null); const fotoError = ref(''); const inputFoto = ref<HTMLInputElement | null>(null)
const reglas = {
  vin: [(v: string) => validarVin(v)], placa: [(v: string) => validarPlaca(v)], marca: [validarTexto('La marca', 2, 40)], modelo: [validarTexto('El modelo', 1, 60)],
  anio: [(v: string) => validarAnio(v)], color: [validarTexto('El color', 3, 30)], kilometraje: [(v: string) => validarKilometraje(v)],
}
const delVehiculo = (v: Vehiculo) => ({ vin: v.vin, placa: v.placa, marca: v.marca, modelo: v.modelo, anio: String(v.anio), color: v.color, kilometraje: v.kilometraje === null ? '' : String(v.kilometraje) })
function abrirEdicion(v: Vehiculo) {
  editando.value = v; Object.assign(form, delVehiculo(v)); foto.value = null; fotoError.value = ''; errorEdicion.value = ''; formKey.value++; edicion.value = true
}
const hayCambios = computed(() => !!editando.value && (!!foto.value || (Object.keys(form) as (keyof typeof form)[]).some((k) => form[k].trim() !== delVehiculo(editando.value as Vehiculo)[k])))
async function elegirFoto(e: Event) {
  const input = e.target as HTMLInputElement; const archivo = input.files?.[0] ?? null; input.value = ''
  fotoError.value = archivo ? await validarFoto(archivo, 'la imagen del vehículo') : ''; foto.value = fotoError.value ? null : archivo
}
async function guardar() {
  errorEdicion.value = ''
  if (!(await formRef.value?.validate())?.valid) { errorEdicion.value = 'Revise los campos marcados en rojo.'; return }
  const datos = new FormData()
  for (const [campo, valor] of Object.entries(form)) datos.append(campo, valor.trim())
  if (foto.value) datos.append('foto', foto.value)
  guardando.value = true
  try {
    await api<Vehiculo>(`/vehiculos/${editando.value?.id}`, { method: 'PUT', body: datos })
    edicion.value = false; aviso.value = 'Vehículo actualizado.'; snackbar.value = true; await cargar()
  } catch (e) { errorEdicion.value = e instanceof Error ? e.message : 'No fue posible guardar los cambios' }
  finally { guardando.value = false }
}

// ---- Eliminar (borrado lógico) y restaurar ----
const eliminando = ref(false); const aEliminar = ref<Vehiculo | null>(null); const procesando = ref(false)
function pedirEliminar(v: Vehiculo) { aEliminar.value = v; eliminando.value = true }
async function eliminar() {
  if (!aEliminar.value) return
  procesando.value = true
  try { await api(`/vehiculos/${aEliminar.value.id}`, { method: 'DELETE' }); eliminando.value = false; aviso.value = 'Vehículo eliminado. Puede restaurarlo desde «Eliminados».'; snackbar.value = true; await cargar() }
  catch (e) { eliminando.value = false; error.value = e instanceof Error ? e.message : 'No fue posible eliminar el vehículo' }
  finally { procesando.value = false }
}
async function restaurar(v: Vehiculo) {
  try { await api(`/vehiculos/${v.id}/restaurar`, { method: 'POST' }); aviso.value = 'Vehículo restaurado.'; snackbar.value = true; await cargar() }
  catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible restaurar el vehículo' }
}
</script>

<template>
  <AppShell section="Vehículos" title="Vehículos">
    <div class="page-head">
      <div class="page-head__icon"><v-icon icon="mdi-car-outline" /></div>
      <div class="page-head__grow"><span class="eyebrow">Módulo · Vehículos</span><h1>Vehículos</h1><p>Vehículos registrados y el cliente al que pertenecen.</p></div>
      <v-btn v-if="puedeRegistrar" class="submit-btn d-none d-sm-flex" color="primary" size="large" prepend-icon="mdi-plus" to="/vehiculos/nuevo">Registrar vehículo</v-btn>
    </div>

    <v-card class="panel-card" elevation="0">
      <div class="emp-filtros">
        <v-text-field v-model="filtros.buscar" class="emp-filtros__buscar" label="Buscar por placa, VIN, marca, modelo o cliente" name="vehiculos-buscar" autocomplete="nope" prepend-inner-icon="mdi-magnify" clearable hide-details />
        <FiltroSuspendidos v-model="filtros.eliminados" />
      </div>
      <div class="emp-atajos">
        <span v-if="resultado" class="muted-note">{{ plural(resultado.total, filtros.eliminados ? 'vehículo suspendido' : 'vehículo', filtros.eliminados ? 'vehículos suspendidos' : 'vehículos') }}</span>
        
      </div>

      <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mt-4" closable @click:close="error = ''">{{ error }}</v-alert>

      <div v-if="loading && !resultado" class="role-list mt-4"><v-skeleton-loader v-for="n in 4" :key="n" type="list-item-two-line" /></div>
      <div v-else-if="resultado && !resultado.items.length" class="empty-state empty-state--lg"><v-icon icon="mdi-car-off" /><p>{{ filtros.buscar.trim() ? 'No hay vehículos con esa búsqueda.' : filtros.eliminados ? 'No hay vehículos suspendidos.' : 'Aún no hay vehículos registrados.' }}</p></div>
      <div v-else-if="resultado" class="role-table mt-4" :class="{ 'is-loading': loading }">
        <div v-for="v in resultado.items" :key="v.id" class="role-row vehiculo-row">
          <FotoProtegida :ruta="`/vehiculos/${v.id}/foto`" :tiene="v.tiene_foto" :tamano="72" icono="mdi-car-outline" />
          <div class="role-row__body">
            <strong>{{ v.marca }} {{ v.modelo }} {{ v.anio }}</strong>
            <code>{{ v.placa }}</code>
            <p><v-icon icon="mdi-account-outline" size="14" /> {{ v.cliente }}<template v-if="veTaller"> · <v-icon icon="mdi-garage-variant" size="14" /> {{ v.taller }}</template></p>
            <div class="vehiculo-row__datos">
              <v-chip size="x-small" label variant="tonal" prepend-icon="mdi-barcode">{{ v.vin }}</v-chip>
              <v-chip size="x-small" label variant="tonal" prepend-icon="mdi-palette-outline">{{ v.color }}</v-chip>
              <v-chip v-if="v.kilometraje !== null" size="x-small" label variant="tonal" prepend-icon="mdi-speedometer">{{ v.kilometraje.toLocaleString('es-MX') }} km</v-chip>
            </div>
          </div>
          <v-chip size="small" label variant="tonal" :color="v.estado === 'ACTIVO' ? 'success' : 'error'">{{ v.estado === 'ACTIVO' ? 'Activo' : 'Suspendido' }}</v-chip>
          <div v-if="puedeRegistrar" class="vehiculo-row__acciones">
            <template v-if="v.estado === 'ACTIVO'">
              <v-btn size="small" variant="text" icon="mdi-pencil-outline" title="Modificar" @click="abrirEdicion(v)" />
              <v-btn size="small" variant="text" color="error" icon="mdi-delete-outline" title="Eliminar" @click="pedirEliminar(v)" />
            </template>
            <v-btn v-else size="small" variant="tonal" prepend-icon="mdi-restore" @click="restaurar(v)">Restaurar</v-btn>
          </div>
        </div>
      </div>
      <v-pagination v-if="paginas > 1" v-model="pagina" class="mt-4" :length="paginas" :total-visible="5" density="comfortable" rounded="lg" @update:model-value="cargar" />
    </v-card>

    <v-dialog v-model="edicion" max-width="560">
      <v-card class="dialog-card">
        <v-card-title class="dialog-title"><v-icon icon="mdi-car-cog" />Modificar vehículo</v-card-title>
        <v-card-text>
          <v-form :key="formKey" ref="formRef" autocomplete="off" @submit.prevent="guardar">
            <v-text-field :model-value="editando?.cliente" class="modal-locked" label="Cliente" prepend-inner-icon="mdi-account-outline" append-inner-icon="mdi-lock-outline" readonly disabled hint="El cliente y el taller no se pueden cambiar" persistent-hint />
            <v-text-field :model-value="form.vin" class="mt-4" label="VIN *" name="vehiculo-editar-vin" autocomplete="nope" maxlength="20" prepend-inner-icon="mdi-barcode" :rules="reglas.vin" @update:model-value="(v: string) => (form.vin = normalizarCodigo(v))" />
            <v-text-field :model-value="form.placa" label="Placa *" name="vehiculo-editar-placa" autocomplete="nope" maxlength="10" prepend-inner-icon="mdi-card-text-outline" :rules="reglas.placa" @update:model-value="(v: string) => (form.placa = (v ?? '').toUpperCase())" />
            <v-text-field v-model="form.marca" label="Marca *" name="vehiculo-editar-marca" autocomplete="nope" prepend-inner-icon="mdi-car-info" :rules="reglas.marca" />
            <v-text-field v-model="form.modelo" label="Modelo *" name="vehiculo-editar-modelo" autocomplete="nope" prepend-inner-icon="mdi-car-side" :rules="reglas.modelo" />
            <v-text-field v-model="form.anio" label="Año *" name="vehiculo-editar-anio" autocomplete="nope" inputmode="numeric" maxlength="4" :placeholder="`${ANIO_MINIMO} a ${anioMaximo()}`" prepend-inner-icon="mdi-calendar-outline" :rules="reglas.anio" />
            <v-text-field v-model="form.color" label="Color *" name="vehiculo-editar-color" autocomplete="nope" prepend-inner-icon="mdi-palette-outline" :rules="reglas.color" />
            <v-text-field v-model="form.kilometraje" label="Kilometraje (opcional)" name="vehiculo-editar-km" autocomplete="nope" inputmode="numeric" suffix="km" prepend-inner-icon="mdi-speedometer" :rules="reglas.kilometraje" />
            <div class="file-row">
              <v-btn variant="tonal" color="primary" size="small" prepend-icon="mdi-paperclip" @click="inputFoto?.click()">Cambiar imagen</v-btn>
              <span class="file-row__name">{{ foto?.name ?? 'Se conserva la imagen actual' }}</span>
              <v-btn v-if="foto" icon="mdi-close" size="x-small" variant="text" title="Conservar la actual" @click="foto = null" />
              <input ref="inputFoto" class="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" @change="elegirFoto">
            </div>
            <small class="muted-note">JPG, PNG o WebP. Máximo {{ FOTO_MAX_TEXTO }}.</small>
            <div v-if="fotoError" class="field-error"><v-icon icon="mdi-alert-circle-outline" size="16" />{{ fotoError }}</div>
            <v-alert v-if="errorEdicion" type="error" variant="tonal" density="comfortable" class="mt-4">{{ errorEdicion }}</v-alert>
            <div class="form-actions"><v-btn variant="text" @click="edicion = false">Cancelar</v-btn><v-btn class="submit-btn" type="submit" color="primary" :loading="guardando" :disabled="!hayCambios" prepend-icon="mdi-content-save-outline">Guardar cambios</v-btn></div>
          </v-form>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-dialog v-model="eliminando" max-width="460">
      <v-card class="dialog-card">
        <v-card-title class="dialog-title dialog-title--danger"><v-icon icon="mdi-delete-outline" />Eliminar vehículo</v-card-title>
        <v-card-text>
          <p>¿Eliminar el <strong>{{ aEliminar?.marca }} {{ aEliminar?.modelo }} {{ aEliminar?.anio }}</strong> (placa {{ aEliminar?.placa }}) de {{ aEliminar?.cliente }}?</p>
          <p class="muted-note">Es un borrado lógico: el vehículo deja de listarse, pero sus datos se conservan y puede restaurarse.</p>
          <div class="form-actions"><v-btn variant="text" :disabled="procesando" @click="eliminando = false">Cancelar</v-btn><v-btn color="error" :loading="procesando" prepend-icon="mdi-delete-outline" @click="eliminar">Eliminar</v-btn></div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar" color="success" location="top right" timeout="4000"><v-icon icon="mdi-check-circle" class="mr-2" />{{ aviso }}</v-snackbar>
  </AppShell>
</template>
