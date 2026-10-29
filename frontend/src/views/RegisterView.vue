<script setup lang="ts">
import { reactive, ref } from 'vue'
import AuthLayout from '../components/AuthLayout.vue'
import { api } from '../api'

type FormRef = { validate: () => Promise<{ valid: boolean }> }
const formRef = ref<FormRef | null>(null)
const form = reactive({ full_name: '', email: '', password: '', confirm: '' })
const loading = ref(false); const error = ref(''); const showPassword = ref(false); const creada = ref('')
const nameRules = [(v: string) => v.trim().split(/\s+/).length >= 2 && v.trim().length >= 3 || 'Ingrese su nombre completo (nombre y apellido)']
const emailRules = [(v: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v.trim()) || 'Ingrese un correo válido']
const passwordRules = [(v: string) => v.length >= 12 || 'Use al menos 12 caracteres']
const confirmRules = [(v: string) => v === form.password || 'Las contraseñas no coinciden']

async function submit() {
  error.value = ''
  if (!(await formRef.value?.validate())?.valid) { error.value = 'Revise los campos marcados en rojo.'; return }
  loading.value = true
  try {
    await api('/auth/register', { method: 'POST', body: JSON.stringify({ full_name: form.full_name, email: form.email.trim(), password: form.password }) })
    creada.value = form.email.trim().toLowerCase()
  } catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible crear la cuenta' }
  finally { loading.value = false }
}
</script>

<template>
  <AuthLayout :title="creada ? 'Cuenta creada' : 'Crear cuenta'" :subtitle="creada ? 'Ya puede ingresar al sistema.' : 'Regístrese como invitado. Un administrador le asignará su rol.'">
    <div v-if="creada" class="success-hero success-hero--left">
      <div class="success-hero__icon"><v-icon icon="mdi-account-check-outline" /></div>
      <p>Su cuenta <strong>{{ creada }}</strong> se registró con el rol <strong>Invitado</strong>. Podrá ingresar, pero no operará el sistema hasta que un administrador le asigne un rol.</p>
      <v-btn class="submit-btn mt-6" block size="large" color="primary" to="/ingresar" append-icon="mdi-arrow-right">Ir a ingresar</v-btn>
    </div>
    <template v-else>
      <v-form ref="formRef" autocomplete="off" @submit.prevent="submit">
        <v-text-field v-model="form.full_name" label="Nombre completo" name="registro-nombre" autocomplete="nope" prepend-inner-icon="mdi-account-outline" :rules="nameRules" />
        <v-text-field v-model="form.email" label="Correo" type="email" name="registro-correo" autocomplete="nope" prepend-inner-icon="mdi-email-outline" :rules="emailRules" />
        <v-text-field v-model="form.password" label="Contraseña" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" prepend-inner-icon="mdi-lock-outline" :append-inner-icon="showPassword ? 'mdi-eye-off-outline' : 'mdi-eye-outline'" hint="Mínimo 12 caracteres" persistent-hint :rules="passwordRules" @click:append-inner="showPassword = !showPassword" />
        <v-text-field v-model="form.confirm" class="mt-3" label="Confirmar contraseña" :type="showPassword ? 'text' : 'password'" autocomplete="new-password" prepend-inner-icon="mdi-lock-check-outline" :rules="confirmRules" />
        <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mb-4" closable @click:close="error = ''">{{ error }}</v-alert>
        <v-btn class="submit-btn" block size="large" color="primary" type="submit" :loading="loading" append-icon="mdi-account-plus-outline">Crear cuenta</v-btn>
      </v-form>
      <div class="auth-footer"><router-link class="auth-link" to="/ingresar"><v-icon icon="mdi-arrow-left" size="16" /> Ya tengo una cuenta</router-link></div>
    </template>
  </AuthLayout>
</template>
