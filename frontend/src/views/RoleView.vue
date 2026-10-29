<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { api } from '../api'
import { ROLE_LABELS, type RoleDefinition } from '../types'

type FormRef = { validate: () => Promise<{ valid: boolean }>; resetValidation: () => void }
const router = useRouter()
const formRef = ref<FormRef | null>(null)
const formKey = ref(0) // al cambiar, el formulario se vuelve a montar limpio (sin errores de validación residuales)
const error = ref(''); const success = ref(''); const loading = ref(false); const snackbar = ref(false); const created = ref('')
const roles = ref<RoleDefinition[]>([]); const rolesLoading = ref(true)
// La lista lateral muestra sólo los personalizados; los de fábrica se ven en «Administrar roles»
const personalizados = computed(() => roles.value.filter((role) => !role.es_sistema))
const empty = () => ({ code: '', name: '', description: '' })
const form = reactive(empty())
const reservedCodes = Object.keys(ROLE_LABELS)

// La clave se sugiere a partir del nombre hasta que el administrador la edita manualmente
const codeTouched = ref(false)
function toCode(value: string) {
  return value.normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase().replace(/[^A-Z0-9]+/g, '_').replace(/^[^A-Z]+/, '').replace(/_+$/, '').slice(0, 40)
}
watch(() => form.name, (name) => { if (!codeTouched.value) form.code = toCode(name) })
function onCodeInput(value: string) { codeTouched.value = value !== ''; form.code = value.toUpperCase().replace(/\s+/g, '_') }

const nameRules = [(v: string) => v.trim().length >= 3 || 'Ingrese el nombre del rol (mínimo 3 caracteres)']
const codeRules = [
  (v: string) => !!v || 'La clave es obligatoria',
  (v: string) => /^[A-Z][A-Z0-9_]*$/.test(v) || 'Inicie con letra; use mayúsculas, números y guion bajo',
  (v: string) => v.length >= 3 || 'La clave debe tener al menos 3 caracteres',
  (v: string) => !reservedCodes.includes(v) || 'Clave reservada para un rol del sistema',
  (v: string) => !roles.value.some((role) => role.code === v) || 'Ya existe un rol con esta clave'
]
const descriptionRules = [(v: string) => v.length <= 250 || 'Máximo 250 caracteres']

onMounted(async () => {
  try { roles.value = await api<RoleDefinition[]>('/roles') } catch { roles.value = [] } finally { rolesLoading.value = false }
})

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
    const role = await api<RoleDefinition>('/roles', { method: 'POST', body: JSON.stringify({ ...form, description: form.description.trim() || null }) })
    roles.value = [...roles.value, role].sort((a, b) => a.name.localeCompare(b.name, 'es'))
    created.value = role.name; snackbar.value = true
    success.value = `El rol «${role.name}» fue dado de alta correctamente. Puede registrar otro rol.`
    codeTouched.value = false
    Object.assign(form, empty())
    formKey.value++
  } catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible registrar el rol' } finally { loading.value = false }
}
</script>

<template>
  <AppShell section="Administración" title="Alta de rol">
    <div class="page-head">
      <div class="page-head__icon"><v-icon icon="mdi-badge-account-horizontal-outline" /></div>
      <div><span class="eyebrow">Administración · Roles</span><h1>Alta de rol</h1><p>Defina una clave única y una descripción clara para el nuevo rol.</p></div>
    </div>

    <div class="form-layout">
      <v-card class="panel-card" elevation="0">
        <v-form :key="formKey" ref="formRef" autocomplete="off" @submit.prevent="submit">
          <section class="form-section">
            <div class="form-section__title"><span class="step-dot">1</span><div><h3>Identidad del rol</h3><p>Nombre visible y clave técnica única.</p></div></div>
            <div class="form-grid">
              <v-text-field v-model="form.name" label="Nombre del rol" name="role-name" autocomplete="nope" prepend-inner-icon="mdi-badge-account-outline" :rules="nameRules" />
              <v-text-field :model-value="form.code" label="Clave del rol" name="role-code" autocomplete="nope" prepend-inner-icon="mdi-key-outline" hint="Se sugiere desde el nombre; puede editarla" persistent-hint :rules="codeRules" @update:model-value="onCodeInput" />
            </div>
          </section>
          <section class="form-section">
            <div class="form-section__title"><span class="step-dot">2</span><div><h3>Descripción</h3><p>Responsabilidades y alcance del rol.</p></div></div>
            <v-textarea v-model="form.description" label="Descripción (opcional)" name="role-description" prepend-inner-icon="mdi-text-box-outline" rows="3" auto-grow counter="250" :rules="descriptionRules" />
          </section>
          <v-alert type="info" variant="tonal" density="compact" icon="mdi-information-outline" class="mt-2">Los roles nuevos se registran en el catálogo. Los permisos operativos siguen ligados a los roles del sistema.</v-alert>
          <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mt-4" closable @click:close="error = ''">{{ error }}</v-alert>
          <v-alert v-if="success" type="success" variant="tonal" density="comfortable" class="mt-4" closable @click:close="success = ''">{{ success }}</v-alert>
          <div class="form-actions">
            <v-btn variant="text" @click="router.push('/panel')">Cancelar</v-btn>
            <v-btn class="submit-btn" type="submit" color="primary" size="large" :loading="loading" prepend-icon="mdi-badge-account-horizontal-outline">Dar de alta</v-btn>
          </div>
        </v-form>
      </v-card>

      <aside class="side-stack">
        <v-card class="panel-card preview-card" elevation="0">
          <div class="preview-card__top">
            <div class="preview-card__badge">
              <div class="tone-icon"><v-icon icon="mdi-badge-account-outline" /></div>
              <div><small>Vista previa</small><strong>{{ form.name.trim() || 'Nombre del rol' }}</strong></div>
            </div>
            <span class="preview-card__code">{{ form.code || 'CLAVE_DEL_ROL' }}</span>
          </div>
          <p class="preview-card__text">{{ form.description.trim() || 'La descripción aparecerá aquí mientras la escribe.' }}</p>
        </v-card>

        <v-card class="panel-card" elevation="0">
          <header class="panel-card__header">
            <div><h2>Roles registrados</h2><p>Personalizados por administración.</p></div>
            <v-chip size="small" variant="tonal" color="primary">{{ personalizados.length }}</v-chip>
          </header>
          <div v-if="rolesLoading" class="role-list"><v-skeleton-loader v-for="n in 2" :key="n" type="list-item-two-line" /></div>
          <div v-else-if="personalizados.length" class="role-list role-list--scroll">
            <div v-for="role in personalizados" :key="role.id" class="role-item">
              <div class="tone-icon tone-orange"><v-icon icon="mdi-badge-account-outline" size="20" /></div>
              <div><strong>{{ role.name }}</strong><code>{{ role.code }}</code></div>
            </div>
          </div>
          <div v-else class="empty-state"><v-icon icon="mdi-tray-plus" /><p>Este será el primer rol personalizado.</p></div>
          <v-divider class="my-4" />
          <small class="muted-note">Claves reservadas del sistema</small>
          <div class="chip-row"><v-chip v-for="code in reservedCodes" :key="code" size="x-small" label variant="outlined">{{ code }}</v-chip></div>
        </v-card>
      </aside>
    </div>

    <v-snackbar v-model="snackbar" color="success" location="top right" timeout="4000"><v-icon icon="mdi-check-circle" class="mr-2" />El rol «{{ created }}» fue dado de alta correctamente.</v-snackbar>
  </AppShell>
</template>
