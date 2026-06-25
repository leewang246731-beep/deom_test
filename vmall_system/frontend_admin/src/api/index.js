import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api/v1', timeout: 15000 })

http.interceptors.request.use(c => {
  const t = localStorage.getItem('admin_token')
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
      localStorage.removeItem('admin_token')
      localStorage.removeItem('admin_user')
      window.location.hash = '#/login'
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(e)
  }
)

// auth
export const login = (u, p) => http.post('/admin/auth/login', { username: u, password: p })

// dashboard
export const getDashboard = () => http.get('/admin/dashboard')

// orders
export const getOrders = (p) => http.get('/admin/orders', { params: p })
export const getOrder = (id) => http.get(`/admin/orders/${id}`)
export const shipOrder = (id, d) => http.post(`/admin/orders/${id}/ship`, d)

// after-sales
export const getAfterSales = (p) => http.get('/admin/after-sales', { params: p })
export const reviewAfterSale = (id, d) => http.post(`/admin/after-sales/${id}/review`, d)
export const confirmReceive = (id) => http.post(`/admin/after-sales/${id}/confirm-receive`)

// conversations
export const getConvs = (p) => http.get('/admin/conversations', { params: p })
export const getConvMsgs = (id) => http.get(`/admin/conversations/${id}/messages`)
export const replyConv = (id, d) => http.post(`/admin/conversations/${id}/messages`, d)

// wallets
export const getWallets = (p) => http.get('/admin/wallets', { params: p })
export const getWalletDetail = (buyerId) => http.get(`/admin/wallets/${buyerId}`)
export const rechargeWallet = (buyerId, d) => http.post(`/admin/wallets/${buyerId}/recharge`, d)
export const getWalletTx = (buyerId, p) => http.get(`/admin/wallets/${buyerId}/transactions`, { params: p })

// settings
export const getSettings = () => http.get('/admin/settings')
export const updateSettings = (d) => http.put('/admin/settings', d)

// logistics
export const getLogistics = (orderId) => http.get(`/admin/logistics/${orderId}`)
export const shipLogistics = (orderId, d) => http.post(`/admin/logistics/${orderId}/ship`, d)
export const advanceLogistics = (id) => http.post(`/admin/logistics/${id}/advance`)
export const exceptionLogistics = (id, d) => http.post(`/admin/logistics/${id}/exception`, d)
export const resolveLogistics = (id) => http.post(`/admin/logistics/${id}/resolve`)
