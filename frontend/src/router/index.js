import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },

  // Admin management routes (admin/manager only)
  {
    path: '/admin', component: () => import('../views/AdminLayout.vue'), meta: { roles: ['admin', 'manager'] },
    children: [
      { path: '', redirect: '/admin/dashboard' },
      { path: 'dashboard', name: 'AdminDashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'shops', name: 'Shops', component: () => import('../views/Shops.vue') },
      { path: 'products', name: 'Products', component: () => import('../views/Products.vue') },
      { path: 'orders', name: 'Orders', component: () => import('../views/Orders.vue') },
      { path: 'tickets', name: 'Tickets', component: () => import('../views/Tickets.vue') },
      { path: 'tickets/:id', name: 'TicketDetail', component: () => import('../views/TicketDetail.vue') },
      { path: 'skill-groups', name: 'SkillGroups', component: () => import('../views/SkillGroups.vue') },
      { path: 'categories', name: 'Categories', component: () => import('../views/Categories.vue') },
      { path: 'recommendations', name: 'Recommendations', component: () => import('../views/Recommendations.vue') },
      { path: 'ai-config', name: 'AIConfig', component: () => import('../views/AIConfig.vue') },
      { path: 'knowledge', name: 'AdminKnowledge', component: () => import('../views/AdminKnowledge.vue') },
      { path: 'service-mode', name: 'ServiceModeConfig', component: () => import('../views/ServiceModeConfig.vue') },
    ],
  },

  { path: '/', redirect: '/admin/dashboard' },
  { path: '/dashboard', redirect: '/admin/dashboard' },
  { path: '/shops', redirect: '/admin/shops' },
  { path: '/products', redirect: '/admin/products' },
  { path: '/orders', redirect: '/admin/orders' },
  { path: '/tickets', redirect: '/admin/tickets' },
  { path: '/tickets/:id', redirect: to => `/admin/tickets/${to.params.id}` },
  { path: '/skill-groups', redirect: '/admin/skill-groups' },
  { path: '/categories', redirect: '/admin/categories' },
  { path: '/recommendations', redirect: '/admin/recommendations' },
  { path: '/ai-config', redirect: '/admin/ai-config' },
  { path: '/knowledge', redirect: '/admin/knowledge' },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  const userStr = localStorage.getItem('user')
  let user = null
  try { user = JSON.parse(userStr) } catch { /* */ }

  if (to.path === '/login') {
    if (token) return '/admin/dashboard'
    return true
  }

  if (!token) return '/login'

  // Admin portal: block non-admin/manager users
  const allowed = ['admin', 'manager']
  if (!allowed.includes(user?.role)) {
    return '/login'
  }

  return true
})

export default router
