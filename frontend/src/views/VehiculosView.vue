<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import AppShell from '../components/AppShell.vue'
import FiltroSuspendidos from '../components/FiltroSuspendidos.vue'
import FotoProtegida from '../components/FotoProtegida.vue'
import { api } from '../api'
import { auth } from '../auth'
import { FOTO_MAX_TEXTO, validarFoto } from '../talleres'
import { ANIO_MINIMO, anioMaximo, validarAnio, validarKilometraje, validarPlaca, validarTexto } from '../vehiculos'
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
    if (filtros.eliminados) consulta.set('estado', 'SUSPENDIDO')
    resultado.value = await api<PaginaVehiculos>(`/vehiculos?${consulta}`)
  } catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible cargar los vehículos' }
  finally { loading.value = false }
}
let temporizador: ReturnType<typeof setTimeout> | undefined
watch(() => filtros.buscar, () => { clearTimeout(temporizador); temporizador = setTimeout(() => { pagina.value = 1; void cargar() }, 350) })
watch(() => filtros.eliminados, () => { pagina.value = 1; void cargar() })
onBeforeUnmount(() => clearTimeout(temporizador))
onMounted(cargar)

// ---- Modificar: VIN, cliente y taller quedan bloqueados; la imagen sólo se cambia si se elige otra ----
type FormRef = { validate: () => Promise<{ valid: boolean }> }
const edicion = ref(false); const editando = ref<Vehiculo | null>(null); const formRef = ref<FormRef | null>(null); const formKey = ref(0)
const form = reactive({ placa: '', marca: '', modelo: '', anio: '', color: '', kilometraje: '' })
const guardando = ref(false); const errorEdicion = ref(''); const aviso = ref(''); const snackbar = ref(false)
const foto = ref<File | null>(null); const fotoError = ref(''); const inputFoto = ref<HTMLInputElement | null>(null)
const reglas = {
  placa: [(v: string) => validarPlaca(v)], marca: [validarTexto('La marca', 2, 40)], modelo: [validarTexto('El modelo', 1, 60)],
  anio: [(v: string) => validarAnio(v)], color: [validarTexto('El color', 3, 30)], kilometraje: [(v: string) => (v ?? '').trim() ? validarKilometraje(v) : 'El kilometraje es obligatorio'],
}
const delVehiculo = (v: Vehiculo) => ({ placa: v.placa, marca: v.marca, modelo: v.modelo, anio: String(v.anio), color: v.color, kilometraje: v.kilometraje === null ? '' : String(v.kilometraje) })
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

// ---- Suspensión lógica y activación, con confirmación explícita ----
const suspendiendo = ref(false); const aSuspender = ref<Vehiculo | null>(null)
const activando = ref(false); const aActivar = ref<Vehiculo | null>(null); const procesando = ref(false)
function pedirSuspension(v: Vehiculo) { aSuspender.value = v; suspendiendo.value = true }
function pedirActivacion(v: Vehiculo) { aActivar.value = v; activando.value = true }
async function suspender() {
  if (!aSuspender.value) return
  procesando.value = true
  try { await api(`/vehiculos/${aSuspender.value.id}/suspender`, { method: 'POST' }); suspendiendo.value = false; aviso.value = 'Vehículo suspendido. Puede activarlo desde «Suspendidos».'; snackbar.value = true; await cargar() }
  catch (e) { suspendiendo.value = false; error.value = e instanceof Error ? e.message : 'No fue posible suspender el vehículo' }
  finally { procesando.value = false }
}
async function activar() {
  if (!aActivar.value) return
  procesando.value = true
  try { await api(`/vehiculos/${aActivar.value.id}/activar`, { method: 'POST' }); activando.value = false; aviso.value = 'Vehículo activado.'; snackbar.value = true; await cargar() }
  catch (e) { activando.value = false; error.value = e instanceof Error ? e.message : 'No fue posible activar el vehículo' }
  finally { procesando.value = false }
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
              <v-btn size="small" variant="text" color="error" icon="mdi-pause-circle-outline" title="Suspender" @click="pedirSuspension(v)" />
            </template>
            <v-btn v-else size="small" variant="tonal" color="success" prepend-icon="mdi-play-circle-outline" @click="pedirActivacion(v)">Activar</v-btn>
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
            <v-text-field :model-value="editando?.vin" class="modal-locked mt-4" label="VIN" name="vehiculo-editar-vin" prepend-inner-icon="mdi-barcode" append-inner-icon="mdi-lock-outline" readonly disabled hint="El VIN identifica al vehículo y no se puede cambiar" persistent-hint />
            <v-text-field :model-value="form.placa" label="Placa *" name="vehiculo-editar-placa" autocomplete="nope" maxlength="10" prepend-inner-icon="mdi-card-text-outline" :rules="reglas.placa" @update:model-value="(v: string) => (form.placa = (v ?? '').toUpperCase())" />
            <v-text-field v-model="form.marca" label="Marca *" name="vehiculo-editar-marca" autocomplete="nope" prepend-inner-icon="mdi-car-info" :rules="reglas.marca" />
            <v-text-field v-model="form.modelo" label="Modelo *" name="vehiculo-editar-modelo" autocomplete="nope" prepend-inner-icon="mdi-car-side" :rules="reglas.modelo" />
            <v-text-field v-model="form.anio" label="Año *" name="vehiculo-editar-anio" autocomplete="nope" inputmode="numeric" maxlength="4" :placeholder="`${ANIO_MINIMO} a ${anioMaximo()}`" prepend-inner-icon="mdi-calendar-outline" :rules="reglas.anio" />
            <v-text-field v-model="form.color" label="Color *" name="vehiculo-editar-color" autocomplete="nope" prepend-inner-icon="mdi-palette-outline" :rules="reglas.color" />
            <v-text-field v-model="form.kilometraje" label="Kilometraje *" name="vehiculo-editar-km" autocomplete="nope" inputmode="numeric" suffix="km" prepend-inner-icon="mdi-speedometer" :rules="reglas.kilometraje" />
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

    <v-dialog v-model="suspendiendo" max-width="460">
      <v-card class="dialog-card">
        <v-card-title class="dialog-title dialog-title--danger"><v-icon icon="mdi-pause-circle-outline" />Suspender vehículo</v-card-title>
        <v-card-text>
          <p>¿Desea suspender el <strong>{{ aSuspender?.marca }} {{ aSuspender?.modelo }} {{ aSuspender?.anio }}</strong> (placa {{ aSuspender?.placa }}) de {{ aSuspender?.cliente }}?</p>
          <p class="muted-note">El vehículo no se borrará: sus datos e imagen se conservarán y podrá activarlo después.</p>
          <div class="form-actions"><v-btn variant="text" :disabled="procesando" @click="suspendiendo = false">Cancelar</v-btn><v-btn color="error" :loading="procesando" prepend-icon="mdi-pause-circle-outline" @click="suspender">Suspender</v-btn></div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-dialog v-model="activando" max-width="460">
      <v-card class="dialog-card">
        <v-card-title class="dialog-title"><v-icon icon="mdi-play-circle-outline" />Activar vehículo</v-card-title>
        <v-card-text>
          <p>¿Desea activar el <strong>{{ aActivar?.marca }} {{ aActivar?.modelo }} {{ aActivar?.anio }}</strong> (placa {{ aActivar?.placa }}) de {{ aActivar?.cliente }}?</p>
          <p class="muted-note">El vehículo volverá a aparecer entre los activos. Su cliente debe estar activo para continuar.</p>
          <div class="form-actions"><v-btn variant="text" :disabled="procesando" @click="activando = false">Cancelar</v-btn><v-btn color="success" :loading="procesando" prepend-icon="mdi-play-circle-outline" @click="activar">Activar</v-btn></div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar" color="success" location="top right" timeout="4000"><v-icon icon="mdi-check-circle" class="mr-2" />{{ aviso }}</v-snackbar>
  </AppShell>
</template>
