<template>
  <el-container style="height:100vh">
    <el-aside width="220px" style="background:#1f2d3d;overflow-y:auto">
      <div style="color:#fff;text-align:center;padding:20px 0;font-size:16px;font-weight:bold;cursor:pointer" @click="$router.push('/dashboard')">
        {{ user?.shop_name || '商户后台' }}
      </div>
      <el-menu :default-active="activeMenu" router background-color="#1f2d3d" text-color="#bfcbd9" active-text-color="#409eff">
        <el-menu-item index="/dashboard"><el-icon><DataAnalysis /></el-icon> 工作台</el-menu-item>
        <el-menu-item index="/products"><el-icon><Goods /></el-icon> 商品管理</el-menu-item>
        <el-menu-item index="/orders"><el-icon><Document /></el-icon> 订单管理</el-menu-item>
        <el-menu-item index="/service"><el-icon><Service /></el-icon> 客服会话</el-menu-item>
        <el-menu-item index="/binding"><el-icon><Connection /></el-icon> SaaS 绑定</el-menu-item>
        <el-menu-item index="/settings"><el-icon><Setting /></el-icon> 店铺设置</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header style="display:flex;align-items:center;justify-content:flex-end;background:#fff;border-bottom:1px solid #e4e7ed;gap:16px">
        <span style="color:#606266;font-size:14px">{{ user?.contact_name || user?.username || '' }}</span>
        <el-button text @click="$router.push('/')">返回</el-button>
        <el-button type="danger" text @click="handleLogout">退出</el-button>
      </el-header>
      <el-main style="background:#f5f7fa"><router-view /></el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useMerchantStore } from '../stores/merchant'
import { DataAnalysis, Goods, Document, Service, Connection, Setting } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const store = useMerchantStore()
const user = computed(() => store.user)

const activeMenu = computed(() => {
  const p = route.path
  if (p.startsWith('/products')) return '/products'
  if (p.startsWith('/orders')) return '/orders'
  return p
})

function handleLogout() {
  store.logout()
  router.push('/login')
}
</script>
