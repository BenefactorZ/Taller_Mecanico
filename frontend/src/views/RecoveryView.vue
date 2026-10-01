<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
const router = useRouter(); const step = ref(1); const message = ref(''); const error = ref(''); const loading = ref(false)
const form = reactive({ email: '', code: '', new_password: '', confirm: '' })
const emailRules = [(v: string) => /.+@.+\..+/.test(v) || 'Ingrese un correo válido']
const codeRules = [(v: string) => /^\d{6}$/.test(v) || 'El código debe tener 6 dígitos']
const passwordRules = [(v: string) => v.length >= 12 || 'Use al menos 12 caracteres']
async function requestCode() { await execute(async () => { await api('/auth/recovery', { method: 'POST', body: JSON.stringify({ email: form.email }) }); message.value = 'Revise su correo. Si la cuenta existe, enviamos un código.'; step.value = 2 }) }
async function verify() { await execute(async () => { await api('/auth/recovery/verify', { method: 'POST', body: JSON.stringify({ email: form.email, code: form.code }) }); step.value = 3 }) }
async function changePassword() { if (form.new_password !== form.confirm) { error.value = 'Las contraseñas no coinciden'; return }; await execute(async () => { await api('/auth/recovery/reset', { method: 'POST', body: JSON.stringify({ email: form.email, code: form.code, new_password: form.new_password }) }); router.push('/ingresar') }) }
async function execute(action: () => Promise<void>) { error.value = ''; loading.value = true; try { await action() } catch (e) { error.value = e instanceof Error ? e.message : 'Error inesperado' } finally { loading.value = false } }
</script>
<template><div class="auth-page"><v-card class="auth-card" elevation="4"><v-card-title class="text-h5 font-weight-bold">Recuperar contraseña</v-card-title><v-card-text><v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert><v-alert v-if="message" type="success" variant="tonal" class="mb-4">{{ message }}</v-alert><v-form v-if="step === 1" @submit.prevent="requestCode"><v-text-field v-model="form.email" label="Correo registrado" type="email" :rules="emailRules" /><v-btn color="primary" block type="submit" :loading="loading">Enviar código</v-btn></v-form><v-form v-else-if="step === 2" @submit.prevent="verify"><v-text-field v-model="form.code" label="Código de verificación" inputmode="numeric" :rules="codeRules" /><v-btn color="primary" block type="submit" :loading="loading">Verificar código</v-btn></v-form><v-form v-else @submit.prevent="changePassword"><v-text-field v-model="form.new_password" label="Nueva contraseña" type="password" :rules="passwordRules" /><v-text-field v-model="form.confirm" label="Confirmar contraseña" type="password" /><v-btn color="primary" block type="submit" :loading="loading">Cambiar contraseña</v-btn></v-form><router-link class="recovery-link" to="/ingresar">Volver al acceso</router-link></v-card-text></v-card></div></template>
