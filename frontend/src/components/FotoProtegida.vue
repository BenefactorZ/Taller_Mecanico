<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { apiBlob } from '../api'

// Las imágenes están protegidas con el token de sesión: se descargan con la API y se muestran desde un objeto local
const props = defineProps<{ ruta: string; tiene: boolean; tamano?: number; icono?: string }>()
const url = ref(''); const fallo = ref(false)
const soltar = () => { if (url.value) URL.revokeObjectURL(url.value); url.value = '' }

watch(() => [props.ruta, props.tiene], async () => {
  soltar(); fallo.value = false
  if (!props.tiene) return
  const turno = props.ruta
  try {
    const objeto = URL.createObjectURL(await apiBlob(props.ruta))
    if (turno === props.ruta) url.value = objeto; else URL.revokeObjectURL(objeto)
  } catch { fallo.value = true }
}, { immediate: true })
onBeforeUnmount(soltar)
</script>

<template>
  <div class="foto-taller" :style="{ width: `${tamano ?? 64}px`, height: `${tamano ?? 64}px` }">
    <img v-if="url" :src="url" alt="Imagen">
    <v-icon v-else :icon="fallo ? 'mdi-image-broken-variant' : (icono ?? 'mdi-image-outline')" :size="Math.round((tamano ?? 64) / 2.4)" />
  </div>
</template>
