import { createRouter, createWebHashHistory } from 'vue-router'
const routes = [
  { path: '/login', name:'Login', component:()=>import('../views/Login.vue'), meta:{public:true} },
  { path: '/', redirect:'/home' },
  { path: '/home', name:'Home', component:()=>import('../views/Home.vue') },
  { path: '/product/:id', name:'ProductDetail', component:()=>import('../views/ProductDetail.vue') },
  { path: '/orders', name:'MyOrders', component:()=>import('../views/MyOrders.vue') },
  { path: '/profile', name:'Profile', component:()=>import('../views/Profile.vue') },
  { path: '/chat/:id', name:'Chat', component:()=>import('../views/Chat.vue') },
  { path: '/pay/:token', name:'PayConfirm', component:()=>import('../views/Pay.vue'), meta:{public:true} },
]
const router = createRouter({ history: createWebHashHistory(), routes })
router.beforeEach(t => { if(!t.meta.public&&!localStorage.getItem('vmall_token')) return '/login' })
export default router
