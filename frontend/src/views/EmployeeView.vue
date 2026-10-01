<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import type { Role } from '../types'
const router = useRouter(); const error = ref(''); const success = ref(''); const loading = ref(false)
const form = reactive({ full_name: '', email: '', password: '', role: 'RECEPCIONISTA' as Role, branch: '' })
const roles = [{ title: 'Recepcionista', value: 'RECEPCIONISTA' }, { title: 'Asesor de servicio', value: 'ASESOR_SERVICIO' }, { title: 'Técnico', value: 'TECNICO' }]
const emailRules = [(v: string) => /.+@.+\..+/.test(v) || 'Ingrese un correo válido']; const nameRules = [(v: string) => v.trim().length >= 3 || 'Ingrese el nombre completo']; const passwordRules = [(v: string) => v.length >= 12 || 'Use al menos 12 caracteres']
async function submit() { error.value = ''; success.value = ''; loading.value = true; try { await api('/users/employees', { method: 'POST', body: JSON.stringify(form) }); success.value = 'Usuario dado de alta correctamente'; Object.assign(form, { full_name: '', email: '', password: '', role: 'RECEPCIONISTA', branch: '' }) } catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible registrar el usuario' } finally { loading.value = false } }
</script>
<template><v-container class="pt-12 content-width"><v-btn variant="text" prepend-icon="mdi-arrow-left" @click="router.push('/panel')">Panel</v-btn><h1 class="text-h4 my-5">Alta de empleado</h1><v-alert v-if="error" type="error" variant="tonal" class="mb-4">{{ error }}</v-alert><v-alert v-if="success" type="success" variant="tonal" class="mb-4">{{ success }}</v-alert><v-form @submit.prevent="submit"><v-text-field v-model="form.full_name" label="Nombre completo" :rules="nameRules" /><v-text-field v-model="form.email" label="Correo" type="email" :rules="emailRules" /><v-select v-model="form.role" label="Rol" :items="roles" /><v-text-field v-model="form.branch" label="Sucursal" :rules="[(v: string) => !!v || 'La sucursal es obligatoria']" /><v-text-field v-model="form.password" label="Contraseña temporal" type="password" :rules="passwordRules" /><v-btn type="submit" color="primary" :loading="loading">Dar de alta</v-btn></v-form></v-container></template>
