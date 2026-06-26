/**
 * useRequest — JS compatibility wrapper (for existing .vue files)
 *
 * Thin wrapper around the pattern all pages already use.
 * Import: import { useRequest } from '../composables/useRequest'
 *
 * Usage (list loading):
 *   const { data, loading, execute } = useRequest(() => api.getXxx(params), [])
 *
 * Usage (submit):
 *   const { loading, execute } = useRequest(() => api.createXxx(data), null, { toast: '创建成功' })
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

export function useRequest(fn, initialData = null, opts = {}) {
  const data = ref(initialData)
  const loading = ref(false)
  const error = ref(null)

  async function execute(...args) {
    loading.value = true
    error.value = null
    try {
      const res = await fn(...args)
      data.value = res?.data ?? res
      if (opts.toast) ElMessage.success(opts.toast)
      if (opts.onSuccess) opts.onSuccess(res)
      return res
    } catch (e) {
      error.value = e
      if (opts.onError) opts.onError(e)
      // Reset data to initial on error
      if (Array.isArray(initialData)) data.value = []
      return null
    } finally {
      loading.value = false
    }
  }

  return { data, loading, error, execute }
}

/**
 * Pre-configured for list pages.
 * Usage: const { data: items, loading, execute: fetch } = useList(() => api.getXxx(params))
 */
export function useList(fn) {
  return useRequest(fn, [])
}

/**
 * Pre-configured for submit operations.
 * Usage: const { loading, execute: submit } = useSubmit(() => api.createXxx(form), '创建')
 */
export function useSubmit(fn, actionName = '提交') {
  return useRequest(fn, null, { toast: `${actionName}成功` })
}
