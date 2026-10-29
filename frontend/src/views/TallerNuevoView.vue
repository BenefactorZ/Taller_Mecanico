<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { api, apiBlob } from '../api'
import { FOTO_MAX_TEXTO, limpiar, requerido, validarCorreo, validarCp, validarFoto, validarRfc, validarTexto } from '../talleres'
import { STATUS_ELIMINADO, type Taller, type TallerAdmin } from '../types'

type FormRef = { validate: () => Promise<{ valid: boolean }>; resetValidation: () => void }
interface ItemColonia { title: string; value: string; colonia: string; cp: string }
interface CodigoPostal { codigo_postal: string; estado: string; municipio: string; colonias: string[] }

// Esta misma pantalla da de alta (/talleres/nuevo) y edita (/talleres/:id/editar): en edición el formulario se llena con el taller y la foto es opcional
const route = useRoute()
const idEdicion = route.params.id ? Number(route.params.id) : null
const editando = idEdicion !== null
const tallerEditado = ref<TallerAdmin | null>(null); const cargandoTaller = ref(editando); const noEditable = ref('')
const formRef = ref<FormRef | null>(null)
const formKey = ref(0) // al cambiar, el formulario se vuelve a montar limpio (sin errores de validación residuales)
const vacio = () => ({ nombre: '', rfc: '', email_contacto: '', calle: '', codigo_postal: '', estado: '', municipio: '' })
const form = reactive(vacio())
const coloniaKey = ref<string | null>(null)
const coloniaItems = ref<ItemColonia[]>([]); const estados = ref<string[]>([]); const municipios = ref<string[]>([])
const cpEstado = ref<'' | 'buscando' | 'ok' | 'error'>(''); const cpMensaje = ref(''); let cpDeCatalogo = false; let secuencia = 0
const talleres = ref<Taller[]>([]); const cargandoLista = ref(true)
const loading = ref(false); const error = ref(''); const exito = ref(''); const snackbar = ref(false)

// ---- Foto ----
const foto = ref<File | null>(null); const fotoUrl = ref(''); const fotoError = ref(''); const arrastrando = ref(false)
const fotoActual = ref('') // en edición: la foto que ya tiene el taller (se descarga con la sesión)
const vistaFoto = computed(() => fotoUrl.value || fotoActual.value)
const inputFoto = ref<HTMLInputElement | null>(null)
function limpiarVistaPrevia() { if (fotoUrl.value) URL.revokeObjectURL(fotoUrl.value); fotoUrl.value = '' }
async function asignarFoto(archivo: File | null) {
  limpiarVistaPrevia(); foto.value = archivo; fotoError.value = archivo ? await validarFoto(archivo) : ''
  if (archivo && !fotoError.value) fotoUrl.value = URL.createObjectURL(archivo)
}
const elegirFoto = (e: Event) => { const input = e.target as HTMLInputElement; void asignarFoto(input.files?.[0] ?? null); input.value = '' }
const soltarFoto = (e: DragEvent) => { arrastrando.value = false; void asignarFoto(e.dataTransfer?.files?.[0] ?? null) }
const quitarFoto = () => { void asignarFoto(null) }
async function cargarFotoActual() {
  if (fotoActual.value) URL.revokeObjectURL(fotoActual.value)
  fotoActual.value = ''
  try { fotoActual.value = URL.createObjectURL(await apiBlob(`/talleres/${idEdicion}/foto`)) } catch { /* sin foto o sin conexión: se muestra el espacio vacío */ }
}
onBeforeUnmount(() => { limpiarVistaPrevia(); if (fotoActual.value) URL.revokeObjectURL(fotoActual.value) })

// ---- Domicilio: del código postal al estado/municipio/colonia, y de estado/municipio/colonia al código postal ----
const consulta = (ruta: string, parametros: Record<string, string>) => api<any>(`${ruta}?${new URLSearchParams(parametros)}`)
const itemsDe = (cp: string, colonias: string[]): ItemColonia[] => colonias.map((c) => ({ title: c, value: `${cp}|${c}`, colonia: c, cp }))

function limpiarDomicilio() { form.estado = ''; form.municipio = ''; municipios.value = []; coloniaItems.value = []; coloniaKey.value = null }
function soltarCpDeCatalogo() { if (cpDeCatalogo) { form.codigo_postal = ''; cpDeCatalogo = false; cpEstado.value = ''; cpMensaje.value = '' } }

async function alCambiarCp(valor: string) {
  const cp = (valor ?? '').replace(/\D/g, '').slice(0, 5)
  form.codigo_postal = cp; cpDeCatalogo = false
  const turno = ++secuencia
  if (cp.length < 5) { if (cpEstado.value === 'ok') limpiarDomicilio(); cpEstado.value = ''; cpMensaje.value = ''; return }
  cpEstado.value = 'buscando'; cpMensaje.value = 'Buscando código postal…'
  try {
    const datos = await api<CodigoPostal>(`/catalogos/codigo-postal/${cp}`)
    const lista = await consulta('/catalogos/municipios', { estado: datos.estado })
    if (turno !== secuencia) return // el usuario siguió escribiendo: esta respuesta ya no aplica
    form.estado = datos.estado; municipios.value = lista; form.municipio = datos.municipio
    coloniaItems.value = itemsDe(cp, datos.colonias); coloniaKey.value = coloniaItems.value.length === 1 ? coloniaItems.value[0].value : null
    cpDeCatalogo = true; cpEstado.value = 'ok'
    cpMensaje.value = `Estado y municipio cargados. ${datos.colonias.length === 1 ? 'Colonia cargada.' : `Elija una de las ${datos.colonias.length} colonias.`}`
  } catch (e) {
    if (turno !== secuencia) return
    limpiarDomicilio(); cpEstado.value = 'error'; cpMensaje.value = e instanceof Error ? e.message : 'No fue posible buscar el código postal'
  }
}

async function alCambiarEstado(estado: string) {
  soltarCpDeCatalogo(); form.estado = estado; form.municipio = ''; municipios.value = []; coloniaItems.value = []; coloniaKey.value = null
  if (estado) municipios.value = await consulta('/catalogos/municipios', { estado })
}
async function alCambiarMunicipio(municipio: string) {
  soltarCpDeCatalogo(); form.municipio = municipio; coloniaItems.value = []; coloniaKey.value = null
  if (municipio) { const datos = await consulta('/catalogos/colonias', { estado: form.estado, municipio }); coloniaItems.value = datos.map((d: { colonia: string; codigo_postal: string }) => itemsDe(d.codigo_postal, [d.colonia])[0]) }
}
function alCambiarColonia(clave: string | null) {
  coloniaKey.value = clave
  const item = coloniaItems.value.find((i) => i.value === clave)
  if (item && item.cp !== form.codigo_postal) { form.codigo_postal = item.cp; cpDeCatalogo = true; cpEstado.value = 'ok'; cpMensaje.value = 'Código postal cargado desde la colonia.' }
}

onMounted(async () => {
  try { estados.value = await api<string[]>('/catalogos/estados') } catch { estados.value = [] }
  if (editando) { await cargarTaller(); return }
  try { talleres.value = await api<Taller[]>('/talleres') } catch { talleres.value = [] } finally { cargandoLista.value = false }
})

async function cargarTaller() {
  try {
    const t = await api<TallerAdmin>(`/talleres/${idEdicion}`)
    tallerEditado.value = t
    if (t.bin_status === STATUS_ELIMINADO) { noEditable.value = 'Este taller está eliminado. Restáurelo desde la lista de talleres para poder editarlo.'; return }
    Object.assign(form, { nombre: t.nombre, rfc: t.rfc ?? '', email_contacto: t.email_contacto ?? '', calle: t.calle ?? '', codigo_postal: '', estado: '', municipio: '' })
    formKey.value++
    if (t.codigo_postal) {
      await alCambiarCp(t.codigo_postal) // del código postal se recuperan estado, municipio y colonias
      const actual = coloniaItems.value.find((i) => i.colonia === t.colonia)
      if (actual) { coloniaKey.value = actual.value; cpMensaje.value = 'Domicilio cargado desde el catálogo.' } else { coloniaKey.value = null; cpMensaje.value = 'La colonia guardada ya no está en el catálogo; elija una.' }
    }
    if (t.tiene_foto) await cargarFotoActual()
  } catch (e) { noEditable.value = e instanceof Error ? e.message : 'No fue posible cargar el taller' }
  finally { cargandoTaller.value = false }
}

// ---- Envío ----
const reglas = {
  nombre: [validarTexto('El nombre', 3, 100)], rfc: [(v: string) => validarRfc(v)], email: [(v: string) => validarCorreo(v)], calle: [validarTexto('La calle y número', 3, 150)],
  cp: [(v: string) => validarCp(v)], estado: [requerido('El estado')], municipio: [requerido('El municipio')], colonia: [requerido('La colonia')],
}
async function enviar() {
  error.value = ''; exito.value = ''
  const resultado = await formRef.value?.validate(); fotoError.value = editando && !foto.value ? '' : await validarFoto(foto.value)
  if (!resultado?.valid || fotoError.value) {
    error.value = 'Faltan datos o hay campos con errores. Revise los campos marcados en rojo.'
    await nextTick(); document.querySelector('.v-input--error, .dropzone.has-error')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); return
  }
  const colonia = coloniaItems.value.find((i) => i.value === coloniaKey.value)?.colonia ?? ''
  const datos = new FormData()
  for (const [campo, valor] of Object.entries({ ...form, colonia })) datos.append(campo, typeof valor === 'string' ? limpiar(valor) : valor)
  if (foto.value) datos.append('foto', foto.value)
  loading.value = true
  try {
    if (editando) { await guardarCambios(datos); return }
    const taller = await api<Taller>('/talleres', { method: 'POST', body: datos })
    exito.value = `El taller «${taller.nombre}» se dio de alta correctamente. Los empleados con la sucursal «${taller.nombre}» ya pueden operar en él.`; snackbar.value = true
    talleres.value = [...talleres.value, taller].sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))
    Object.assign(form, vacio()); limpiarDomicilio(); cpEstado.value = ''; cpMensaje.value = ''; cpDeCatalogo = false; await asignarFoto(null)
    formKey.value++
  } catch (e) { error.value = e instanceof Error ? e.message : editando ? 'No fue posible guardar los cambios' : 'No fue posible dar de alta el taller' }
  finally { loading.value = false }
}

async function guardarCambios(datos: FormData) {
  const taller = await api<TallerAdmin>(`/talleres/${idEdicion}`, { method: 'PUT', body: datos })
  const renombrado = tallerEditado.value && taller.nombre !== tallerEditado.value.nombre
  tallerEditado.value = taller
  exito.value = renombrado ? `Los cambios se guardaron. Las sucursales de los empleados se actualizaron al nuevo nombre «${taller.nombre}».` : 'Los cambios se guardaron correctamente.'; snackbar.value = true
  if (foto.value) { await asignarFoto(null); await cargarFotoActual() }
}
</script>

<template>
  <AppShell section="Talleres" :title="editando ? 'Editar taller' : 'Alta de taller'">
    <div class="page-head">
      <div class="page-head__icon"><v-icon :icon="editando ? 'mdi-garage-open-variant' : 'mdi-garage-variant'" /></div>
      <div v-if="editando"><span class="eyebrow">Administración · Talleres</span><h1>Editar taller</h1><p>Corrija los datos, el domicilio o la foto. Si cambia el nombre, la sucursal de sus empleados se actualiza con él.</p></div>
      <div v-else><span class="eyebrow">Subsistema · Taller mecánico</span><h1>Alta de taller mecánico</h1><p>Registre los datos del taller al que podrán asociarse sus clientes y empleados.</p></div>
    </div>

    <v-alert v-if="noEditable" type="warning" variant="tonal" density="comfortable" class="mb-4">{{ noEditable }}<template #append><v-btn variant="text" to="/talleres">Volver a talleres</v-btn></template></v-alert>
    <v-skeleton-loader v-else-if="cargandoTaller" type="card, card" />
    <v-form v-else :key="formKey" ref="formRef" autocomplete="off" @submit.prevent="enviar">
      <div class="taller-layout">
        <div class="taller-col">
          <v-card class="panel-card" elevation="0">
            <section class="form-section">
              <div class="form-section__title"><span class="step-dot"><v-icon icon="mdi-wrench-outline" size="16" /></span><div><h3>Datos del taller</h3><p>Todos los campos marcados con * son obligatorios.</p></div></div>
              <v-text-field v-model="form.nombre" label="Nombre del taller mecánico *" name="taller-nombre" autocomplete="nope" placeholder="Ej. Servicio Automotriz del Centro" prepend-inner-icon="mdi-store-outline" :rules="reglas.nombre" />
              <div class="form-grid mt-3">
                <v-text-field :model-value="form.rfc" label="RFC *" name="taller-rfc" autocomplete="nope" placeholder="ABC010203AB1" maxlength="13" prepend-inner-icon="mdi-card-account-details-outline" hint="12 o 13 caracteres. Se guardará en mayúsculas." persistent-hint :rules="reglas.rfc" @update:model-value="(v: string) => (form.rfc = (v ?? '').toUpperCase().replace(/\s/g, ''))" />
                <v-text-field v-model="form.email_contacto" label="Email de contacto *" type="email" name="taller-email" autocomplete="nope" placeholder="contacto@taller.com" prepend-inner-icon="mdi-email-outline" :rules="reglas.email" />
              </div>
            </section>
          </v-card>

          <v-card class="panel-card" elevation="0">
            <section class="form-section">
              <div class="form-section__title"><span class="step-dot"><v-icon icon="mdi-map-marker-outline" size="16" /></span><div><h3>Domicilio del taller</h3><p>Escriba el código postal y se llenan estado, municipio y colonia. Si no lo conoce, elíjalos y se cargará el código postal.</p></div></div>
              <v-text-field v-model="form.calle" label="Calle y número *" name="taller-calle" autocomplete="nope" placeholder="Ej. Av. Reforma 125, local 2" prepend-inner-icon="mdi-road-variant" hint="Incluya número exterior e interior, si corresponde." persistent-hint :rules="reglas.calle" />
              <div class="form-grid mt-3">
                <v-text-field :model-value="form.codigo_postal" label="Código postal *" name="taller-cp" autocomplete="nope" inputmode="numeric" maxlength="5" placeholder="Ej. 06000" prepend-inner-icon="mdi-mailbox-outline" :loading="cpEstado === 'buscando'" :hint="cpMensaje || '5 dígitos'" persistent-hint :error="cpEstado === 'error'" :rules="reglas.cp" @update:model-value="alCambiarCp" />
                <v-select :model-value="form.estado || null" label="Estado *" :items="estados" placeholder="Selecciona un estado" prepend-inner-icon="mdi-map-outline" :rules="reglas.estado" @update:model-value="alCambiarEstado" />
                <v-select :model-value="form.municipio || null" label="Municipio o alcaldía *" :items="municipios" :disabled="!form.estado" :placeholder="form.estado ? 'Selecciona un municipio' : 'Primero selecciona un estado'" prepend-inner-icon="mdi-city-variant-outline" hint="Las opciones corresponden al estado seleccionado." persistent-hint :rules="reglas.municipio" @update:model-value="alCambiarMunicipio" />
                <v-autocomplete :model-value="coloniaKey" label="Colonia *" :items="coloniaItems" item-title="title" item-value="value" :disabled="!form.municipio" :placeholder="form.municipio ? 'Busca y elige la colonia' : 'Primero selecciona un municipio'" no-data-text="Sin colonias para mostrar" prepend-inner-icon="mdi-home-city-outline" :rules="reglas.colonia" @update:model-value="alCambiarColonia">
                  <template #item="{ props: itemProps, item }"><v-list-item v-bind="itemProps" :subtitle="`C.P. ${item.raw.cp}`" /></template>
                </v-autocomplete>
              </div>
            </section>
          </v-card>

          <div class="taller-actions">
            <v-alert v-if="error" type="error" variant="tonal" density="comfortable" closable @click:close="error = ''">{{ error }}</v-alert>
            <v-alert v-if="exito" type="success" variant="tonal" density="comfortable" closable @click:close="exito = ''">{{ exito }}</v-alert>
            <div class="form-actions"><v-btn variant="text" :to="editando ? '/talleres' : '/panel'">{{ editando ? 'Volver a talleres' : 'Cancelar' }}</v-btn><v-btn class="submit-btn" type="submit" color="primary" size="large" :loading="loading" :prepend-icon="editando ? 'mdi-content-save-outline' : 'mdi-garage-variant'">{{ editando ? 'Guardar cambios' : 'Dar de alta el taller' }}</v-btn></div>
          </div>
        </div>

        <aside class="taller-col">
          <v-card class="panel-card" elevation="0">
            <section class="form-section">
              <div class="form-section__title"><span class="step-dot"><v-icon icon="mdi-camera-outline" size="16" /></span><div><h3>Foto del taller</h3><p>{{ editando ? 'Elija una imagen sólo si desea reemplazar la actual.' : 'Una imagen para identificar el establecimiento.' }}</p></div></div>
              <label class="dropzone" :class="{ 'is-over': arrastrando, 'has-image': !!vistaFoto, 'has-error': !!fotoError }" @dragover.prevent="arrastrando = true" @dragleave.prevent="arrastrando = false" @drop.prevent="soltarFoto">
                <img v-if="vistaFoto" :src="vistaFoto" :alt="fotoUrl ? 'Vista previa de la foto nueva' : 'Foto actual del taller'">
                <span v-else class="dropzone__empty"><v-icon icon="mdi-image-outline" /><span>Agrega una foto de la fachada o del interior del taller.</span><small>Arrastre la imagen aquí o haga clic.</small></span>
                <input ref="inputFoto" class="visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" @change="elegirFoto">
              </label>
              <div class="file-row">
                <v-btn variant="tonal" color="primary" size="small" prepend-icon="mdi-paperclip" @click="inputFoto?.click()">Elegir archivo</v-btn>
                <span class="file-row__name">{{ foto?.name ?? (editando ? 'Se conserva la foto actual' : 'No se eligió ningún archivo') }}</span>
                <v-btn v-if="foto" icon="mdi-close" size="x-small" variant="text" title="Quitar foto" @click="quitarFoto" />
              </div>
              <small class="muted-note">JPG, PNG o WebP. Máximo {{ FOTO_MAX_TEXTO }}.{{ editando ? '' : ' *' }}</small>
              <div v-if="fotoError" class="field-error"><v-icon icon="mdi-alert-circle-outline" size="16" />{{ fotoError }}</div>
            </section>
          </v-card>

          <v-card v-if="!editando" class="panel-card" elevation="0">
            <header class="panel-card__header"><div><h2>Talleres registrados</h2><p>Los empleados se asocian por el nombre de su sucursal.</p></div><v-chip size="small" variant="tonal" color="primary">{{ talleres.length }}</v-chip></header>
            <div v-if="cargandoLista" class="role-list"><v-skeleton-loader v-for="n in 2" :key="n" type="list-item-two-line" /></div>
            <div v-else-if="talleres.length" class="role-list role-list--scroll">
              <div v-for="t in talleres" :key="t.id" class="role-item">
                <div class="tone-icon tone-blue"><v-icon icon="mdi-garage-variant" size="20" /></div>
                <div><strong>{{ t.nombre }}</strong><code>{{ t.rfc || 'Sin RFC' }}</code><p v-if="t.municipio">{{ t.municipio }}, {{ t.estado }}</p></div>
              </div>
            </div>
            <div v-else class="empty-state"><v-icon icon="mdi-garage-variant" /><p>Aún no hay talleres registrados.</p></div>
          </v-card>
        </aside>
      </div>
    </v-form>

    <v-snackbar v-model="snackbar" color="success" location="top right" timeout="4000"><v-icon icon="mdi-check-circle" class="mr-2" />{{ editando ? 'Cambios guardados.' : 'Taller dado de alta correctamente.' }}</v-snackbar>
  </AppShell>
</template>
