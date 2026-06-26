/* ============================================================
   useProgress — Smooth Progress Animation
   进度可视化：RAF 插值驱动
   ============================================================ */

import { ref, watch } from 'vue'

/**
 * Ease-out cubic: decelerating to zero
 */
export function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3)
}

/**
 * Linear interpolation between two numbers
 */
function lerp(a, b, t) {
  return a + (b - a) * t
}

/**
 * Animate a value from `from` to `to` over `duration` ms using RAF.
 * Returns a ref that updates each frame.
 */
export function animateValue(from, to, duration = 600, easingFn = easeOutCubic) {
  const displayValue = ref(from)
  let rafId = null
  const startTime = performance.now()

  function step(now) {
    const elapsed = now - startTime
    const progress = Math.min(elapsed / duration, 1.0)
    const eased = easingFn(progress)
    displayValue.value = lerp(from, to, eased)

    if (progress < 1.0) {
      rafId = requestAnimationFrame(step)
    }
  }

  rafId = requestAnimationFrame(step)

  return {
    displayValue,
    cancel: () => {
      if (rafId) cancelAnimationFrame(rafId)
    },
  }
}

/**
 * Progress Bar — animates smoothly to target percentage
 */
export function useProgressBar(initialValue = 0) {
  const target = ref(initialValue)
  const displayValue = ref(initialValue)
  let animation = null

  function setValue(newTarget, duration = 600) {
    target.value = Math.max(0, Math.min(100, newTarget))
    const from = displayValue.value
    const to = target.value
    if (animation) animation.cancel()
    animation = animateValue(from, to, duration)
    // Sync displayValue from the animation
    const syncRaf = () => {
      displayValue.value = animation.displayValue.value
      if (displayValue.value !== to) {
        requestAnimationFrame(syncRaf)
      }
    }
    syncRaf()
  }

  return { target, displayValue, setValue }
}

/**
 * Progress Ring — animates smoothly to target, returns SVG parameters
 */
export function useProgressRing(initialValue = 0, radius = 36) {
  const target = ref(initialValue)
  const displayValue = ref(initialValue)
  const circumference = 2 * Math.PI * radius
  let animation = null

  function setValue(newTarget, duration = 800) {
    target.value = Math.max(0, Math.min(100, newTarget))
    const from = displayValue.value
    const to = target.value
    if (animation) animation.cancel()
    animation = animateValue(from, to, duration)
    const syncRaf = () => {
      displayValue.value = animation.displayValue.value
      if (displayValue.value !== to) {
        requestAnimationFrame(syncRaf)
      }
    }
    syncRaf()
  }

  const offset = ref(circumference)
  watch(displayValue, (val) => {
    offset.value = circumference - (val / 100) * circumference
  })

  return { target, displayValue, circumference, offset, setValue }
}

/**
 * Step Indicator — reactive step states
 */
export function useStepIndicator(totalSteps, initialCurrent = 0) {
  const current = ref(initialCurrent)
  const steps = ref([])

  function buildSteps() {
    const result = []
    for (let i = 0; i < totalSteps; i++) {
      let status = 'pending'
      if (i < current.value) status = 'completed'
      else if (i === current.value) status = 'active'
      result.push({
        index: i,
        status,
        pulse: i === current.value, // pulse animation only on active
      })
    }
    steps.value = result
  }

  function setCurrent(stepIndex) {
    current.value = Math.max(0, Math.min(totalSteps - 1, stepIndex))
    buildSteps()
  }

  function next() {
    if (current.value < totalSteps - 1) {
      current.value++
      buildSteps()
    }
  }

  function prev() {
    if (current.value > 0) {
      current.value--
      buildSteps()
    }
  }

  buildSteps()

  return { current, steps, setCurrent, next, prev }
}
