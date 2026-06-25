<template>
  <el-container style="height:100vh">
    <el-aside width="200px" style="background:#1f2d3d">
      <div style="color:#fff;text-align:center;padding:20px 0;font-size:16px;font-weight:bold">vMall 运营后台</div>
      <el-menu :default-active="activeMenu" router background-color="#1f2d3d" text-color="#bfcbd9" active-text-color="#409eff">
        <el-menu-item index="/dashboard"><el-icon><DataAnalysis/></el-icon> 总览</el-menu-item>
        <el-menu-item index="/orders"><el-icon><Document/></el-icon> 订单</el-menu-item>
        <el-menu-item index="/after-sales"><el-icon><Warning/></el-icon> 售后</el-menu-item>
        <el-menu-item index="/conversations"><el-icon><ChatDotRound/></el-icon> 客服消息</el-menu-item>
        <el-menu-item index="/logistics"><el-icon><Van/></el-icon> 物流管理</el-menu-item>
        <el-menu-item index="/wallets"><el-icon><Wallet/></el-icon> 钱包管理</el-menu-item>
        <el-menu-item index="/settings"><el-icon><Setting/></el-icon> 系统设置</el-menu-item>
      </el-menu></el-aside>
    <el-container>
      <el-header style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e4e7ed;background:#fff">
        <div style="display:flex;align-items:center;gap:8px">
          <el-button v-if="showBack" text @click="goBack"><el-icon><ArrowLeft/></el-icon> 返回</el-button>
          <span style="font-size:14px;color:#606266">{{ pageTitle }}</span>
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <span style="color:#606266">{{auth.user?.username}}</span>
          <el-button type="danger" text @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main style="background:#f5f7fa">
        <router-view />
      </el-main>
    </el-container></el-container>
</template>
<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/orders')) return '/orders'
  if (path.startsWith('/after-sales')) return '/after-sales'
  if (path.startsWith('/conversations')) return '/conversations'
  if (path.startsWith('/logistics')) return '/logistics'
  if (path.startsWith('/wallets')) return '/wallets'
  if (path.startsWith('/settings')) return '/settings'
  return '/dashboard'
})

const showBack = computed(() => route.path !== '/dashboard')
const pageTitle = computed(() => {
  const path = route.path
  if (path.startsWith('/orders')) return '订单管理'
  if (path.startsWith('/after-sales')) return '售后管理'
  if (path.startsWith('/conversations')) return '客服消息'
  if (path.startsWith('/logistics')) return '物流管理'
  if (path.startsWith('/wallets')) return '钱包管理'
  if (path.startsWith('/settings')) return '系统设置'
  return '总览'
})

function goBack() {
  if (window.history.length > 2) router.back()
  else router.push('/dashboard')
}

function logout() { auth.logout(); router.replace('/login') }
</script>
