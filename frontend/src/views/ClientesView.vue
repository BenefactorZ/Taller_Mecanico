<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { api } from '../api'
import { esContacto, iniciales } from '../clientes'
import { tienePermiso, type PaginaCustomers } from '../types'
import { auth } from '../auth'

const TAMANO = 8
const puedeAlta = tienePermiso(auth.user(), 'clientes.alta')
const router = useRouter(); const route = useRoute()
const criterio = ref(String(route.query.criterio ?? ''))
const resultados = ref<PaginaCustomers | null>(null)
const loading = ref(false); const error = ref(''); const buscado = ref('')
const paginas = computed(() => (resultados.value ? Math.max(1, Math.ceil(resultados.value.total / resultados.value.tamano)) : 1))
const pagina = computed({ get: () => resultados.value?.numero ?? 1, set: (valor: number) => { void buscar(valor) } })
const rango = computed(() => {
  const r = resultados.value
  return r && r.total ? `${(r.numero - 1) * r.tamano + 1}–${(r.numero - 1) * r.tamano + r.items.length} de ${r.total}` : ''
})

async function buscar(numero = 1) {
  error.value = ''
  const texto = (criterio.value ?? '').trim()
  if (!texto) { error.value = 'Escriba un nombre, un teléfono o un correo para buscar.'; return }
  loading.value = true
  try {
    // criterio → normalización (servidor) → búsqueda paginada → coincidencias
    resultados.value = await api<PaginaCustomers>(`/customers?criterio=${encodeURIComponent(texto)}&pagina=${numero}&tamano=${TAMANO}`)
    buscado.value = texto
    router.replace({ query: { criterio: texto, pagina: numero > 1 ? String(numero) : undefined } })
  } catch (e) { error.value = e instanceof Error ? e.message : 'No fue posible consultar los clientes' }
  finally { loading.value = false }
}

onMounted(() => { if (criterio.value.trim()) void buscar(Number(route.query.pagina) || 1) })
</script>

<template>
  <AppShell section="Clientes" title="Consultar clientes">
    <div class="page-head">
      <div class="page-head__icon"><v-icon icon="mdi-account-search-outline" /></div>
      <div class="page-head__grow"><span class="eyebrow">Clientes · Consulta</span><h1>Consultar clientes</h1><p>Busque por nombre completo o por contacto exacto (correo o teléfono) dentro de su taller.</p></div>
      <v-btn v-if="puedeAlta" class="submit-btn d-none d-sm-flex" color="primary" size="large" prepend-icon="mdi-account-plus-outline" to="/clientes/nuevo">Nuevo cliente</v-btn>
    </div>

    <v-card class="panel-card" elevation="0">
      <v-form class="search-bar" autocomplete="off" @submit.prevent="buscar(1)">
        <v-text-field v-model="criterio" class="search-bar__field" label="Nombre, teléfono o correo" name="cliente-criterio" autocomplete="nope" prepend-inner-icon="mdi-magnify" clearable hide-details="auto" />
        <v-btn class="submit-btn" type="submit" color="primary" size="large" :loading="loading" prepend-icon="mdi-magnify">Buscar</v-btn>
      </v-form>
      <v-alert v-if="error" type="error" variant="tonal" density="comfortable" class="mt-4" closable @click:close="error = ''">{{ error }}</v-alert>

      <div v-if="!resultados && !loading" class="empty-state empty-state--lg">
        <v-icon icon="mdi-account-search-outline" /><p>Escriba un nombre, un teléfono o un correo y pulse <strong>Buscar</strong>.</p>
      </div>

      <template v-else-if="resultados">
        <div v-if="resultados.total === 0" class="empty-state empty-state--lg">
          <v-icon icon="mdi-account-off-outline" />
          <p>No hay clientes que coincidan con «<strong>{{ buscado }}</strong>».</p>
          <v-btn v-if="puedeAlta" color="primary" variant="tonal" prepend-icon="mdi-account-plus-outline" :to="{ path: '/clientes/nuevo', query: { q: buscado } }">Dar de alta a este cliente</v-btn>
        </div>
        <template v-else>
          <div class="result-meta"><span>{{ resultados.total }} resultado{{ resultados.total === 1 ? '' : 's' }}</span><span>{{ rango }}</span></div>
          <div class="result-list" :class="{ 'is-loading': loading }">
            <router-link v-for="c in resultados.items" :key="c.id" class="result-row" :to="`/clientes/${c.id}`">
              <v-avatar class="avatar-initials" size="42">{{ iniciales(c.nombre_completo) }}</v-avatar>
              <div class="result-row__body"><strong>{{ c.nombre_completo }}</strong><span><v-icon icon="mdi-pound" size="14" />ID {{ c.id }} · <v-icon icon="mdi-phone-outline" size="14" />{{ c.telefono ?? 'Sin teléfono' }} · <v-icon icon="mdi-email-outline" size="14" />{{ c.correo ?? 'Sin correo' }}</span></div>
              <v-chip size="x-small" label :color="c.estado === 'ACTIVO' ? 'success' : 'warning'" variant="tonal">{{ c.estado === 'ACTIVO' ? 'Activo' : 'Suspendido' }}</v-chip>
              <v-icon class="result-row__go" icon="mdi-chevron-right" />
            </router-link>
          </div>
          <v-pagination v-if="paginas > 1" v-model="pagina" class="mt-4" :length="paginas" :total-visible="5" density="comfortable" rounded="lg" />
        </template>
        <p v-if="!esContacto(buscado)" class="muted-note mt-4">Consejo: para buscar por teléfono o correo escriba el dato completo.</p>
      </template>
    </v-card>
  </AppShell>
</template>
