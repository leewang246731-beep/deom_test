/**
 * useRequest — 统一数据请求层
 *
 * 替代手写 try/catch/loading/error 模式。
 * 用法:
 *   const { data, loading, error, execute } = useRequest(() => api.getProducts(params))
 *   // 或直接: const { data, loading } = useRequest(api.getProducts)
 *
 *   带防抖:  const { data, loading, run } = useRequest(searchApi, { debounce: 300 })
 *   提交模式: const { submit, loading } = useRequest(createApi, { action: '创建' })
 */
import { ref, type Ref, type UnwrapRef } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

// ===== 类型 =====
interface UseRequestOptions<TParams extends any[]> {
  /** 防抖延迟(ms)，默认 0 不防抖 */
  debounce?: number
  /** 操作名称，用于自动生成 Toast（如 '创建'→'创建成功'） */
  action?: string
  /** 成功提示（覆盖自动生成） */
  successMsg?: string
  /** 错误提示（覆盖拦截器） */
  errorMsg?: string
  /** 静默模式：不显示任何 Toast */
  silent?: boolean
  /** 删除确认（传入名称则弹出 ElMessageBox.confirm） */
  confirmDelete?: string
  /** 成功回调 */
  onSuccess?: (data: any) => void
  /** 错误回调 */
  onError?: (err: any) => void
  /** 初始数据 */
  initialData?: any
  /** 是否立即执行 */
  immediate?: boolean
  /** 最大重试次数 */
  maxRetries?: number
}

interface UseRequestReturn<TData, TParams extends any[]> {
  data: Ref<UnwrapRef<TData> | null>
  loading: Ref<boolean>
  error: Ref<string | null>
  execute: (...args: TParams) => Promise<TData | null>
  /** 提交模式：自动 Toast + 确认 */
  submit: (...args: TParams) => Promise<TData | null>
  /** 防抖执行 */
  run: (...args: TParams) => Promise<TData | null>
  /** 重置状态 */
  reset: () => void
}

// ===== 主函数 =====
export function useRequest<TData = any, TParams extends any[] = any[]>(
  fn: (...args: TParams) => Promise<TData>,
  options: UseRequestOptions<TParams> = {},
): UseRequestReturn<TData, TParams> {
  const {
    debounce = 0,
    action,
    successMsg,
    errorMsg,
    silent = false,
    confirmDelete,
    onSuccess,
    onError,
    initialData = null,
    maxRetries = 0,
  } = options

  const data = ref<TData | null>(initialData) as Ref<UnwrapRef<TData> | null>
  const loading = ref(false)
  const error = ref<string | null>(null)
  let debounceTimer: ReturnType<typeof setTimeout> | null = null
  let retryCount = 0

  async function _execute(args: TParams, isRetry = false): Promise<TData | null> {
    loading.value = true
    error.value = null
    try {
      const result = await fn(...args)
      data.value = result as UnwrapRef<TData>
      retryCount = 0

      if (!silent) {
        const msg = successMsg || (action ? `${action}成功` : '')
        if (msg) ElMessage.success(msg)
      }
      onSuccess?.(result)
      return result
    } catch (e: any) {
      error.value = e?.message || String(e)

      // 重试
      if (maxRetries > 0 && retryCount < maxRetries && !isRetry) {
        retryCount++
        return _execute(args, true)
      }

      if (!silent) {
        // 拦截器已显示通用错误，这里仅显示自定义错误
        if (errorMsg) ElMessage.error(errorMsg)
      }
      onError?.(e)
      return null
    } finally {
      loading.value = false
    }
  }

  /** 普通执行 */
  async function execute(...args: TParams): Promise<TData | null> {
    return _execute(args)
  }

  /** 提交模式：带删除确认 */
  async function submit(...args: TParams): Promise<TData | null> {
    if (confirmDelete) {
      try {
        await ElMessageBox.confirm(
          `确定${confirmDelete}吗？此操作不可恢复。`,
          '确认操作',
          { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' },
        )
      } catch {
        return null // 用户取消
      }
    }
    return _execute(args)
  }

  /** 防抖执行 */
  async function run(...args: TParams): Promise<TData | null> {
    if (debounce <= 0) return _execute(args)
    return new Promise((resolve) => {
      if (debounceTimer) clearTimeout(debounceTimer)
      debounceTimer = setTimeout(async () => {
        const result = await _execute(args)
        resolve(result)
      }, debounce)
    })
  }

  /** 重置状态 */
  function reset() {
    data.value = initialData as UnwrapRef<TData>
    loading.value = false
    error.value = null
    retryCount = 0
  }

  return { data, loading, error, execute, submit, run, reset }
}

// ===== 便捷工厂函数 =====

/** 列表加载（静默错误，由页面空状态展示） */
export function useLoad<TData = any, TParams extends any[] = any[]>(
  fn: (...args: TParams) => Promise<TData>,
  options?: UseRequestOptions<TParams>,
) {
  return useRequest<TData, TParams>(fn, { silent: true, ...options })
}

/** 提交操作（自动 Toast） */
export function useSubmit<TData = any, TParams extends any[] = any[]>(
  fn: (...args: TParams) => Promise<TData>,
  action: string,
  options?: UseRequestOptions<TParams>,
) {
  return useRequest<TData, TParams>(fn, { action, ...options })
}

/** 删除操作（自动确认弹窗 + Toast） */
export function useDelete<TData = any, TParams extends any[] = any[]>(
  fn: (...args: TParams) => Promise<TData>,
  itemName: string,
  options?: UseRequestOptions<TParams>,
) {
  return useRequest<TData, TParams>(fn, {
    confirmDelete: itemName,
    successMsg: `已删除${itemName}`,
    action: '删除',
    ...options,
  })
}
