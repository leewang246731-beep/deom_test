import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api/v1', timeout: 15000 })

http.interceptors.request.use(c => {
  const t = localStorage.getItem('vmall_token')
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
      localStorage.removeItem('vmall_token')
      localStorage.removeItem('vmall_user')
      window.location.hash = '#/login'
    } else {
      ElMessage.error(msg)
    }
    return Promise.reject(e)
  }
)

// auth
export const login = (u, p) => http.post('/consumer/auth/login', { username: u, password: p })

// products
export const getProducts = (p) => http.get('/consumer/products', { params: p })
export const getProduct = (id) => http.get(`/consumer/products/${id}`)

// orders
export const createOrder = (d) => http.post('/consumer/orders', d)
export const payOrder = (id) => http.post(`/consumer/orders/${id}/pay`)
export const getMyOrders = (p) => http.get('/consumer/orders', { params: p })
export const getOrder = (id) => http.get(`/consumer/orders/${id}`)

// after-sales
export const applyAfterSale = (d) => http.post('/consumer/after-sales', d)
export const getAfterSale = (id) => http.get(`/consumer/after-sales/${id}`)

// conversations
export const createConv = (d) => http.post('/consumer/conversations', d)
export const sendMsg = (id, d) => http.post(`/consumer/conversations/${id}/messages`, d)
export const getMsgs = (id) => http.get(`/consumer/conversations/${id}/messages`)

// profile & wallet
export const getProfile = () => http.get('/consumer/profile')
export const updateProfile = (d) => http.put('/consumer/profile', d)
export const getWallet = () => http.get('/consumer/wallet')
export const getWalletTransactions = (p) => http.get('/consumer/wallet/transactions', { params: p })
