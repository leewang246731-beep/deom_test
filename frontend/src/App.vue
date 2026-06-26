<template>
  <div>
    <div v-if="hasError" style="padding:40px;color:#e74c3c;font-family:monospace;white-space:pre-wrap;font-size:14px">
      <h2>App Error</h2>
      <p>{{ errorMessage }}</p>
      <pre>{{ errorStack }}</pre>
    </div>
    <router-view v-else />
  </div>
</template>

<script setup>
import { ref, onErrorCaptured } from 'vue'
const hasError = ref(false)
const errorMessage = ref('')
const errorStack = ref('')

onErrorCaptured((err, instance, info) => {
  hasError.value = true
  errorMessage.value = String(err)
  errorStack.value = err?.stack || info || ''
  console.error('[App error]', err, info)
  return false
})
</script>
