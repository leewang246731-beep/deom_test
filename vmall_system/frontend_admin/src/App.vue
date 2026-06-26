<template>
  <ParticleBackground :enabled="true" />
  <CursorGlow />
  <router-view />
</template>

<script setup>
import ParticleBackground from './components/ParticleBackground.vue'
import CursorGlow from './components/CursorGlow.vue'
</script>
