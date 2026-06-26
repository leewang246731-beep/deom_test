<template>
  <div class="step-indicator" :class="'step-indicator--' + direction">
    <div
      v-for="(step, i) in stepList"
      :key="i"
      class="step-item"
      :class="'step-item--' + step.status"
    >
      <!-- Connector line (before the node) -->
      <div
        v-if="i > 0"
        class="step-connector"
        :class="'step-connector--' + stepList[i - 1].status"
      />

      <!-- Node -->
      <div class="step-node" :class="{ 'pulse-glow': step.pulse }">
        <svg
          v-if="step.status === 'completed'"
          class="step-check"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="3"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <polyline points="20 6 9 17 4 12" />
        </svg>
        <span v-else-if="step.status === 'active'" class="step-dot" />
        <span v-else class="step-dot step-dot--empty" />
      </div>

      <!-- Label -->
      <div class="step-label">
        <span class="step-title">{{ step.title }}</span>
        <span v-if="step.description" class="step-desc">{{ step.description }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useStepIndicator } from '../composables/useProgress'

const props = defineProps({
  steps: {
    type: Array,
    default: () => [],
    // Each step: { title: string, description?: string }
  },
  current: { type: Number, default: 0 },
  direction: {
    type: String,
    default: 'horizontal',
    validator: (v) => ['horizontal', 'vertical'].includes(v),
  },
})

const { steps: stepStates } = useStepIndicator(props.steps.length, props.current)

const stepList = computed(() => {
  return props.steps.map((step, i) => ({
    ...step,
    ...stepStates.value[i],
  }))
})
</script>

<style scoped>
.step-indicator {
  display: flex;
  width: 100%;
}

.step-indicator--horizontal {
  flex-direction: row;
  align-items: flex-start;
}

.step-indicator--vertical {
  flex-direction: column;
  align-items: flex-start;
}

.step-item {
  display: flex;
  align-items: center;
  flex: 1;
  position: relative;
}

.step-indicator--vertical .step-item {
  flex: none;
  min-height: 60px;
}

.step-connector {
  flex: 1;
  height: 2px;
  background: #E4E7ED;
  margin: 0 8px;
}

.step-indicator--vertical .step-connector {
  width: 2px;
  height: 100%;
  position: absolute;
  left: 13px;
  top: 28px;
}

.step-connector--completed {
  background: #2A6BFF;
}

.step-node {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

.step-item--completed .step-node {
  background: #2A6BFF;
  color: #fff;
}

.step-item--active .step-node {
  background: #fff;
  border: 2.5px solid #2A6BFF;
}

.step-item--pending .step-node {
  background: #fff;
  border: 2px solid #D1D5DB;
}

.step-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #2A6BFF;
}

.step-dot--empty {
  background: #D1D5DB;
}

.step-check {
  width: 14px;
  height: 14px;
}

.pulse-glow {
  animation: pulse-glow 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.step-label {
  margin-left: 10px;
  display: flex;
  flex-direction: column;
}

.step-indicator--horizontal .step-label {
  position: absolute;
  top: 34px;
  left: 50%;
  transform: translateX(-50%);
  text-align: center;
  white-space: nowrap;
}

.step-title {
  font-size: 13px;
  font-weight: 500;
  color: #4B5563;
  line-height: 1.3;
}

.step-item--active .step-title {
  color: #1F2937;
  font-weight: 600;
}

.step-desc {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}

@keyframes pulse-glow {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(42, 107, 255, 0.4);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(42, 107, 255, 0);
  }
}
</style>
