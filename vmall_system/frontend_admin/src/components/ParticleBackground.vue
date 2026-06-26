<template>
  <canvas
    v-show="enabled"
    ref="canvasEl"
    class="particle-canvas"
  />
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useParticleBackground } from '../composables/useParticleBackground'

const props = defineProps({
  enabled: { type: Boolean, default: true },
  color: { type: String, default: '26, 58, 92' },
  count: { type: Number, default: 80 },
  opacity: { type: Number, default: 0.3 },
})

const canvasEl = ref(null)
const { init, destroy, toggle } = useParticleBackground()

onMounted(() => {
  if (canvasEl.value && props.enabled) {
    init(canvasEl.value, {
      color: props.color,
      particleCount: props.count,
      opacity: props.opacity,
    })
  }
})

watch(() => props.enabled, (val) => {
  if (val) {
    if (canvasEl.value) {
      init(canvasEl.value, {
        color: props.color,
        particleCount: props.count,
        opacity: props.opacity,
      })
    }
  } else {
    destroy()
  }
})

defineExpose({ toggle })
</script>

<style scoped>
.particle-canvas {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
}
</style>
