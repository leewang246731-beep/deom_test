<template>
  <div class="progress-ring" :style="{ width: size + 'px', height: size + 'px' }">
    <svg :width="size" :height="size" viewBox="0 0 100 100">
      <!-- Background circle -->
      <circle
        cx="50"
        cy="50"
        :r="radius"
        fill="none"
        :stroke="bgColor"
        :stroke-width="strokeWidth"
      />
      <!-- Progress circle -->
      <circle
        cx="50"
        cy="50"
        :r="radius"
        fill="none"
        :stroke="strokeColor"
        :stroke-width="strokeWidth"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="offset"
        stroke-linecap="round"
        class="progress-ring__circle"
      />
    </svg>
    <div class="progress-ring__center">
      <span class="progress-ring__value">{{ displayText }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed, watch, ref, onMounted } from 'vue'
import { useProgressRing } from '../composables/useProgress'

const props = defineProps({
  percentage: { type: Number, default: 0 },
  size: { type: Number, default: 80 },
  strokeWidth: { type: Number, default: 4 },
  colorStart: { type: String, default: '#2A6BFF' },
  colorEnd: { type: String, default: '#22C55E' },
  text: { type: String, default: '' },
})

const radius = 42 // centered in 100x100 viewBox
const { displayValue, circumference, offset, setValue } = useProgressRing(0, radius)

onMounted(() => {
  setValue(props.percentage, 800)
})

watch(() => props.percentage, (val) => {
  setValue(val, 600)
})

const bgColor = '#E8ECF1'

// Color transition: blue → green based on percentage
const strokeColor = computed(() => {
  const p = displayValue.value / 100
  // Simple linear interpolation between colorStart and colorEnd
  if (p <= 0.3) return props.colorStart
  if (p >= 0.7) return props.colorEnd
  // We'll keep it simple: just show the start color, shifting at thresholds
  return p > 0.5 ? props.colorEnd : props.colorStart
})

const displayText = computed(() => {
  if (props.text) return props.text
  return Math.round(displayValue.value) + '%'
})
</script>

<style scoped>
.progress-ring {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.progress-ring svg {
  transform: rotate(-90deg);
}

.progress-ring__circle {
  transition: stroke-dashoffset 0.1s linear, stroke 0.6s ease;
}

.progress-ring__center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.progress-ring__value {
  font-size: 16px;
  font-weight: 600;
  color: #1F2937;
}
</style>
