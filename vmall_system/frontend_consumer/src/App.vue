<template>
  <div>
    <!-- 顶部导航栏（登录后显示） -->
    <div v-if="auth.isLoggedIn" style="position:sticky;top:0;z-index:100;background:#fff;border-bottom:1px solid #ebeef5;padding:8px 16px;display:flex;justify-content:space-between;align-items:center">
      <div style="display:flex;align-items:center;gap:12px">
        <span style="font-weight:bold;font-size:16px;color:#409eff;cursor:pointer" @click="$router.push('/home')">vMall</span>
        <el-button text size="small" @click="$router.push('/home')">首页</el-button>
        <el-button text size="small" @click="$router.push('/orders')">订单</el-button>
        <el-button text size="small" @click="$router.push('/profile')">个人中心</el-button>
      </div>
      <div style="display:flex;align-items:center;gap:8px">
        <span style="font-size:12px;color:#909399">{{ auth.user?.nickname || auth.user?.username }}</span>
        <el-button v-if="canGoBack" text size="small" @click="goBack">← 返回</el-button>
      </div>
    </div>
    <router-view />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const canGoBack = computed(() => {
  return route.path !== '/home' && route.path !== '/login' && route.path !== '/'
})

const cachedViews = ['Home', 'ProductDetail', 'MyOrders', 'Chat', 'Profile']

function goBack() {
  if (window.history.length > 2) {
    router.back()
  } else {
    router.push('/home')
  }
}
</script>
