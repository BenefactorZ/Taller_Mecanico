<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { api } from '../api'
import { iniciales } from '../clientes'
import { tienePermiso, type Customer } from '../types'
import { auth } from '../auth'

const route = useRoute(); const router = useRouter()
const puedeAlta = tienePermiso(auth.user(), 'clientes.alta')
const customer = ref<Customer | null>(null); const loading = ref(true); const error = ref('')
// Si se llegó desde una búsqueda se vuelve a ella; si no (enlace directo), a la consulta
const volver = () => (window.history.state?.back ? router.back() : router.push('/clientes'))

onMounted(async () => {
  try { customer.value = await api<Customer>(`/customers/${route.params.id}`) }
  catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible cargar la ficha' }
  finally { loading.value = false }
})
</script>

<template>
  <AppShell section="Clientes" title="Ficha de cliente">
    <v-btn class="mb-4" variant="text" prepend-icon="mdi-arrow-left" @click="volver">Volver</v-btn>

    <v-card v-if="loading" class="panel-card" elevation="0"><v-skeleton-loader type="avatar, article" /></v-card>
    <v-alert v-else-if="error" type="error" variant="tonal" density="comfortable" icon="mdi-account-off-outline">{{ error }}</v-alert>

    <div v-else-if="customer" class="ficha">
      <v-card class="panel-card ficha__card" elevation="0">
        <div class="ficha__head">
          <v-avatar class="avatar-initials" size="72">{{ iniciales(customer.nombre_completo) }}</v-avatar>
          <div>
            <span class="eyebrow">Cliente #{{ customer.id }}</span>
            <h1>{{ customer.nombre_completo }}</h1>
            <v-chip size="small" label :color="customer.estado === 'ACTIVO' ? 'success' : 'warning'" variant="tonal">{{ customer.estado === 'ACTIVO' ? 'Activo' : 'Suspendido' }}</v-chip>
          </div>
        </div>
        <dl class="summary-list">
          <div><dt><v-icon icon="mdi-pound" size="16" />ID</dt><dd>{{ customer.id }}</dd></div>
          <div><dt><v-icon icon="mdi-account-outline" size="16" />Nombre completo</dt><dd>{{ customer.nombre_completo }}</dd></div>
          <div><dt><v-icon icon="mdi-phone-outline" size="16" />Teléfono</dt><dd>{{ customer.telefono ?? 'Sin registrar' }}</dd></div>
          <div><dt><v-icon icon="mdi-email-outline" size="16" />Correo</dt><dd>{{ customer.correo ?? 'Sin registrar' }}</dd></div>
          <div><dt><v-icon icon="mdi-check-decagram-outline" size="16" />Estado</dt><dd>{{ customer.estado === 'ACTIVO' ? 'Activo' : 'Suspendido' }}</dd></div>
        </dl>
        <div class="form-actions">
          <v-btn variant="text" to="/clientes">Ir a consulta</v-btn>
          <v-btn v-if="puedeAlta" color="primary" prepend-icon="mdi-account-plus-outline" to="/clientes/nuevo">Nuevo cliente</v-btn>
        </div>
      </v-card>
    </div>
  </AppShell>
</template>
