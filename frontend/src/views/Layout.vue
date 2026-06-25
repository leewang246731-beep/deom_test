<template>
  <el-container style="height:100vh">
    <el-aside width="220px" style="background:#1f2d3d">
      <div style="color:#fff;text-align:center;padding:20px 0;font-size:16px;font-weight:bold;cursor:pointer" @click="$router.push('/dashboard')">
        智能托管 SaaS
      </div>
      <el-menu :default-active="activeMenu" router background-color="#1f2d3d" text-color="#bfcbd9" active-text-color="#409eff">
        <el-menu-item index="/dashboard"><el-icon><DataAnalysis /></el-icon> 工作台</el-menu-item>
        <el-menu-item index="/shops"><el-icon><Shop /></el-icon> 店铺管理</el-menu-item>
        <el-menu-item index="/products"><el-icon><Goods /></el-icon> 商品库</el-menu-item>
        <el-menu-item index="/orders"><el-icon><Document /></el-icon> 订单中心</el-menu-item>
        <el-menu-item index="/tickets"><el-icon><Tickets /></el-icon> 工单管理</el-menu-item>
        <el-menu-item index="/service"><el-icon><Headset /></el-icon> 客服工作台</el-menu-item>
        <el-menu-item index="/skill-groups"><el-icon><UserFilled /></el-icon> 技能组</el-menu-item>
        <el-menu-item index="/categories"><el-icon><Grid /></el-icon> 分类管理</el-menu-item>
        <el-menu-item index="/recommendations"><el-icon><MagicStick /></el-icon> 推荐管理</el-menu-item>
        <el-menu-item index="/ai-config"><el-icon><Cpu /></el-icon> AI 配置</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e4e7ed;background:#fff">
        <div style="display:flex;align-items:center;gap:8px">
          <el-button v-if="showBack" text @click="goBack"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
          <span style="font-size:14px;color:#606266">{{ pageTitle }}</span>
        </div>
        <div>
          <span style="margin-right:16px;color:#606266">{{ auth.user?.display_name || auth.user?.username }}（{{ auth.user?.role }}）</span>
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
import { computed, onErrorCaptured } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// 菜单高亮：取前两级路径匹配（/tickets/123 → /tickets）
const activeMenu = computed(() => {
  const p = route.path
  const segments = p.split('/').filter(Boolean)
  return '/' + (segments[0] || 'dashboard')
})

// 返回按钮：子路由或详情页显示
const showBack = computed(() => {
  return route.path.split('/').filter(Boolean).length > 1
})

const pageTitle = computed(() => {
  const titles = {
    '/dashboard': '工作台', '/shops': '店铺管理', '/products': '商品库',
    '/orders': '订单中心', '/tickets': '工单管理', '/service': '客服工作台',
    '/skill-groups': '技能组', '/categories': '分类管理',
    '/recommendations': '推荐管理', '/ai-config': 'AI 配置',
  }
  return titles[activeMenu.value] || ''
})

function goBack() {
  if (window.history.length > 2) {
    router.back()
  } else {
    router.push(activeMenu.value)
  }
}

function handleLogout() {
  auth.logout()
  router.replace('/login')
}

onErrorCaptured((err, instance, info) => {
  console.error('[Layout] error boundary:', err, info)
  return false
})
</script>
