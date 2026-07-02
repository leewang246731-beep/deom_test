import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'Login', component: () => import('../views/Login.vue'), meta: { public: true } },

  // Customer service workspace
  {
    path: '/service', component: () => import('../views/ServiceLayout.vue'), meta: { roles: ['admin', 'manager', 'service'] },
    children: [
      { path: '', redirect: '/service/workbench' },
      { path: 'workbench', name: 'ServiceWorkbench', component: () => import('../views/Service.vue') },
      { path: 'knowledge', name: 'ServiceKnowledge', component: () => import('../views/ServiceKnowledge.vue') },
      { path: 'tickets/:id', name: 'ServiceTicketDetail', component: () => import('../views/TicketDetail.vue') },
    ],
  },

  // 快捷路由：客服工作台内点击商品/工单链接不会白屏
  { path: '/tickets/:id', redirect: to => `/service/tickets/${to.params.id}` },
  { path: '/products/:id', redirect: () => '/service/workbench' },

  { path: '/', redirect: '/service/workbench' },
]

const router = createRouter({ history: createWebHashHistory(), routes })

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  const userStr = localStorage.getItem('user')
  let user = null
  try { user = JSON.parse(userStr) } catch { /* */ }

  if (to.path === '/login') {
    if (token) return '/service/workbench'
    return true
  }

  if (!token) return '/login'

  return true
})

export default router
