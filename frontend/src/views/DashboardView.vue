<script setup lang="ts">
import { useRouter } from 'vue-router'
import { auth } from '../auth'
const router = useRouter(); const user = auth.user()!
function logout() { auth.clear(); router.push('/ingresar') }
</script>
<template><v-layout><v-app-bar color="white" elevation="1"><v-app-bar-title class="font-weight-bold">Taller Mecánico</v-app-bar-title><v-spacer/><span class="mr-4 text-body-2">{{ user.full_name }} · {{ user.role }}</span><v-btn icon="mdi-logout" title="Cerrar sesión" @click="logout" /></v-app-bar><v-main><v-container class="pt-12"><h1 class="text-h4 mb-2">Panel de trabajo</h1><p class="text-medium-emphasis mb-8">Sesión activa con el rol {{ user.role }}.</p><v-alert v-if="user.role === 'ADMINISTRADOR'" color="secondary" variant="tonal">Puede administrar empleados y sus accesos.<template #append><v-btn to="/empleados/nuevo" color="primary">Nuevo empleado</v-btn></template></v-alert><v-alert v-else type="info" variant="tonal">Las opciones de operación se habilitan de acuerdo con su rol.</v-alert></v-container></v-main></v-layout></template>
