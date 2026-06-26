/* ============================================================
   useParticleBackground — Canvas 2D Particle System
   动态粒子背景：隐喻数据流与信息网络
   ============================================================ */

import { ref, shallowRef, onUnmounted } from 'vue'

const DEFAULT_OPTIONS = {
  particleCount: 80,
  dotSizeMin: 2,
  dotSizeMax: 4,
  color: '26, 58, 92',       // #1A3A5C as RGB string
  opacity: 0.3,
  speed: 0.5,
  repulsionRadius: 80,
  connectionDistance: 120,
  lineOpacity: 0.08,
  lineWidth: 0.8,
}

export function useParticleBackground() {
  const canvasRef = shallowRef(null)
  const isRunning = ref(false)
  const isEnabled = ref(true)
  let rafId = null
  let particles = []
  let mouseX = -1000
  let mouseY = -1000
  let ctx = null
  let width = 0
  let height = 0
  let opts = { ...DEFAULT_OPTIONS }
  let resizeObserver = null

  function init(canvas, options) {
    if (!canvas) return
    canvasRef.value = canvas
    if (options) {
      opts = { ...DEFAULT_OPTIONS, ...options }
    }

    ctx = canvas.getContext('2d')
    resize()
    createParticles()

    resizeObserver = new ResizeObserver(() => resize())
    resizeObserver.observe(canvas)

    window.addEventListener('mousemove', onMouseMove, { passive: true })
    window.addEventListener('mouseleave', onMouseLeave, { passive: true })

    isRunning.value = true
    loop()
  }

  function destroy() {
    if (rafId) cancelAnimationFrame(rafId)
    rafId = null
    isRunning.value = false
    window.removeEventListener('mousemove', onMouseMove)
    window.removeEventListener('mouseleave', onMouseLeave)
    if (resizeObserver) {
      resizeObserver.disconnect()
      resizeObserver = null
    }
    particles = []
    ctx = null
    canvasRef.value = null
  }

  function toggle() {
    isEnabled.value = !isEnabled.value
    if (isEnabled.value) {
      loop()
    }
  }

  function setMousePosition(x, y) {
    mouseX = x
    mouseY = y
  }

  function resize() {
    const canvas = canvasRef.value
    if (!canvas) return
    const dpr = window.devicePixelRatio || 1
    width = window.innerWidth
    height = window.innerHeight
    canvas.width = width * dpr
    canvas.height = height * dpr
    canvas.style.width = width + 'px'
    canvas.style.height = height + 'px'
    if (ctx) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
  }

  function createParticles() {
    particles = []
    for (let i = 0; i < opts.particleCount; i++) {
      particles.push({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * opts.speed,
        vy: (Math.random() - 0.5) * opts.speed,
        radius: opts.dotSizeMin + Math.random() * (opts.dotSizeMax - opts.dotSizeMin),
      })
    }
  }

  function onMouseMove(e) {
    mouseX = e.clientX
    mouseY = e.clientY
  }

  function onMouseLeave() {
    mouseX = -1000
    mouseY = -1000
  }

  function drawParticle(p) {
    if (!ctx) return
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${opts.color}, ${opts.opacity})`
    ctx.fill()
  }

  function drawLine(p1, p2) {
    if (!ctx) return
    const dx = p1.x - p2.x
    const dy = p1.y - p2.y
    const dist = Math.sqrt(dx * dx + dy * dy)
    if (dist > opts.connectionDistance) return
    const alpha = opts.lineOpacity * (1 - dist / opts.connectionDistance)
    ctx.beginPath()
    ctx.moveTo(p1.x, p1.y)
    ctx.lineTo(p2.x, p2.y)
    ctx.strokeStyle = `rgba(${opts.color}, ${alpha})`
    ctx.lineWidth = opts.lineWidth
    ctx.stroke()
  }

  function updateParticle(p) {
    p.x += p.vx
    p.y += p.vy

    // Boundary wrap
    if (p.x < -10) p.x = width + 10
    if (p.x > width + 10) p.x = -10
    if (p.y < -10) p.y = height + 10
    if (p.y > height + 10) p.y = -10

    // Mouse repulsion
    if (mouseX > -500) {
      const dx = p.x - mouseX
      const dy = p.y - mouseY
      const dist = Math.sqrt(dx * dx + dy * dy)
      if (dist < opts.repulsionRadius && dist > 0) {
        const force = (opts.repulsionRadius - dist) / opts.repulsionRadius
        const angle = Math.atan2(dy, dx)
        p.vx += Math.cos(angle) * force * 0.3
        p.vy += Math.sin(angle) * force * 0.3
      }
    }

    // Damping
    p.vx *= 0.995
    p.vy *= 0.995

    // Speed clamp
    const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy)
    if (speed > opts.speed * 2) {
      p.vx = (p.vx / speed) * opts.speed * 2
      p.vy = (p.vy / speed) * opts.speed * 2
    }
  }

  function loop() {
    if (!isRunning.value || !ctx) return
    rafId = requestAnimationFrame(loop)

    if (!isEnabled.value) return

    ctx.clearRect(0, 0, width, height)

    // Draw connections first (behind dots)
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        drawLine(particles[i], particles[j])
      }
    }

    // Draw particles
    for (const p of particles) {
      updateParticle(p)
      drawParticle(p)
    }
  }

  onUnmounted(destroy)

  return {
    canvasRef,
    isRunning,
    isEnabled,
    init,
    destroy,
    toggle,
    setMousePosition,
  }
}
