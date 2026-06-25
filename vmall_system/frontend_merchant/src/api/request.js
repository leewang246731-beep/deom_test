import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api/v1', timeout: 15000 })

http.interceptors.request.use(c => {
  const t = localStorage.getItem('merchant_token')
  if (t) c.headers.Authorization = `Bearer ${t}`
  return c
})

http.interceptors.response.use(
  r => r.data,
  e => {
    const detail = e.response?.data?.detail
    const msg = typeof detail === 'object' ? (detail.msg || '请求失败') : (detail || '请求失败')
    if (e.response?.status === 401) {
      ElMessage.error('登录已过期，请重新登录')
      localStorage.removeItem('merchant_token')
      localStorage.removeItem('merchant_user')
      location.hash = '#/login'
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(e)
  },
)

export default http
