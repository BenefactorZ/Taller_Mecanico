<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthLayout from '../components/AuthLayout.vue'
import { api } from '../api'

type FormRef = { validate: () => Promise<{ valid: boolean }> }
const router = useRouter(); const step = ref(1); const message = ref(''); const error = ref(''); const loading = ref(false); const showPassword = ref(false)
const formRef = ref<FormRef | null>(null)
const form = reactive({ email: '', code: '', new_password: '', confirm: '' })
const steps = ['Correo', 'Código', 'Contraseña']
const subtitles = ['Le enviaremos un código de 6 dígitos al correo registrado.', 'Escriba el código que recibió. Caduca en pocos minutos.', 'Defina una contraseña nueva de al menos 12 caracteres.']
const subtitle = computed(() => subtitles[step.value - 1])
const emailRules = [(v: string) => /.+@.+\..+/.test(v) || 'Ingrese un correo válido']
const codeRules = [(v: string) => /^\d{6}$/.test(v) || 'El código debe tener 6 dígitos']
const passwordRules = [(v: string) => v.length >= 12 || 'Use al menos 12 caracteres']
const confirmRules = [(v: string) => v === form.new_password || 'Las contraseñas no coinciden']
async function requestCode() { await execute(async () => { await api('/auth/recovery', { method: 'POST', body: JSON.stringify({ email: form.email }) }); message.value = 'Revise su correo. Si la cuenta existe, enviamos un código.'; step.value = 2 }) }
async function verify() { await execute(async () => { await api('/auth/recovery/verify', { method: 'POST', body: JSON.stringify({ email: form.email, code: form.code }) }); message.value = 'Código verificado. Ya puede definir su nueva contraseña.'; step.value = 3 }) }
async function changePassword() { await execute(async () => { await api('/auth/recovery/reset', { method: 'POST', body: JSON.stringify({ email: form.email, code: form.code, new_password: form.new_password }) }); router.push('/ingresar') }) }
async function resendCode() { form.code = ''; await execute(async () => { await api('/auth/recovery', { method: 'POST', body: JSON.stringify({ email: form.email }) }); message.value = 'Enviamos un código nuevo. El anterior ya no es válido.' }, false) }
function changeEmail() { step.value = 1; form.code = ''; message.value = ''; error.value = '' }
async function execute(action: () => Promise<void>, validate = true) {
  error.value = ''
  if (validate && !(await formRef.value?.validate())?.valid) return
  loading.value = true
  try { await action() } catch (e) { error.value = e instanceof Error ? e.message : 'Error inesperado' } finally { loading.value = false }
}
</script>

<template>
  <AuthLayout title="Recuperar contraseña" :subtitle="subtitle">
    <template #top>
      <div class="steps">
        <div v-for="(label, index) in steps" :key="label" class="step" :class="{ 'is-active': index + 1 <= step, 'is-current': index + 1 === step }">
          <span class="step__bar" /><small>{{ index + 1 }}. {{ label }}</small>
        </div>
      </div>
    </template>
    <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mb-5">{{ error }}</v-alert>
    <v-alert v-if="message" type="success" variant="tonal" density="comfortable" class="mb-5">{{ message }}</v-alert>
    <v-form v-if="step === 1" ref="formRef" @submit.prevent="requestCode">
      <v-text-field v-model="form.email" label="Correo registrado" type="email" autocomplete="username" prepend-inner-icon="mdi-email-outline" :rules="emailRules" />
      <v-btn class="submit-btn" color="primary" block size="large" type="submit" :loading="loading" append-icon="mdi-send-outline">Enviar código</v-btn>
    </v-form>
    <v-form v-else-if="step === 2" ref="formRef" @submit.prevent="verify">
      <v-text-field v-model="form.code" class="code-field" label="Código de verificación" inputmode="numeric" maxlength="6" autocomplete="one-time-code" prepend-inner-icon="mdi-numeric" :rules="codeRules" />
      <v-btn class="submit-btn" color="primary" block size="large" type="submit" :loading="loading" append-icon="mdi-check">Verificar código</v-btn>
      <div class="auth-inline-actions"><button type="button" class="auth-link" @click="changeEmail">Cambiar correo</button><button type="button" class="auth-link" :disabled="loading" @click="resendCode">Reenviar código</button></div>
    </v-form>
    <v-form v-else ref="formRef" @submit.prevent="changePassword">
      <v-text-field v-model="form.new_password" label="Nueva contraseña" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" prepend-inner-icon="mdi-lock-outline" :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'" :rules="passwordRules" @click:append-inner="showPassword = !showPassword" />
      <v-text-field v-model="form.confirm" label="Confirmar contraseña" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" prepend-inner-icon="mdi-lock-check-outline" :rules="confirmRules" />
      <v-btn class="submit-btn" color="primary" block size="large" type="submit" :loading="loading" append-icon="mdi-content-save-outline">Cambiar contraseña</v-btn>
    </v-form>
    <div class="auth-footer"><router-link class="auth-link" to="/ingresar"><v-icon icon="mdi-arrow-left" size="16" /> Volver al acceso</router-link></div>
  </AuthLayout>
</template>
