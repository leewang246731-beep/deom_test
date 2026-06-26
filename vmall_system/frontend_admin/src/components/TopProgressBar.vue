<template>
  <transition name="top-progress">
    <div v-if="visible" class="top-progress-bar">
      <div
        class="top-progress-bar__fill"
        :class="{ 'top-progress-bar__fill--indeterminate': indeterminate }"
        :style="fillStyle"
      />
    </div>
  </transition>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  loading: { type: Boolean, default: false },
  percentage: { type: Number, default: 0 },
})

const visible = ref(false)
const completed = ref(false)

watch(() => props.loading, (val) => {
  if (val) {
    visible.value = true
    completed.value = false
  } else if (visible.value && !completed.value) {
    // Transition to complete
    completed.value = true
    setTimeout(() => {
      visible.value = false
      completed.value = false
    }, 500)
  }
})

watch(() => props.percentage, (val) => {
  if (val >= 100 && !completed.value) {
    completed.value = true
    setTimeout(() => {
      visible.value = false
      completed.value = false
    }, 500)
  }
})

const indeterminate = computed(() => {
  return props.loading && props.percentage === 0
})

const fillStyle = computed(() => {
  if (completed.value) return { width: '100%', backgroundColor: '#22C55E' }
  if (indeterminate.value) return { width: '30%' }
  return { width: Math.min(props.percentage, 100) + '%', backgroundColor: '#2A6BFF' }
})
</script>

<style scoped>
.top-progress-bar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  z-index: 10000;
  background: transparent;
  pointer-events: none;
}

.top-progress-bar__fill {
  height: 100%;
  transition: width 0.3s ease, background-color 0.4s ease;
  border-radius: 0 2px 2px 0;
}

.top-progress-bar__fill--indeterminate {
  animation: indeterminate-slide 1.5s ease-in-out infinite;
}

@keyframes indeterminate-slide {
  0% { transform: translateX(-100%); }
  50% { transform: translateX(150%); }
  100% { transform: translateX(350%); }
}

.top-progress-enter-active {
  transition: opacity 0.2s ease;
}

.top-progress-leave-active {
  transition: opacity 0.4s ease 0.3s;
}

.top-progress-enter-from,
.top-progress-leave-to {
  opacity: 0;
}
</style>
