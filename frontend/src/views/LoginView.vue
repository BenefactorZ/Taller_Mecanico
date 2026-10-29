<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import AuthLayout from '../components/AuthLayout.vue'
import { api } from '../api'
import { auth } from '../auth'
import type { User } from '../types'

type FormRef = { validate: () => Promise<{ valid: boolean }> }
const router = useRouter()
const formRef = ref<FormRef | null>(null)
const form = reactive({ email: '', password: '' })
const loading = ref(false), error = ref(''), showPassword = ref(false)
const emailRules = [(v: string) => /.+@.+\..+/.test(v) || 'Ingrese un correo válido']
const passwordRules = [(v: string) => v.length >= 8 || 'La contraseña es obligatoria']
async function submit() {
  error.value = ''
  if (!(await formRef.value?.validate())?.valid) return
  loading.value = true
  try { const data = await api<{ access_token: string; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify(form) }); auth.set(data.access_token, data.user); router.push('/panel') }
  catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible ingresar' }
  finally { loading.value = false }
}
</script>

<template>
  <AuthLayout title="Bienvenido de nuevo" subtitle="Ingrese con su correo para acceder al panel del taller.">
    <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mb-5">{{ error }}</v-alert>
    <v-form ref="formRef" @submit.prevent="submit">
      <v-text-field v-model="form.email" label="Correo" type="email" autocomplete="username" prepend-inner-icon="mdi-email-outline" :rules="emailRules" />
      <v-text-field v-model="form.password" label="Contraseña" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" prepend-inner-icon="mdi-lock-outline" :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'" :rules="passwordRules" @click:append-inner="showPassword = !showPassword" />
      <div class="form-row-end"><router-link class="auth-link" to="/recuperar">¿Olvidó su contraseña?</router-link></div>
      <v-btn class="submit-btn" block size="large" color="primary" type="submit" :loading="loading" append-icon="mdi-arrow-right">Ingresar</v-btn>
    </v-form>
    <div class="auth-footer"><span class="auth-footer__text">¿No tiene cuenta?</span><router-link class="auth-link" to="/registro">Crear cuenta</router-link></div>
    <p class="auth-note"><v-icon icon="mdi-lock-check-outline" size="16" />Su contraseña nunca se muestra ni se almacena en texto plano.</p>
  </AuthLayout>
</template>
