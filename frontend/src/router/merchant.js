import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },

  // Merchant dashboard
  {
    path: '/merchant',
    component: () => import('../views/MerchantLayout.vue'),
    meta: { roles: ['admin', 'manager'] },
    children: [
      { path: '', redirect: '/merchant/dashboard' },
      { path: 'dashboard', name: 'MerchantDashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'products', name: 'MerchantProducts', component: () => import('../views/Products.vue') },
      { path: 'orders', name: 'MerchantOrders', component: () => import('../views/Orders.vue') },
      { path: 'conversations', name: 'MerchantConversations', component: () => import('../views/Service.vue') },
      { path: 'tickets', name: 'MerchantTickets', component: () => import('../views/Tickets.vue') },
      { path: 'tickets/:id', name: 'MerchantTicketDetail', component: () => import('../views/TicketDetail.vue') },
      { path: 'recommendations', name: 'MerchantRecommendations', component: () => import('../views/Recommendations.vue') },
      { path: 'service-mode', name: 'MerchantServiceMode', component: () => import('../views/ServiceModeConfig.vue') },
      { path: 'users', name: 'MerchantUsers', component: () => import('../views/Users.vue') },
      { path: 'auto-reply-logs', name: 'MerchantAutoReplyLogs', component: () => import('../views/AutoReplyLogs.vue') },
      { path: 'shops', name: 'MerchantShops', component: () => import('../views/Shops.vue') },
      { path: 'live-monitor', name: 'MerchantLiveMonitor', component: () => import('../views/LiveMonitor.vue') },
      { path: 'connectors', name: 'MerchantConnectors', component: () => import('../views/Connectors.vue') },
      { path: 'buyer-profiles', name: 'MerchantBuyerProfiles', component: () => import('../views/BuyerProfiles.vue') },
    ],
  },

  { path: '/', redirect: '/merchant/dashboard' },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  // 商户工作台仅认商户 token（拒绝平台 token）
  const token = localStorage.getItem('token')
  const userStr = localStorage.getItem('user')
  let user = null
  try { user = JSON.parse(userStr) } catch { /* */ }

  if (to.path === '/login') {
    if (token) return '/merchant/dashboard'
    return true
  }

  if (!token) return '/login'

  // 商户工作台拒绝客服角色
  if (user && user.role === 'service') {
    return '/login'
  }

  return true
})

export default router
