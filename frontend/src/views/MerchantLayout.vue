<template>
  <el-container style="height:100vh">
    <el-aside width="220px" style="background:#1f2d3d">
      <div style="color:#fff;text-align:center;padding:20px 0;font-size:16px;font-weight:bold">商户工作台</div>
      <el-menu :default-active="activeMenu" router background-color="#1f2d3d" text-color="#bfcbd9" active-text-color="#409eff">
        <el-menu-item index="/merchant/dashboard"><el-icon><DataAnalysis/></el-icon> 工作台</el-menu-item>
        <el-menu-item index="/merchant/shops"><el-icon><Shop/></el-icon> 店铺管理</el-menu-item>
        <el-menu-item index="/merchant/products"><el-icon><Goods/></el-icon> 我的商品</el-menu-item>
        <el-menu-item index="/merchant/orders"><el-icon><Document/></el-icon> 订单管理</el-menu-item>
        <el-menu-item index="/merchant/conversations"><el-icon><ChatDotRound/></el-icon> 会话管理</el-menu-item>
        <el-menu-item index="/merchant/tickets"><el-icon><Tickets/></el-icon> 工单管理</el-menu-item>
        <el-menu-item index="/merchant/recommendations"><el-icon><MagicStick/></el-icon> AI推荐</el-menu-item>
        <el-menu-item index="/merchant/service-mode"><el-icon><Setting/></el-icon> 客服模式</el-menu-item>
        <el-menu-item index="/merchant/users"><el-icon><User/></el-icon> 用户管理</el-menu-item>
        <el-menu-item index="/merchant/auto-reply-logs"><el-icon><Notebook/></el-icon> AI 话术日志</el-menu-item>
        <el-menu-item index="/merchant/live-monitor"><el-icon><Monitor/></el-icon> 实时监控</el-menu-item>
        <el-menu-item index="/merchant/connectors"><el-icon><Connection/></el-icon> 平台连接器</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e4e7ed;background:#fff">
        <div style="display:flex;align-items:center;gap:8px">
          <el-button v-if="showBack" text @click="goBack"><el-icon><ArrowLeft/></el-icon> 返回</el-button>
          <span style="font-size:14px;color:#606266">{{ pageTitle }}</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <span style="color:#606266">{{auth.user?.display_name || auth.user?.username}}</span>
          <el-button type="danger" text @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main style="background:#f5f7fa">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => '/' + route.path.split('/').filter(Boolean).slice(0, 2).join('/'))

const showBack = computed(() => route.path !== '/merchant/dashboard')

const pageTitle = computed(() => {
  const map = {
    '/merchant/dashboard': '工作台',
    '/merchant/shops': '店铺管理',
    '/merchant/products': '我的商品',
    '/merchant/orders': '订单管理',
    '/merchant/conversations': '会话管理',
    '/merchant/tickets': '工单管理',
    '/merchant/recommendations': 'AI推荐',
    '/merchant/service-mode': '客服模式',
    '/merchant/users': '用户管理',
    '/merchant/auto-reply-logs': 'AI 话术日志',
    '/merchant/live-monitor': '实时监控',
  }
  if (route.path.startsWith('/merchant/tickets/')) return '工单详情'
  return map[route.path] || ''
})

function goBack() {
  if (window.history.length > 2) router.back()
  else router.push('/merchant/dashboard')
}

function handleLogout() {
  auth.logout()
  router.replace('/login')
}
</script>
