<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { apiBlob } from '../api'

// La foto está protegida con el token de sesión, así que se descarga con la API y se muestra desde un objeto local
const props = defineProps<{ id: number; tiene: boolean; tamano?: number }>()
const url = ref(''); const fallo = ref(false)
const soltar = () => { if (url.value) URL.revokeObjectURL(url.value); url.value = '' }

watch(() => [props.id, props.tiene], async () => {
  soltar(); fallo.value = false
  if (!props.tiene) return
  const turno = props.id
  try {
    const objeto = URL.createObjectURL(await apiBlob(`/talleres/${props.id}/foto`))
    if (turno === props.id) url.value = objeto; else URL.revokeObjectURL(objeto)
  } catch { fallo.value = true }
}, { immediate: true })
onBeforeUnmount(soltar)
</script>

<template>
  <div class="foto-taller" :style="{ width: `${tamano ?? 64}px`, height: `${tamano ?? 64}px` }">
    <img v-if="url" :src="url" alt="Foto del taller">
    <v-icon v-else :icon="fallo ? 'mdi-image-broken-variant' : 'mdi-garage-variant'" :size="Math.round((tamano ?? 64) / 2.4)" />
  </div>
</template>
