<template>
  <el-container style="height:100vh">
    <el-aside width="220px" style="background:#1f2d3d">
      <div style="color:#fff;text-align:center;padding:20px 0;font-size:16px;font-weight:bold;cursor:pointer" @click="$router.push('/admin/dashboard')">
        智能托管 SaaS
      </div>
      <el-menu :default-active="activeMenu" router background-color="#1f2d3d" text-color="#bfcbd9" active-text-color="#409eff">
        <el-menu-item index="/admin/dashboard"><el-icon><DataAnalysis /></el-icon> 工作台</el-menu-item>
        <el-menu-item index="/admin/shops"><el-icon><Shop /></el-icon> 店铺管理</el-menu-item>
        <el-menu-item index="/admin/products"><el-icon><Goods /></el-icon> 商品库</el-menu-item>
        <el-menu-item index="/admin/orders"><el-icon><Document /></el-icon> 订单中心</el-menu-item>
        <el-menu-item index="/admin/tickets"><el-icon><Tickets /></el-icon> 工单管理</el-menu-item>
        <el-menu-item index="/admin/skill-groups"><el-icon><UserFilled /></el-icon> 技能组</el-menu-item>
        <el-menu-item index="/admin/categories"><el-icon><Grid /></el-icon> 分类管理</el-menu-item>
        <el-menu-item index="/admin/recommendations"><el-icon><MagicStick /></el-icon> 推荐管理</el-menu-item>
        <el-menu-item index="/admin/ai-config"><el-icon><Cpu /></el-icon> AI 配置</el-menu-item>
        <el-menu-item index="/admin/knowledge"><el-icon><Reading /></el-icon> 企业知识库</el-menu-item>
        <el-menu-item index="/admin/service-mode"><el-icon><Setting /></el-icon> 客服模式</el-menu-item>
        <el-menu-item index="/admin/users"><el-icon><User /></el-icon> 用户管理</el-menu-item>
        <el-menu-item index="/admin/sla-policies"><el-icon><AlarmClock /></el-icon> SLA 策略</el-menu-item>
        <el-menu-item index="/admin/auto-reply-logs"><el-icon><Notebook /></el-icon> AI 话术日志</el-menu-item>
        <el-menu-item index="/admin/ticket-categories"><el-icon><FolderOpened /></el-icon> 工单分类</el-menu-item>
        <el-menu-item index="/admin/webhook-logs"><el-icon><Connection /></el-icon> Webhook 监控</el-menu-item>
        <el-menu-item index="/admin/audit-logs"><el-icon><WarningFilled /></el-icon> 审计日志</el-menu-item>
        <el-menu-item index="/admin/live-monitor"><el-icon><Monitor /></el-icon> 实时监控</el-menu-item>
        <el-menu-item index="/admin/connectors"><el-icon><Connection /></el-icon> 平台连接器</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e4e7ed;background:#fff">
        <div style="display:flex;align-items:center;gap:8px">
          <el-button v-if="showBack" text @click="goBack"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
          <span style="font-size:14px;color:#606266">{{ pageTitle }}</span>
        </div>
        <div style="display:flex;align-items:center;gap:12px">
          <el-tag :type="modeTagType" size="small" effect="dark">{{ modeLabel }}</el-tag>
          <span style="color:#606266">{{ auth.user?.display_name || auth.user?.username }}（{{ auth.user?.role }}）</span>
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
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { getServiceModeConfig } from '../api'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const currentMode = ref('copilot')

const modeLabel = computed(() => {
  const map = { manual: '纯人工', copilot: '人机协同', auto: '全自动' }
  return map[currentMode.value] || currentMode.value
})
const modeTagType = computed(() => {
  const map = { manual: 'info', copilot: 'warning', auto: 'success' }
  return map[currentMode.value] || 'info'
})

async function loadMode() {
  try {
    const res = await getServiceModeConfig()
    if (res.data?.default_mode) currentMode.value = res.data.default_mode
  } catch { /* */ }
}

const activeMenu = computed(() => {
  const parts = route.path.split('/').filter(Boolean)
  return '/' + parts.slice(0, 2).join('/')
})

const showBack = computed(() => route.path.split('/').filter(Boolean).length > 2)

const pageTitle = computed(() => {
  const titles = {
    '/admin/dashboard': '工作台', '/admin/shops': '店铺管理', '/admin/products': '商品库',
    '/admin/orders': '订单中心', '/admin/tickets': '工单管理', '/admin/skill-groups': '技能组',
    '/admin/categories': '分类管理', '/admin/recommendations': '推荐管理', '/admin/ai-config': 'AI 配置',
    '/admin/knowledge': '企业知识库', '/admin/service-mode': '客服模式',
    '/admin/users': '用户管理', '/admin/sla-policies': 'SLA 策略', '/admin/auto-reply-logs': 'AI 话术日志',
    '/admin/ticket-categories': '工单分类',
    '/admin/webhook-logs': 'Webhook 监控',
    '/admin/audit-logs': '审计日志',
    '/admin/live-monitor': '实时监控',
    '/admin/connectors': '平台连接器',
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
  auth.logout()
  router.replace('/login')
}

onMounted(() => { loadMode() })
</script>
