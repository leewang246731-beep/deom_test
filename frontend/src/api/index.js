import http from './request'

// ---- auth ----
export const login = (username, password) => http.post('/auth/login', { username, password })

// ---- shops ----
export const getShops = () => http.get('/shops')
export const bindShop = (data) => http.post('/shops', data)
export const unbindShop = (id) => http.delete(`/shops/${id}`)
export const syncShop = (id) => http.post(`/shops/${id}/sync`)

// ---- products ----
export const getProducts = (params) => http.get('/products', { params })
export const searchProducts = (q, shopId) => http.get('/products/search', { params: { q, shop_id: shopId } })
export const syncProducts = (shopId) => http.post(`/products/sync/${shopId}`)

// ---- orders ----
export const getOrders = (params) => http.get('/orders', { params })
export const getPendingPayment = () => http.get('/orders/pending-payment')
export const refundOrder = (id) => http.post(`/orders/${id}/refund`)
export const remindPayment = (shopId, limit, offset) => http.post('/orders/pending-payment/remind', { shop_id: shopId, limit, offset })

// ---- conversations ----
export const getConversations = (params) => http.get('/conversations', { params })
export const getConversation = (id) => http.get(`/conversations/${id}`)
export const assignConversation = (id) => http.post(`/conversations/${id}/assign`)
export const closeConversation = (id) => http.post(`/conversations/${id}/close`)
export const sendConversationMessage = (id, data) => http.post(`/conversations/${id}/messages`, data)

// ---- ai ----
export const aiSuggest = (data) => http.post('/ai/suggest', data)
export const aiSuggestLog = (data) => http.post('/ai/suggest/log', data)
export const aiCampaignRemind = (shopId, limit, offset) => http.post('/ai/campaign/pending-payment', { shop_id: shopId, limit, offset })
export const getAIStyles = () => http.get('/ai/styles')
export const createAIStyle = (data) => http.post('/ai/styles', data)
export const updateAIStyle = (id, data) => http.put(`/ai/styles/${id}`, data)
export const deleteAIStyle = (id) => http.delete(`/ai/styles/${id}`)
export const setDefaultStyle = (id) => http.post(`/ai/styles/${id}/default`)

// ---- dashboard ----
export const getMetrics = () => http.get('/dashboard/metrics')
export const getOrderTrend = (range) => http.get('/dashboard/order-trend', { params: { range } })
export const getServiceStats = () => http.get('/dashboard/service-stats')

// ---- recommendations ----
export const getSimilarProducts = (data) => http.post('/recommendations/similar', data)
export const getBuyerRecommendations = (data) => http.post('/recommendations/for-buyer', data)
export const getHotProducts = (params) => http.get('/recommendations/hot', { params })
export const getRecommendationRules = () => http.get('/recommendations/rules')
export const createRecommendationRule = (data) => http.post('/recommendations/rules', data)
export const deleteRecommendationRule = (id) => http.delete(`/recommendations/rules/${id}`)
export const rebuildCoPurchase = () => http.post('/recommendations/rebuild-co-purchase')

// ---- service mode ----
export const getServiceModeConfig = () => http.get('/service-mode/config')
export const updateServiceModeConfig = (data) => http.put('/service-mode/config', data)
export const setConvMode = (id, mode) => http.post(`/service-mode/conversations/${id}/mode`, { mode })
export const takeoverConv = (id) => http.post(`/service-mode/conversations/${id}/takeover`)
export const getAutoReplyLogs = (params) => http.get('/service-mode/auto-reply-logs', { params })
export const getAutoReplyStats = () => http.get('/service-mode/stats')
export const getCategories = () => http.get('/categories')
export const createCategory = (data) => http.post('/categories', data)
export const updateCategory = (id, data) => http.put(`/categories/${id}`, data)
export const deleteCategory = (id) => http.delete(`/categories/${id}`)

// ---- tickets ----
export const getTickets = (params) => http.get('/tickets', { params })
export const getTicket = (id) => http.get(`/tickets/${id}`)
export const createTicket = (data) => http.post('/tickets', data)
export const updateTicket = (id, data) => http.put(`/tickets/${id}`, data)
export const updateTicketStatus = (id, data) => http.post(`/tickets/${id}/status`, data)
export const assignTicket = (id, toUserId) => http.post(`/tickets/${id}/assign`, { to_user_id: toUserId })
export const claimTicket = (id) => http.post(`/tickets/${id}/claim`)
export const getTicketComments = (id) => http.get(`/tickets/${id}/comments`)
export const addTicketComment = (id, data) => http.post(`/tickets/${id}/comments`, data)
export const autoClassifyTicket = (id) => http.post(`/tickets/${id}/auto-classify`)
export const autoSummarizeTicket = (id) => http.post(`/tickets/${id}/auto-summarize`)
export const ticketAISuggest = (id) => http.post(`/tickets/${id}/ai-suggest`)
export const getTicketCategories = () => http.get('/tickets/categories')
export const preClassify = (data) => http.post('/tickets/auto-classify', data)

// ---- skill groups ----
export const getSkillGroups = () => http.get('/skill-groups')
export const createSkillGroup = (data) => http.post('/skill-groups', data)
export const updateSkillGroup = (id, data) => http.put(`/skill-groups/${id}`, data)
export const deleteSkillGroup = (id) => http.delete(`/skill-groups/${id}`)
export const addSkillMember = (gid, data) => http.post(`/skill-groups/${gid}/members`, data)
export const removeSkillMember = (gid, uid) => http.delete(`/skill-groups/${gid}/members/${uid}`)

// ---- SLA ----
export const getSLAPolicies = () => http.get('/sla/policies')
export const createSLAPolicy = (data) => http.post('/sla/policies', data)
export const updateSLAPolicy = (id, data) => http.put(`/sla/policies/${id}`, data)
export const deleteSLAPolicy = (id) => http.delete(`/sla/policies/${id}`)

// ---- dashboard tickets ----
export const getTicketStats = () => http.get('/dashboard/ticket-stats')
export const getTicketTrend = (range) => http.get('/dashboard/ticket-trend', { params: { range } })

// ---- knowledge base ----
export const kbAsk = (data) => http.post('/kb/ask', data)
export const kbGetDocuments = (params) => http.get('/kb/documents', { params })
export const kbCreateDocument = (data) => http.post('/kb/documents', data)
export const kbDeleteDocument = (id) => http.delete(`/kb/documents/${id}`)
export const kbGetConversations = (params) => http.get('/kb/conversations', { params })
export const kbCreateConversation = (data) => http.post('/kb/conversations', data)
export const kbGetMessages = (convId) => http.get(`/kb/conversations/${convId}/messages`)
export const kbGetStats = () => http.get('/kb/stats')
export const kbSyncShop = (data) => http.post('/kb/sync', data)
