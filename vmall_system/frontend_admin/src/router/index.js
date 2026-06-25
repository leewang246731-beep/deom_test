import { createRouter, createWebHashHistory } from 'vue-router'
const routes = [
  { path: '/login', name:'Login', component:()=>import('../views/Login.vue'), meta:{public:true} },
  { path: '/', component:()=>import('../views/Layout.vue'), children:[
      { path:'', redirect:'/dashboard' },
      { path:'dashboard', name:'Dashboard', component:()=>import('../views/Dashboard.vue') },
      { path:'orders', name:'Orders', component:()=>import('../views/Orders.vue') },
      { path:'orders/:id', name:'OrderDetail', component:()=>import('../views/OrderDetail.vue') },
      { path:'after-sales', name:'AfterSales', component:()=>import('../views/AfterSales.vue') },
      { path:'conversations', name:'Conversations', component:()=>import('../views/Conversations.vue') },
      { path:'conversations/:id', name:'ConversationDetail', component:()=>import('../views/ConversationDetail.vue') },
      { path:'logistics', name:'Logistics', component:()=>import('../views/Logistics.vue') },
      { path:'wallets', name:'Wallets', component:()=>import('../views/Wallets.vue') },
      { path:'settings', name:'Settings', component:()=>import('../views/Settings.vue') },
    ]},
]
const router = createRouter({ history: createWebHashHistory(), routes })
router.beforeEach(t => { if(!t.meta.public&&!localStorage.getItem('admin_token')) return '/login' })
export default router
