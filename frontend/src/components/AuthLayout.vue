<script setup lang="ts">
defineProps<{ title: string; subtitle: string }>()
const year = new Date().getFullYear()
const features = [
  { icon: 'mdi-shield-lock-outline', text: 'Contraseñas con Argon2 y sesiones JWT' },
  { icon: 'mdi-account-key-outline', text: 'Permisos por rol validados en el servidor' },
  { icon: 'mdi-store-cog-outline', text: 'Personal organizado por sucursal' }
]
</script>

<template>
  <div class="auth-page">
    <aside class="auth-hero">
      <div class="auth-hero__glow auth-hero__glow--a" />
      <div class="auth-hero__glow auth-hero__glow--b" />
      <div class="auth-brand"><div class="brand-mark"><v-icon icon="mdi-car-wrench" /></div>Taller Mecánico</div>
      <div class="auth-hero__copy">
        <span class="auth-kicker"><v-icon icon="mdi-lightning-bolt" size="14" />Plataforma de gestión</span>
        <h2>Su taller organizado, de la recepción a la entrega.</h2>
        <p>Controle accesos, personal y operación desde un solo lugar, con la seguridad validada en cada solicitud.</p>
        <ul class="auth-features">
          <li v-for="feature in features" :key="feature.text"><v-icon :icon="feature.icon" size="20" />{{ feature.text }}</li>
        </ul>
      </div>
      <small>© {{ year }} Taller Mecánico · Capa de seguridad</small>
    </aside>
    <main class="auth-panel">
      <div class="auth-panel__inner">
        <div class="auth-brand auth-brand--mobile"><div class="brand-mark"><v-icon icon="mdi-car-wrench" /></div>Taller Mecánico</div>
        <slot name="top" />
        <h1>{{ title }}</h1>
        <p class="auth-panel__subtitle">{{ subtitle }}</p>
        <slot />
      </div>
    </main>
  </div>
</template>
