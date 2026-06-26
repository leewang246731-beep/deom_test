<template>
  <div class="progress-bar-wrapper">
    <div
      class="progress-bar"
      :style="{ height: height + 'px', borderRadius: height + 'px' }"
    >
      <div
        class="progress-bar__fill"
        :class="{ shimmer: animating }"
        :style="fillStyle"
      />
    </div>
    <span v-if="showText" class="progress-bar__text">
      {{ displayText }}
    </span>
  </div>
</template>

<script setup>
import { computed, watch, ref, onMounted } from 'vue'
import { useProgressBar } from '../composables/useProgress'

const props = defineProps({
  percentage: { type: Number, default: 0 },
  showText: { type: Boolean, default: true },
  height: { type: Number, default: 6 },
  color: { type: String, default: '#2A6BFF' },
  text: { type: String, default: '' },
  animating: { type: Boolean, default: true },
})

const { displayValue, setValue } = useProgressBar(0)

onMounted(() => {
  setValue(props.percentage, 800)
})

watch(() => props.percentage, (val) => {
  setValue(val, 600)
})

const fillStyle = computed(() => ({
  width: displayValue.value + '%',
  backgroundColor: props.color,
  transition: 'width 0.1s linear',
}))

const displayText = computed(() => {
  if (props.text) return props.text
  return Math.round(displayValue.value) + '%'
})
</script>

<style scoped>
.progress-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.progress-bar {
  flex: 1;
  background: #E8ECF1;
  overflow: hidden;
  position: relative;
}

.progress-bar__fill {
  height: 100%;
  border-radius: inherit;
  position: relative;
  min-width: 0;
  will-change: width;
}

.progress-bar__fill.shimmer::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.35) 25%,
    rgba(255, 255, 255, 0.5) 50%,
    rgba(255, 255, 255, 0.35) 75%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: shimmer 2s linear infinite;
  border-radius: inherit;
  pointer-events: none;
}

.progress-bar__text {
  font-size: 13px;
  font-weight: 500;
  color: #4B5563;
  white-space: nowrap;
  min-width: 40px;
  text-align: right;
}

@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
</style>
