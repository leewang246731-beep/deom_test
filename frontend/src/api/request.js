import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api/v1', timeout: 30000 })

let _refreshing = false  // 防止并发刷新

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('platform_token') || localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`

  // 平台端：注入选中商户 ID
  const mid = localStorage.getItem('active_merchant_id')
  if (mid && localStorage.getItem('platform_token')) {
    config.headers['X-Merchant-Id'] = mid
  }

  return config
})

http.interceptors.response.use(
  (res) => res.data,
  async (err) => {
    // 网络超时或服务器无响应
    if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
      ElMessage.warning('请求超时，请检查网络后重试')
      return Promise.reject(err)
    }
    // 服务器无响应 (502/503/504) 或网络断开
    if (!err.response) {
      ElMessage.error('服务器无响应，请检查网络连接后重试')
      return Promise.reject(err)
    }
    const detail = err.response?.data?.detail
    const msg = typeof detail === 'object'
      ? (detail.msg || detail.message || JSON.stringify(detail))
      : (detail || '请求失败')
    const status = err.response?.status

    if (status === 401) {
      // 尝试用 refresh_token 刷新（仅商户 token，非平台 token）
      const refreshToken = localStorage.getItem('refresh_token')
      const isLoginPage = window.location.hash === '#/login' || window.location.pathname === '/login'
      if (refreshToken && !_refreshing && !isLoginPage) {
        _refreshing = true
        try {
          const refreshRes = await axios.post('/api/v1/auth/refresh', { refresh_token: refreshToken })
          const newToken = refreshRes.data?.data?.access_token
          if (newToken) {
            localStorage.setItem('token', newToken)
            err.config.headers.Authorization = `Bearer ${newToken}`
            _refreshing = false
            return http(err.config)  // 用新 token 重试原请求
          }
        } catch { /* refresh failed */ }
        _refreshing = false
      }

      // 刷新失败或不可用 → 清除并跳转
      if (!isLoginPage) {
        ElMessage.error('登录已过期，请重新登录')
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        localStorage.removeItem('refresh_token')
        localStorage.removeItem('platform_token')
        localStorage.removeItem('platform_user')
        window.location.hash = '#/login'
      }
    } else if (status === 400) {
      ElMessage.warning(msg)
    } else if (status === 403) {
      ElMessage.warning(msg || '权限不足')
    } else if (status === 404) {
      // 资源不存在 — 不弹窗，由组件自行处理
    } else if (status === 409) {
      ElMessage.warning(msg)
    } else if (status >= 500) {
      ElMessage.error(`服务器错误: ${msg}`)
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(err)
  },
)

export default http
