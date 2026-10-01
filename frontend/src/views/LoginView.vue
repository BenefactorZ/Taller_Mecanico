<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { auth } from '../auth'
import type { User } from '../types'

const router = useRouter()
const form = reactive({ email: '', password: '' })
const loading = ref(false), error = ref('')
const emailRules = [(v: string) => /.+@.+\..+/.test(v) || 'Ingrese un correo válido']
const passwordRules = [(v: string) => v.length >= 8 || 'La contraseña es obligatoria']
async function submit() {
  error.value = ''; loading.value = true
  try { const data = await api<{ access_token: string; user: User }>('/auth/login', { method: 'POST', body: JSON.stringify(form) }); auth.set(data.access_token, data.user); router.push('/panel') }
  catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible ingresar' }
  finally { loading.value = false }
}
</script>
<template><div class="auth-page"><v-card class="auth-card" elevation="4"><v-card-title class="text-h5 font-weight-bold">Taller Mecánico</v-card-title><v-card-subtitle>Acceso al sistema</v-card-subtitle><v-card-text><v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert><v-form @submit.prevent="submit"><v-text-field v-model="form.email" label="Correo" type="email" :rules="emailRules" prepend-inner-icon="mdi-email-outline" /><v-text-field v-model="form.password" label="Contraseña" type="password" :rules="passwordRules" prepend-inner-icon="mdi-lock-outline" /><v-btn block color="primary" type="submit" :loading="loading">Ingresar</v-btn></v-form><router-link class="recovery-link" to="/recuperar">¿Olvidó su contraseña?</router-link></v-card-text></v-card></div></template>
