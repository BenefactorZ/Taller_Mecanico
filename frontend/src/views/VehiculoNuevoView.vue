<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { api } from '../api'
import { FOTO_MAX_TEXTO, validarFoto } from '../talleres'
import { iniciales } from '../clientes'
import { ANIO_MINIMO, anioMaximo, normalizarCodigo, validarAnio, validarKilometraje, validarPlaca, validarTexto, validarVin } from '../vehiculos'
import type { ClienteAdmin, PaginaClientesAdmin, Vehiculo } from '../types'

type FormRef = { validate: () => Promise<{ valid: boolean }>; resetValidation: () => void }
const route = useRoute()
const formRef = ref<FormRef | null>(null); const formKey = ref(0)
const vacio = () => ({ vin: '', placa: '', marca: '', modelo: '', anio: '', color: '', kilometraje: '' })
const form = reactive(vacio())
const loading = ref(false); const error = ref(''); const exito = ref(''); const snackbar = ref(false)

// ---- Cliente: se busca entre los clientes activos que la persona puede administrar ----
const clienteId = ref<number | null>(null); const clientes = ref<ClienteAdmin[]>([]); const buscando = ref(false); const errorCliente = ref('')
const seleccionado = computed(() => clientes.value.find((c) => c.id === clienteId.value) ?? null)
let temporizador: ReturnType<typeof setTimeout> | undefined
async function buscarClientes(texto: string) {
  buscando.value = true
  try {
    const consulta = new URLSearchParams({ estado: 'ACTIVO', tamano: '10' })
    if (texto.trim()) consulta.set('buscar', texto.trim())
    const encontrados = (await api<PaginaClientesAdmin>(`/administracion/clientes?${consulta}`)).items
    const actual = seleccionado.value
    clientes.value = actual && !encontrados.some((c) => c.id === actual.id) ? [actual, ...encontrados] : encontrados
  } catch { /* sin conexión: se conserva la lista actual */ }
  finally { buscando.value = false }
}
function alEscribirCliente(texto: string) {
  if (seleccionado.value && texto === seleccionado.value.nombre_completo) return
  clearTimeout(temporizador); temporizador = setTimeout(() => void buscarClientes(texto ?? ''), 300)
}
onBeforeUnmount(() => clearTimeout(temporizador))
onMounted(async () => {
  const previo = Number(route.query.cliente)
  if (previo) {
    try { const c = await api<ClienteAdmin>(`/administracion/clientes/${previo}`); if (c.estado === 'ACTIVO') { clientes.value = [c]; clienteId.value = c.id } } catch { /* se elige manualmente */ }
  }
  await buscarClientes('')
})

// ---- Imagen ----
const foto = ref<File | null>(null); const fotoUrl = ref(''); const fotoError = ref(''); const arrastrando = ref(false)
const inputFoto = ref<HTMLInputElement | null>(null)
function limpiarVistaPrevia() { if (fotoUrl.value) URL.revokeObjectURL(fotoUrl.value); fotoUrl.value = '' }
async function asignarFoto(archivo: File | null) {
  limpiarVistaPrevia(); foto.value = archivo; fotoError.value = archivo ? await validarFoto(archivo, 'la imagen del vehículo') : ''
  if (archivo && !fotoError.value) fotoUrl.value = URL.createObjectURL(archivo)
}
const elegirFoto = (e: Event) => { const input = e.target as HTMLInputElement; void asignarFoto(input.files?.[0] ?? null); input.value = '' }
const soltarFoto = (e: DragEvent) => { arrastrando.value = false; void asignarFoto(e.dataTransfer?.files?.[0] ?? null) }
onBeforeUnmount(limpiarVistaPrevia)

// ---- Envío ----
const reglas = {
  cliente: [(v: number | null) => !!v || 'Seleccione el cliente al que pertenece el vehículo'],
  vin: [(v: string) => validarVin(v)], placa: [(v: string) => validarPlaca(v)], marca: [validarTexto('La marca', 2, 40)], modelo: [validarTexto('El modelo', 1, 60)],
  anio: [(v: string) => validarAnio(v)], color: [validarTexto('El color', 3, 30)], kilometraje: [(v: string) => validarKilometraje(v)],
}
async function enviar() {
  error.value = ''; exito.value = ''
  const resultado = await formRef.value?.validate(); fotoError.value = await validarFoto(foto.value, 'la imagen del vehículo')
  if (!resultado?.valid || fotoError.value) {
    error.value = 'Faltan datos o hay campos con errores. Revise los campos marcados en rojo.'
    await nextTick(); document.querySelector('.v-input--error, .dropzone.has-error')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); return
  }
  const datos = new FormData()
  datos.append('customer_id', String(clienteId.value))
  for (const [campo, valor] of Object.entries(form)) datos.append(campo, valor.trim())
  datos.append('foto', foto.value as File)
  loading.value = true
  try {
    const v = await api<Vehiculo>('/vehiculos', { method: 'POST', body: datos })
    exito.value = `Vehículo registrado y activo: ${v.marca} ${v.modelo} ${v.anio}, placa ${v.placa}, asociado a ${v.cliente}.`; snackbar.value = true
    Object.assign(form, vacio()); await asignarFoto(null); formKey.value++
  } catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible registrar el vehículo' }
  finally { loading.value = false }
}
</script>

<template>
  <AppShell section="Vehículos" title="Registrar vehículo">
    <div class="page-head">
      <div class="page-head__icon"><v-icon icon="mdi-car-arrow-right" /></div>
      <div><span class="eyebrow">Módulo · Vehículos</span><h1>Registrar vehículo</h1><p>Capture los datos del vehículo y asócielo a un cliente. Se normaliza, se verifica que no esté duplicado y queda activo.</p></div>
    </div>

    <v-form :key="formKey" ref="formRef" autocomplete="off" @submit.prevent="enviar">
      <div class="taller-layout">
        <div class="taller-col">
          <v-card class="panel-card" elevation="0">
            <section class="form-section">
              <div class="form-section__title"><span class="step-dot"><v-icon icon="mdi-account-outline" size="16" /></span><div><h3>Cliente</h3><p>El vehículo pertenece a un cliente activo del taller.</p></div></div>
              <v-autocomplete v-model="clienteId" :items="clientes" item-title="nombre_completo" item-value="id" label="Cliente *" placeholder="Escriba nombre, teléfono o correo" no-filter :loading="buscando"
                prepend-inner-icon="mdi-account-search-outline" no-data-text="No hay clientes activos con esa búsqueda" :rules="reglas.cliente" @update:search="alEscribirCliente">
                <template #item="{ props: itemProps, item }">
                  <v-list-item v-bind="itemProps" :title="item.raw.nombre_completo" :subtitle="`ID ${item.raw.id} · ${item.raw.telefono ?? 'sin teléfono'} · ${item.raw.correo ?? 'sin correo'} · ${item.raw.taller}`">
                    <template #prepend><v-avatar class="avatar-initials mr-3" size="34">{{ iniciales(item.raw.nombre_completo) }}</v-avatar></template>
                  </v-list-item>
                </template>
              </v-autocomplete>
              <p v-if="seleccionado" class="muted-note mt-1"><v-icon icon="mdi-pound" size="14" /> ID {{ seleccionado.id }} · <v-icon icon="mdi-phone-outline" size="14" /> {{ seleccionado.telefono ?? 'sin teléfono' }} · <v-icon icon="mdi-email-outline" size="14" /> {{ seleccionado.correo ?? 'sin correo' }} · <v-icon icon="mdi-garage-variant" size="14" /> {{ seleccionado.taller }}</p>
            </section>
          </v-card>

          <v-card class="panel-card" elevation="0">
            <section class="form-section">
              <div class="form-section__title"><span class="step-dot"><v-icon icon="mdi-car-outline" size="16" /></span><div><h3>Datos del vehículo</h3><p>Los campos marcados con * son obligatorios.</p></div></div>
              <div class="form-grid">
                <v-text-field :model-value="form.vin" label="VIN *" name="vehiculo-vin" autocomplete="nope" maxlength="20" placeholder="1HGCM82633A004352" prepend-inner-icon="mdi-barcode" hint="17 caracteres, sin I, O ni Q. Se guarda en mayúsculas." persistent-hint :rules="reglas.vin" @update:model-value="(v: string) => (form.vin = normalizarCodigo(v))" />
                <v-text-field :model-value="form.placa" label="Placa *" name="vehiculo-placa" autocomplete="nope" maxlength="10" placeholder="ABC-123-D" prepend-inner-icon="mdi-card-text-outline" hint="5 a 7 caracteres entre letras y números." persistent-hint :rules="reglas.placa" @update:model-value="(v: string) => (form.placa = (v ?? '').toUpperCase())" />
                <v-text-field v-model="form.marca" label="Marca *" name="vehiculo-marca" autocomplete="nope" placeholder="Ej. Toyota" prepend-inner-icon="mdi-car-info" :rules="reglas.marca" />
                <v-text-field v-model="form.modelo" label="Modelo *" name="vehiculo-modelo" autocomplete="nope" placeholder="Ej. Corolla" prepend-inner-icon="mdi-car-side" :rules="reglas.modelo" />
                <v-text-field v-model="form.anio" label="Año *" name="vehiculo-anio" autocomplete="nope" inputmode="numeric" maxlength="4" :placeholder="`${ANIO_MINIMO} a ${anioMaximo()}`" prepend-inner-icon="mdi-calendar-outline" :rules="reglas.anio" />
                <v-text-field v-model="form.color" label="Color *" name="vehiculo-color" autocomplete="nope" placeholder="Ej. Rojo" prepend-inner-icon="mdi-palette-outline" :rules="reglas.color" />
                <v-text-field v-model="form.kilometraje" class="form-grid__wide" label="Kilometraje (opcional)" name="vehiculo-km" autocomplete="nope" inputmode="numeric" placeholder="Ej. 45000" suffix="km" prepend-inner-icon="mdi-speedometer" :rules="reglas.kilometraje" />
              </div>
            </section>
          </v-card>

          <div class="taller-actions">
            <v-alert v-if="error" type="error" variant="tonal" density="comfortable" closable @click:close="error = ''">{{ error }}</v-alert>
            <v-alert v-if="exito" type="success" variant="tonal" density="comfortable" closable @click:close="exito = ''">{{ exito }}</v-alert>
            <div class="form-actions"><v-btn variant="text" to="/vehiculos">Ver vehículos</v-btn><v-btn class="submit-btn" type="submit" color="primary" size="large" :loading="loading" prepend-icon="mdi-car-arrow-right">Registrar vehículo</v-btn></div>
          </div>
        </div>

        <aside class="taller-col">
          <v-card class="panel-card" elevation="0">
            <section class="form-section">
              <div class="form-section__title"><span class="step-dot"><v-icon icon="mdi-camera-outline" size="16" /></span><div><h3>Imagen del vehículo</h3><p>Una fotografía para identificarlo.</p></div></div>
              <label class="dropzone" :class="{ 'is-over': arrastrando, 'has-image': !!fotoUrl, 'has-error': !!fotoError }" @dragover.prevent="arrastrando = true" @dragleave.prevent="arrastrando = false" @drop.prevent="soltarFoto">
                <img v-if="fotoUrl" :src="fotoUrl" alt="Vista previa de la imagen del vehículo">
                <span v-else class="dropzone__empty"><v-icon icon="mdi-car-outline" /><span>Agregue una foto del vehículo.</span><small>Arrastre la imagen aquí o haga clic.</small></span>
                <input ref="inputFoto" class="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" @change="elegirFoto">
              </label>
              <div class="file-row">
                <v-btn variant="tonal" color="primary" size="small" prepend-icon="mdi-paperclip" @click="inputFoto?.click()">Elegir archivo</v-btn>
                <span class="file-row__name">{{ foto?.name ?? 'No se eligió ningún archivo' }}</span>
                <v-btn v-if="foto" icon="mdi-close" size="x-small" variant="text" title="Quitar imagen" @click="asignarFoto(null)" />
              </div>
              <small class="muted-note">JPG, PNG o WebP. Máximo {{ FOTO_MAX_TEXTO }}. *</small>
              <div v-if="fotoError" class="field-error"><v-icon icon="mdi-alert-circle-outline" size="16" />{{ fotoError }}</div>
            </section>
          </v-card>
        </aside>
      </div>
    </v-form>

    <v-snackbar v-model="snackbar" color="success" location="top right" timeout="4000"><v-icon icon="mdi-check-circle" class="mr-2" />Vehículo registrado correctamente.</v-snackbar>
  </AppShell>
</template>
