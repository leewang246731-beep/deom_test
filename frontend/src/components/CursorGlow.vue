<template>
  <div
    v-show="isVisible"
    class="cursor-glow"
    :style="glowStyle"
  />
</template>

<script setup>
import { computed } from 'vue'
import { useCursorGlow } from '../composables/useMouseInteraction'

const { cursorX, cursorY, isVisible } = useCursorGlow()

const glowStyle = computed(() => ({
  left: cursorX.value + 'px',
  top: cursorY.value + 'px',
}))
</script>

<style scoped>
.cursor-glow {
  position: fixed;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 1.5px solid rgba(42, 107, 255, 0.3);
  pointer-events: none;
  z-index: 9999;
  transition: left 0.05s linear, top 0.05s linear;
  transform: translate(-50%, -50%);
  box-shadow: 0 0 12px 2px rgba(42, 107, 255, 0.12);
}
</style>
