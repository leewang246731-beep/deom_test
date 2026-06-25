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
    ],
  },

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
