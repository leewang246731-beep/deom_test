/* ============================================================
   useMouseInteraction — Mouse Feedback Composables
   鼠标动态交互：光标光晕、波纹、卡片悬浮
   ============================================================ */

import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Cursor glow — follows mouse with throttle and delay
 */
export function useCursorGlow() {
  const cursorX = ref(-100)
  const cursorY = ref(-100)
  const isVisible = ref(false)
  let lastTime = 0
  let rafId = null

  function onMouseMove(e) {
    const now = performance.now()
    if (now - lastTime < 16) return // ~60fps throttle
    lastTime = now
    cursorX.value = e.clientX
    cursorY.value = e.clientY
    isVisible.value = true
  }

  function onMouseLeave() {
    isVisible.value = false
  }

  onMounted(() => {
    window.addEventListener('mousemove', onMouseMove, { passive: true })
    document.addEventListener('mouseleave', onMouseLeave, { passive: true })
  })

  onUnmounted(() => {
    window.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseleave', onMouseLeave)
    if (rafId) cancelAnimationFrame(rafId)
  })

  return { cursorX, cursorY, isVisible }
}

/**
 * Ripple effect on click within an element
 */
export function useRipple() {
  function createRipple(event, el) {
    if (!el) return
    // Ensure the container has relative positioning
    const style = getComputedStyle(el)
    if (style.position === 'static') {
      el.style.position = 'relative'
    }
    el.style.overflow = 'hidden'

    const ripple = document.createElement('span')
    const rect = el.getBoundingClientRect()
    const size = Math.max(rect.width, rect.height) * 2
    const x = event.clientX - rect.left - size / 2
    const y = event.clientY - rect.top - size / 2

    ripple.style.cssText = `
      position: absolute;
      width: ${size}px;
      height: ${size}px;
      left: ${x}px;
      top: ${y}px;
      border-radius: 50%;
      background: rgba(255, 255, 255, 0.4);
      transform: scale(0);
      pointer-events: none;
      animation: ripple-effect 0.4s ease-out forwards;
      z-index: 1;
    `
    ripple.className = 'ripple-element'
    el.appendChild(ripple)

    ripple.addEventListener('animationend', () => {
      ripple.remove()
    })
  }

  return { createRipple }
}

/**
 * Card hover effect — translateY + shadow
 */
export function useCardHover() {
  function apply(el) {
    if (!el) return
    el.style.transition = 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1)'

    function onEnter() {
      el.style.transform = 'translateY(-2px)'
      el.style.boxShadow = '0 8px 24px rgba(0, 0, 0, 0.10)'
    }

    function onLeave() {
      el.style.transform = 'translateY(0)'
      el.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.06)'
    }

    el.addEventListener('mouseenter', onEnter)
    el.addEventListener('mouseleave', onLeave)

    return () => {
      el.removeEventListener('mouseenter', onEnter)
      el.removeEventListener('mouseleave', onLeave)
    }
  }

  return { apply }
}

/**
 * Row hover — subtle background shift (for tables/lists)
 */
export function useRowHover() {
  function apply(el) {
    if (!el) return
    el.style.transition = 'background-color 0.2s cubic-bezier(0.4, 0, 0.2, 1)'

    const originalBg = el.style.backgroundColor || ''
    function onEnter() {
      el.style.backgroundColor = 'rgba(0, 0, 0, 0.025)'
    }
    function onLeave() {
      el.style.backgroundColor = originalBg
    }

    el.addEventListener('mouseenter', onEnter)
    el.addEventListener('mouseleave', onLeave)

    return () => {
      el.removeEventListener('mouseenter', onEnter)
      el.removeEventListener('mouseleave', onLeave)
    }
  }

  return { apply }
}
