import { createRouter, createWebHashHistory } from 'vue-router'
const routes = [
  { path: '/login', name:'Login', component:()=>import('../views/Login.vue'), meta:{public:true} },
  { path: '/', component:()=>import('../views/Layout.vue'), children:[
      { path:'', redirect:'/dashboard' },
      { path:'dashboard', name:'Dashboard', component:()=>import('../views/Dashboard.vue') },
      { path:'orders', name:'Orders', component:()=>import('../views/Orders.vue') },
      { path:'after-sales', name:'AfterSales', component:()=>import('../views/AfterSales.vue') },
      { path:'messages', name:'Messages', component:()=>import('../views/Messages.vue') },
      { path:'wallets', name:'Wallets', component:()=>import('../views/Wallets.vue') },
      { path:'settings', name:'Settings', component:()=>import('../views/Settings.vue') },
    ]},
]
const router = createRouter({ history: createWebHashHistory(), routes })
router.beforeEach(t => { if(!t.meta.public&&!localStorage.getItem('vmall_admin_token')) return '/login' })
export default router
