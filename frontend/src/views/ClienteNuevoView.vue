<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { api } from '../api'
import { iniciales, limpiarNombre, normalizarCorreo, normalizarTelefono, validarCorreo, validarNombre, validarTelefono } from '../clientes'
import { tienePermiso, type Customer, type RespuestaAlta } from '../types'
import { auth } from '../auth'

type FormRef = { validate: () => Promise<{ valid: boolean }>; resetValidation: () => void }
type Fase = 'captura' | 'coincidencias' | 'confirmar' | 'listo'

const router = useRouter(); const route = useRoute()
const puedeConsultar = tienePermiso(auth.user(), 'clientes.consultar')
const puedeRegistrarVehiculo = tienePermiso(auth.user(), 'vehiculos.registrar')
const esAdmin = auth.user()?.role === 'ADMINISTRADOR' // sin sucursal: elige el taller al que pertenecerá el cliente
const talleres = ref<{ id: number; nombre: string }[]>([]); const tallerId = ref<number | null>(null)
const consultaTaller = () => (esAdmin && tallerId.value ? `?taller_id=${tallerId.value}` : '')
const formRef = ref<FormRef | null>(null)
const fase = ref<Fase>('captura')
const taller = ref(''); const accesoError = ref(''); const accesoListo = ref(false)
const loading = ref(false); const error = ref(''); const snackbar = ref(false)
const form = reactive({ nombre_completo: '', telefono: '', correo: '' })
const coincidencias = ref<Customer[]>([]); const creado = ref<Customer | null>(null)

// Datos tal como se guardarán (vista previa; el servidor normaliza de nuevo y es la autoridad)
const nombreFinal = computed(() => limpiarNombre(form.nombre_completo))
const telefonoFinal = computed(() => normalizarTelefono(form.telefono))
const correoFinal = computed(() => normalizarCorreo(form.correo))

// «Abrir alta»: la API aplica las guardas (autenticación, autorización y Taller activo) antes de mostrar el formulario
async function abrirAlta() {
  accesoListo.value = false; accesoError.value = ''
  try { taller.value = (await api<{ taller: string }>(`/customers/alta/acceso${consultaTaller()}`)).taller; accesoListo.value = true }
  catch (e) { accesoError.value = e instanceof Error ? e.message : 'No fue posible abrir el alta de clientes' }
}
onMounted(async () => {
  if (esAdmin) {
    try { talleres.value = await api<{ id: number; nombre: string }[]>('/talleres'); tallerId.value = talleres.value[0]?.id ?? null }
    catch (e) { accesoError.value = e instanceof Error ? e.message : 'No fue posible cargar los talleres' }
    if (!tallerId.value) accesoError.value ||= 'No hay talleres registrados; dé de alta uno antes de registrar clientes'
  }
  if (!accesoError.value) await abrirAlta()
  const q = String(route.query.q ?? '').trim()
  if (q) { if (q.includes('@')) form.correo = q; else if (/^[\d\s+().-]+$/.test(q)) form.telefono = q; else form.nombre_completo = q }
})

async function solicitar(confirmar: boolean): Promise<RespuestaAlta | null> {
  error.value = ''; loading.value = true
  try { return await api<RespuestaAlta>(`/customers${consultaTaller()}`, { method: 'POST', body: JSON.stringify({ ...form, confirmar }) }) }
  catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible completar el alta'; return null }
  finally { loading.value = false }
}

function aplicar(respuesta: RespuestaAlta) {
  coincidencias.value = respuesta.coincidencias
  if (respuesta.resultado === 'COINCIDENCIAS') fase.value = 'coincidencias'
  else if (respuesta.resultado === 'PENDIENTE_CONFIRMACION') fase.value = 'confirmar'
  else { creado.value = respuesta.customer; fase.value = 'listo'; snackbar.value = true }
}

async function buscar() {
  error.value = ''
  if (!(await formRef.value?.validate())?.valid) { error.value = 'Revise los campos marcados en rojo.'; return }
  const respuesta = await solicitar(false)
  if (respuesta) aplicar(respuesta)
}

async function confirmar() { const respuesta = await solicitar(true); if (respuesta) aplicar(respuesta) }
function corregir() { error.value = ''; fase.value = 'captura' }
function nuevo() { Object.assign(form, { nombre_completo: '', telefono: '', correo: '' }); coincidencias.value = []; creado.value = null; error.value = ''; fase.value = 'captura' }
</script>

<template>
  <AppShell section="Clientes" title="Nuevo cliente">
    <div class="page-head">
      <div class="page-head__icon"><v-icon icon="mdi-account-plus-outline" /></div>
      <div><span class="eyebrow">Clientes · Alta</span><h1>Alta de cliente</h1><p>Capture el nombre completo, el teléfono y el correo. Antes de guardar buscamos coincidencias para no duplicar al cliente.</p></div>
    </div>

    <v-alert v-if="accesoError" type="error" variant="tonal" density="comfortable" icon="mdi-shield-alert-outline" class="mb-5">
      {{ accesoError }}
      <template #append><v-btn variant="text" to="/panel">Volver al panel</v-btn></template>
    </v-alert>

    <div v-else class="form-layout">
      <v-card class="panel-card" elevation="0">
        <v-select v-if="esAdmin && fase === 'captura'" v-model="tallerId" :items="talleres" item-title="nombre" item-value="id" label="Taller del cliente *" prepend-inner-icon="mdi-garage-variant" hint="El cliente pertenecerá a este taller" persistent-hint class="mb-4" @update:model-value="abrirAlta" />
        <div v-else-if="taller" class="taller-badge"><v-icon icon="mdi-store-outline" size="16" />Taller: <strong>{{ taller }}</strong></div>

        <!-- 1 · Captura -->
        <v-form v-if="fase === 'captura'" ref="formRef" autocomplete="off" @submit.prevent="buscar">
          <section class="form-section">
            <div class="form-section__title"><span class="step-dot">1</span><div><h3>Datos del cliente</h3><p>Todos los datos son obligatorios. El ID lo asigna el sistema al guardar.</p></div></div>
            <v-text-field v-model="form.nombre_completo" label="Nombre completo" name="cliente-nombre" autocomplete="nope" prepend-inner-icon="mdi-account-outline" hint="Nombre y apellido" persistent-hint :rules="[validarNombre]" />
            <div class="form-grid mt-3">
              <v-text-field v-model="form.telefono" label="Teléfono" name="cliente-telefono" autocomplete="nope" inputmode="tel" prepend-inner-icon="mdi-phone-outline" hint="De 10 a 15 dígitos" persistent-hint :rules="[validarTelefono]" />
              <v-text-field v-model="form.correo" label="Correo" name="cliente-correo" type="email" autocomplete="nope" prepend-inner-icon="mdi-email-outline" hint="Ej. cliente@correo.com" persistent-hint :rules="[validarCorreo]" />
            </div>
          </section>
          <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mt-4" closable @click:close="error = ''">{{ error }}</v-alert>
          <div class="form-actions">
            <v-btn variant="text" @click="router.push(puedeConsultar ? '/clientes' : '/panel')">Cancelar</v-btn>
            <v-btn class="submit-btn" type="submit" color="primary" size="large" :loading="loading" :disabled="!accesoListo" prepend-icon="mdi-account-search-outline">Buscar coincidencias</v-btn>
          </div>
        </v-form>

        <!-- 2 · Coincidencias: alerta y no se crea nada -->
        <div v-else-if="fase === 'coincidencias'">
          <v-alert type="warning" variant="tonal" density="comfortable" icon="mdi-alert-outline" title="Posible cliente duplicado">
            Encontramos {{ coincidencias.length }} cliente{{ coincidencias.length === 1 ? '' : 's' }} con el mismo nombre, teléfono o correo. <strong>No se creó ningún registro</strong> para evitar un duplicado.
          </v-alert>
          <div class="match-list">
            <div v-for="c in coincidencias" :key="c.id" class="match-card">
              <v-avatar class="avatar-initials" size="40">{{ iniciales(c.nombre_completo) }}</v-avatar>
              <div class="match-card__body"><strong>{{ c.nombre_completo }}</strong><span><v-icon icon="mdi-pound" size="14" />ID {{ c.id }}</span><span><v-icon icon="mdi-phone-outline" size="14" />{{ c.telefono ?? 'Sin teléfono' }}</span><span><v-icon icon="mdi-email-outline" size="14" />{{ c.correo ?? 'Sin correo' }}</span></div>
              <v-btn v-if="puedeConsultar" size="small" variant="tonal" color="primary" :to="`/clientes/${c.id}`">Ver ficha</v-btn>
            </div>
          </div>
          <div class="form-actions">
            <v-btn v-if="puedeConsultar" variant="text" @click="router.push('/clientes')">Ir a consulta</v-btn>
            <v-btn color="primary" size="large" prepend-icon="mdi-pencil-outline" @click="corregir">Corregir datos</v-btn>
          </div>
        </div>

        <!-- 3 · Confirmar -->
        <div v-else-if="fase === 'confirmar'">
          <v-alert type="success" variant="tonal" density="comfortable" icon="mdi-check-circle-outline" title="Sin coincidencias">No hay un cliente parecido en este taller. Confirme para guardarlo.</v-alert>
          <dl class="summary-list">
            <div><dt><v-icon icon="mdi-account-outline" size="16" />Nombre completo</dt><dd>{{ nombreFinal }}</dd></div>
            <div><dt><v-icon icon="mdi-phone-outline" size="16" />Teléfono</dt><dd>{{ telefonoFinal }}</dd></div>
            <div><dt><v-icon icon="mdi-email-outline" size="16" />Correo</dt><dd>{{ correoFinal }}</dd></div>
            <div><dt><v-icon icon="mdi-check-decagram-outline" size="16" />Estado inicial</dt><dd>Activo</dd></div>
          </dl>
          <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mt-4" closable @click:close="error = ''">{{ error }}</v-alert>
          <div class="form-actions">
            <v-btn variant="text" :disabled="loading" @click="corregir">Corregir datos</v-btn>
            <v-btn class="submit-btn" color="primary" size="large" :loading="loading" prepend-icon="mdi-check" @click="confirmar">Confirmar alta</v-btn>
          </div>
        </div>

        <!-- 4 · Listo -->
        <div v-else class="success-hero">
          <div class="success-hero__icon"><v-icon icon="mdi-check-bold" /></div>
          <h2>Cliente dado de alta</h2>
          <p>Quedó registrado como <strong>activo</strong> y se guardó la auditoría de la operación.</p>
          <div v-if="creado" class="match-card match-card--center">
            <v-avatar class="avatar-initials" size="44">{{ iniciales(creado.nombre_completo) }}</v-avatar>
            <div class="match-card__body"><strong>{{ creado.nombre_completo }}</strong><span><v-icon icon="mdi-pound" size="14" />ID {{ creado.id }}</span><span><v-icon icon="mdi-phone-outline" size="14" />{{ creado.telefono }}</span><span><v-icon icon="mdi-email-outline" size="14" />{{ creado.correo }}</span></div>
            <v-chip size="small" color="success" variant="tonal" label>Activo</v-chip>
          </div>
          <div class="form-actions form-actions--center">
            <v-btn v-if="puedeConsultar" variant="text" @click="router.push('/clientes')">Ir a consulta</v-btn>
            <v-btn v-if="puedeConsultar" variant="tonal" color="primary" :to="`/clientes/${creado?.id}`">Ver ficha</v-btn>
            <v-btn :variant="puedeRegistrarVehiculo ? 'text' : 'elevated'" color="primary" size="large" prepend-icon="mdi-account-plus-outline" @click="nuevo">Registrar otro</v-btn>
            <v-btn v-if="puedeRegistrarVehiculo" class="submit-btn" color="primary" size="large" prepend-icon="mdi-car-arrow-right" :to="`/vehiculos/nuevo?cliente=${creado?.id}`">Registrar su vehículo</v-btn>
          </div>
        </div>
      </v-card>

      <aside class="side-stack">
        <v-card class="panel-card" elevation="0">
          <header class="panel-card__header"><div><h2>Reglas</h2></div></header>
          <ul class="tip-list">
            <li><v-icon icon="mdi-format-text" size="18" />Se limpian espacios y se normalizan teléfono y correo antes de comparar.</li>
            <li><v-icon icon="mdi-content-duplicate" size="18" />Si hay coincidencias se alerta y nunca se crea un segundo registro.</li>
            <li><v-icon icon="mdi-history" size="18" />Cada alta queda registrada en la auditoría.</li>
          </ul>
        </v-card>
      </aside>
    </div>

    <v-snackbar v-model="snackbar" color="success" location="top right" timeout="4000"><v-icon icon="mdi-check-circle" class="mr-2" />Cliente dado de alta correctamente.</v-snackbar>
  </AppShell>
</template>
