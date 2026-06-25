import http from './request'

// ---- auth ----
export const merchantLogin = (username, password) => http.post('/merchant/auth/login', { username, password })

// ---- dashboard ----
export const getDashboard = () => http.get('/merchant/dashboard')

// ---- products ----
export const getProducts = (params) => http.get('/merchant/products', { params })
export const getProduct = (id) => http.get(`/merchant/products/${id}`)
export const createProduct = (data) => http.post('/merchant/products', data)
export const updateProduct = (id, data) => http.put(`/merchant/products/${id}`, data)
export const deleteProduct = (id) => http.delete(`/merchant/products/${id}`)

// ---- orders ----
export const getOrders = (params) => http.get('/merchant/orders', { params })
export const getOrder = (id) => http.get(`/merchant/orders/${id}`)
export const shipOrder = (id, data) => http.post(`/merchant/orders/${id}/ship`, data)

// ---- conversations ----
export const getConversations = (params) => http.get('/merchant/conversations', { params })
export const getConvMessages = (convId) => http.get(`/merchant/conversations/${convId}/messages`)
export const sendMessage = (convId, data) => http.post(`/merchant/conversations/${convId}/messages`, data)

// ---- settings ----
export const getSettings = () => http.get('/merchant/settings')
export const updateSettings = (data) => http.put('/merchant/settings', data)

// ---- binding ----
export const applyBinding = (data) => http.post('/merchant/binding/apply', data)
export const confirmBinding = (data) => http.post('/merchant/binding/confirm', data)
export const getBindingStatus = () => http.get('/merchant/binding/status')
export const unbindSaaS = () => http.delete('/merchant/binding')
