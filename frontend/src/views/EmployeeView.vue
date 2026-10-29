<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { api } from '../api'
import { ROL_ICONOS, type Permiso, type RoleDefinition } from '../types'

type FormRef = { validate: () => Promise<{ valid: boolean }>; resetValidation: () => void }
const router = useRouter()
const formRef = ref<FormRef | null>(null)
const formKey = ref(0) // al cambiar, el formulario se vuelve a montar limpio (sin errores de validación residuales)
const error = ref(''); const success = ref(''); const loading = ref(false); const showPassword = ref(false); const snackbar = ref(false); const created = ref('')
const empty = () => ({ full_name: '', email: '', password: '', role: null as string | null, branch: '' })
const form = reactive(empty())

const emailRules = [(v: string) => /.+@.+\..+/.test(v) || 'Ingrese un correo válido']
const nameRules = [(v: string) => v.trim().length >= 3 || 'Ingrese el nombre completo']
const passwordRules = [(v: string) => v.length >= 12 || 'Use al menos 12 caracteres']
const roleRules = [(v: string | null) => !!v || 'Seleccione un rol']
const branchRules = [(v: string) => !!v.trim() || 'La sucursal es obligatoria']

// Los roles salen de la base de datos: los de empleado de fábrica y los personalizados que creó el administrador
const rolesCargando = ref(true); const rolesError = ref(''); const roles = ref<RoleDefinition[]>([]); const catalogo = ref<Permiso[]>([])
onMounted(async () => {
  try { catalogo.value = await api<Permiso[]>('/permisos') } catch { catalogo.value = [] }
  try { roles.value = await api<RoleDefinition[]>('/roles/asignables') }
  catch (e) { rolesError.value = e instanceof Error ? e.message : 'No fue posible cargar los roles' }
  finally { rolesCargando.value = false }
})
const opciones = computed(() => roles.value.map((rol) => ({ title: rol.name, value: rol.code, icon: ROL_ICONOS[rol.code] ?? 'mdi-badge-account-outline', personalizado: !rol.es_sistema, description: rol.description || 'Rol personalizado sin descripción.', permisos: rol.permisos })))
const nombreDe = (codigo: string) => catalogo.value.find((p) => p.codigo === codigo)?.nombre ?? codigo
const selectedRole = computed(() => opciones.value.find((rol) => rol.value === form.role))
const strength = computed(() => {
  const p = form.password
  if (!p) return 0
  return [p.length >= 12, p.length >= 16, /[a-z]/.test(p) && /[A-Z]/.test(p), /\d/.test(p), /[^A-Za-z0-9]/.test(p)].filter(Boolean).length
})
const strengthMeta = computed(() => [
  { label: '', color: '#E8EAF0' }, { label: 'Muy débil', color: '#D93A2B' }, { label: 'Débil', color: '#F07820' },
  { label: 'Aceptable', color: '#E0B000' }, { label: 'Fuerte', color: '#3FAE6A' }, { label: 'Excelente', color: '#1E9E62' }
][strength.value])

function generatePassword() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%&*?'
  form.password = Array.from(crypto.getRandomValues(new Uint32Array(16)), (value) => chars[value % chars.length]).join('')
  showPassword.value = true
}

// El resultado se muestra junto al botón: en pantallas bajas el campo con error puede quedar fuera de vista
async function submit() {
  error.value = ''; success.value = ''
  const result = await formRef.value?.validate()
  if (!result?.valid) {
    error.value = result ? 'Faltan datos o hay campos con errores. Revise los campos marcados en rojo.' : 'No se pudo validar el formulario. Recargue la página e inténtelo de nuevo.'
    await nextTick(); document.querySelector('.v-input--error')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    return
  }
  loading.value = true
  try {
    await api('/users/employees', { method: 'POST', body: JSON.stringify(form) })
    created.value = form.full_name.trim(); snackbar.value = true; showPassword.value = false
    success.value = `${created.value} fue dado de alta correctamente. Ya puede ingresar con su correo; puede registrar otro empleado.`
    Object.assign(form, empty())
    formKey.value++
  } catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible registrar el usuario' } finally { loading.value = false }
}
</script>

<template>
  <AppShell section="Administración" title="Alta de empleado">
    <div class="page-head">
      <div class="page-head__icon"><v-icon icon="mdi-account-plus-outline" /></div>
      <div><span class="eyebrow">Administración · Personal</span><h1>Alta de empleado</h1><p>Capture la información requerida para habilitar un nuevo acceso.</p></div>
    </div>

    <div class="form-layout">
      <v-card class="panel-card" elevation="0">
        <!-- autocomplete desactivado: el navegador no debe rellenar el formulario con las credenciales del administrador -->
        <v-form :key="formKey" ref="formRef" autocomplete="off" @submit.prevent="submit">
          <section class="form-section">
            <div class="form-section__title"><span class="step-dot">1</span><div><h3>Datos personales</h3><p>Nombre y correo con el que ingresará.</p></div></div>
            <div class="form-grid">
              <v-text-field v-model="form.full_name" label="Nombre completo" name="employee-name" autocomplete="nope" prepend-inner-icon="mdi-account-outline" :rules="nameRules" />
              <v-text-field v-model="form.email" label="Correo" type="email" name="employee-email" autocomplete="nope" prepend-inner-icon="mdi-email-outline" :rules="emailRules" />
            </div>
          </section>
          <section class="form-section">
            <div class="form-section__title"><span class="step-dot">2</span><div><h3>Asignación</h3><p>Rol operativo y sucursal donde trabajará.</p></div></div>
            <div class="form-grid">
              <v-select v-model="form.role" label="Rol" :items="opciones" item-title="title" item-value="value" :loading="rolesCargando" :error-messages="rolesError" no-data-text="No hay roles disponibles" prepend-inner-icon="mdi-badge-account-outline" :rules="roleRules">
                <template #item="{ props: itemProps, item }">
                  <v-list-item v-bind="itemProps" :prepend-icon="item.raw.icon" :subtitle="item.raw.description">
                    <template v-if="item.raw.personalizado" #append><v-chip size="x-small" label color="primary" variant="tonal">Personalizado</v-chip></template>
                  </v-list-item>
                </template>
              </v-select>
              <v-text-field v-model="form.branch" label="Sucursal" name="employee-branch" autocomplete="nope" prepend-inner-icon="mdi-store-outline" :rules="branchRules" />
            </div>
          </section>
          <section class="form-section">
            <div class="form-section__title"><span class="step-dot">3</span><div><h3>Credenciales</h3><p>Contraseña inicial con la que el empleado ingresará por primera vez.</p></div></div>
            <v-text-field v-model="form.password" label="Contraseña temporal" name="employee-password" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" prepend-inner-icon="mdi-lock-outline" :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'" :rules="passwordRules" @click:append-inner="showPassword = !showPassword" />
            <div class="strength">
              <div class="strength__bars"><span v-for="n in 5" :key="n" :style="{ background: n <= strength ? strengthMeta.color : undefined }" /></div>
              <small :style="{ color: strengthMeta.color }">{{ strengthMeta.label }}</small>
              <v-btn size="small" variant="tonal" color="primary" prepend-icon="mdi-auto-fix" @click="generatePassword">Generar</v-btn>
            </div>
          </section>
          <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mt-4" closable @click:close="error = ''">{{ error }}</v-alert>
          <v-alert v-if="success" type="success" variant="tonal" density="comfortable" class="mt-4" closable @click:close="success = ''">{{ success }}</v-alert>
          <div class="form-actions">
            <v-btn variant="text" @click="router.push('/panel')">Cancelar</v-btn>
            <v-btn class="submit-btn" type="submit" color="primary" size="large" :loading="loading" prepend-icon="mdi-account-plus-outline">Dar de alta</v-btn>
          </div>
        </v-form>
      </v-card>

      <aside class="side-stack">
        <v-card class="panel-card preview-card" elevation="0">
          <div class="preview-card__top">
            <div class="preview-card__badge">
              <div class="tone-icon"><v-icon :icon="selectedRole?.icon ?? 'mdi-account-question-outline'" /></div>
              <div><small>Vista previa</small><strong>{{ form.full_name.trim() || 'Nuevo empleado' }}</strong></div>
            </div>
            <span class="preview-card__code">{{ selectedRole?.title ?? 'Sin rol seleccionado' }}<template v-if="form.branch.trim()"> · {{ form.branch.trim() }}</template></span>
          </div>
          <template v-if="selectedRole">
            <p class="preview-card__text">{{ selectedRole.description }}</p>
            <ul v-if="selectedRole.permisos.length" class="check-list"><li v-for="codigo in selectedRole.permisos" :key="codigo"><v-icon icon="mdi-check-circle" size="18" />{{ nombreDe(codigo) }}</li></ul>
            <v-alert v-else type="warning" variant="tonal" density="compact" icon="mdi-information-outline">Este rol no tiene permisos asignados: el empleado podrá ingresar, pero no usar los módulos hasta que se definan en «Roles y permisos».</v-alert>
          </template>
          <p v-else class="preview-card__text">Seleccione un rol para ver los permisos que tendrá el empleado.</p>
        </v-card>
        <v-card class="panel-card" elevation="0">
          <header class="panel-card__header"><div><h2>Recomendaciones</h2></div></header>
          <ul class="tip-list">
            <li><v-icon icon="mdi-email-check-outline" size="18" />El correo debe ser único en el sistema.</li>
            <li><v-icon icon="mdi-lock-reset" size="18" />Comparta la contraseña temporal por un canal seguro.</li>
            <li><v-icon icon="mdi-store-marker-outline" size="18" />Use el mismo nombre de sucursal en todo el personal.</li>
          </ul>
        </v-card>
      </aside>
    </div>

    <v-snackbar v-model="snackbar" color="success" location="top right" timeout="4000"><v-icon icon="mdi-check-circle" class="mr-2" />{{ created }} fue dado de alta correctamente.</v-snackbar>
  </AppShell>
</template>
