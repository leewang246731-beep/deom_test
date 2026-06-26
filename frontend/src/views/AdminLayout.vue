<template>
  <el-container style="height:100vh">
    <el-aside width="220px" style="background:#1f2d3d">
      <div style="color:#fff;text-align:center;padding:20px 0;font-size:16px;font-weight:bold;cursor:pointer" @click="$router.push('/admin/dashboard')">
        智能托管 SaaS
      </div>
      <el-menu :default-active="activeMenu" router background-color="#1f2d3d" text-color="#bfcbd9" active-text-color="#409eff">
        <el-menu-item index="/admin/dashboard"><el-icon><DataAnalysis /></el-icon> 工作台</el-menu-item>
        <el-menu-item index="/admin/shops"><el-icon><OfficeBuilding /></el-icon> 商户管理</el-menu-item>
        <el-menu-item index="/admin/connectors"><el-icon><Connection /></el-icon> 平台连接器</el-menu-item>
        <el-menu-item index="/admin/audit-logs"><el-icon><WarningFilled /></el-icon> 审计日志</el-menu-item>
        <el-menu-item index="/admin/webhook-logs"><el-icon><Link /></el-icon> Webhook 监控</el-menu-item>
        <el-menu-item index="/admin/sla-policies"><el-icon><AlarmClock /></el-icon> SLA 策略</el-menu-item>
        <el-menu-item index="/admin/ticket-categories"><el-icon><FolderOpened /></el-icon> 工单分类</el-menu-item>
        <el-menu-item index="/admin/ai-config"><el-icon><Cpu /></el-icon> AI 配置</el-menu-item>
        <el-menu-item index="/admin/knowledge"><el-icon><Reading /></el-icon> 企业知识库</el-menu-item>
        <el-menu-item index="/admin/live-monitor"><el-icon><Monitor /></el-icon> 实时监控</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e4e7ed;background:#fff">
        <div style="display:flex;align-items:center;gap:8px">
          <el-button v-if="showBack" text @click="goBack"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
          <span style="font-size:14px;color:#606266">{{ pageTitle }}</span>
        </div>
        <div style="display:flex;align-items:center;gap:12px">
          <span style="color:#606266">{{ auth.platformUser?.display_name || auth.platformUser?.username || auth.user?.display_name || auth.user?.username }}（{{ auth.platformUser?.role || auth.user?.role }}）</span>
          <el-button type="danger" text @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main style="background:#f5f7fa;overflow-y:auto">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => {
  const parts = route.path.split('/').filter(Boolean)
  return '/' + parts.slice(0, 2).join('/')
})

const showBack = computed(() => route.path.split('/').filter(Boolean).length > 2)

const pageTitle = computed(() => {
  const titles = {
    '/admin/dashboard': '工作台', '/admin/shops': '商户管理',
    '/admin/connectors': '平台连接器',
    '/admin/audit-logs': '审计日志', '/admin/webhook-logs': 'Webhook 监控',
    '/admin/sla-policies': 'SLA 策略', '/admin/ticket-categories': '工单分类',
    '/admin/ai-config': 'AI 配置', '/admin/knowledge': '企业知识库',
    '/admin/live-monitor': '实时监控',
  }
  if (route.path.startsWith('/admin/tickets/')) return '工单详情'
  if (route.path.startsWith('/admin/products/')) return '商品详情'
  if (route.path.startsWith('/admin/orders/')) return '订单详情'
  return titles[route.path] || ''
})

function goBack() {
  if (window.history.length > 2) { router.back() }
  else { router.push('/admin/dashboard') }
}

function handleLogout() {
  auth.logoutPlatform()
  router.replace('/login')
}
</script>
