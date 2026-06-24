import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },
  {
    path: '/', component: () => import('../views/Layout.vue'), children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue') },
      { path: 'shops', name: 'Shops', component: () => import('../views/Shops.vue') },
      { path: 'products', name: 'Products', component: () => import('../views/Products.vue') },
      { path: 'orders', name: 'Orders', component: () => import('../views/Orders.vue') },
      { path: 'tickets', name: 'Tickets', component: () => import('../views/Tickets.vue') },
      { path: 'tickets/:id', name: 'TicketDetail', component: () => import('../views/TicketDetail.vue'), meta: { hideMenu: true } },
      { path: 'service', name: 'Service', component: () => import('../views/Service.vue') },
      { path: 'skill-groups', name: 'SkillGroups', component: () => import('../views/SkillGroups.vue') },
      { path: 'categories', name: 'Categories', component: () => import('../views/Categories.vue') },
      { path: 'recommendations', name: 'Recommendations', component: () => import('../views/Recommendations.vue') },
      { path: 'ai-config', name: 'AIConfig', component: () => import('../views/AIConfig.vue') },
    ],
  },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (!to.meta.public && !token) return '/login'
  if (to.path === '/login' && token) return '/dashboard'
})

export default router
