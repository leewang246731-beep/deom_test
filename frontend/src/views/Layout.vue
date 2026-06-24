<template>
  <el-container style="height:100vh">
    <el-aside width="220px" style="background:#1f2d3d">
      <div style="color:#fff;text-align:center;padding:20px 0;font-size:16px;font-weight:bold">
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
      <el-header style="display:flex;align-items:center;justify-content:flex-end;border-bottom:1px solid #e4e7ed;background:#fff">
        <span style="margin-right:16px;color:#606266">{{ auth.user?.display_name || auth.user?.username }}（{{ auth.user?.role }}）</span>
        <el-button type="danger" text @click="handleLogout">退出</el-button>
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
const activeMenu = computed(() => route.path)

function handleLogout() {
  auth.logout()
  router.replace('/login')
}
</script>
