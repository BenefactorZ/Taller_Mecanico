<script setup lang="ts">
// Botón para alternar entre los registros activos y los suspendidos (borrado lógico) de una administración.
defineProps<{ modelValue: boolean }>()
defineEmits<{ 'update:modelValue': [valor: boolean] }>()
</script>

<template>
  <v-btn-toggle class="filtro-suspendidos" :model-value="modelValue" mandatory divided density="comfortable" color="primary" variant="outlined" @update:model-value="$emit('update:modelValue', $event === true)">
    <v-btn :value="false" prepend-icon="mdi-check-circle-outline">Activos</v-btn>
    <v-btn :value="true" prepend-icon="mdi-pause-circle-outline">Suspendidos</v-btn>
  </v-btn-toggle>
</template>
