import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api/v1', timeout: 30000 })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('platform_token') || localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (res) => res.data,
  (err) => {
    // 网络超时或服务器无响应
    if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
      ElMessage.warning('请求超时，请检查网络后重试')
      return Promise.reject(err)
    }
    // 服务器无响应 (502/503/504)
    if (!err.response) {
      ElMessage.error('服务器无响应，请稍后重试')
      return Promise.reject(err)
    }
    const detail = err.response?.data?.detail
    const msg = typeof detail === 'object' ? detail.msg : (detail || '请求失败')
    if (err.response?.status === 401) {
      // 仅当不在登录页时清除 token 并跳转
      if (window.location.hash !== '#/login' && window.location.pathname !== '/login') {
        ElMessage.error('登录已过期，请重新登录')
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        localStorage.removeItem('platform_token')
        localStorage.removeItem('platform_user')
        window.location.hash = '#/login'
      }
    } else if (err.response?.status === 403) {
      // 403 静默处理 — 组件层面通过 .catch() 自行处理降级
      // 避免平台账号访问商户接口时弹出无关警告
    } else if (err.response?.status >= 500) {
      ElMessage.error(`服务器错误 (${err.response.status}): ${msg}`)
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(err)
  },
)

export default http
