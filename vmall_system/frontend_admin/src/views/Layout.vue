<template>
  <el-container style="height:100vh">
    <el-aside width="200px" style="background:#1f2d3d">
      <div style="color:#fff;text-align:center;padding:20px 0;font-size:16px;font-weight:bold">vMall 运营后台</div>
      <el-menu :default-active="$route.path" router background-color="#1f2d3d" text-color="#bfcbd9" active-text-color="#409eff">
        <el-menu-item index="/dashboard"><el-icon><DataAnalysis/></el-icon> 总览</el-menu-item>
        <el-menu-item index="/orders"><el-icon><Document/></el-icon> 订单</el-menu-item>
        <el-menu-item index="/after-sales"><el-icon><Warning/></el-icon> 售后</el-menu-item>
        <el-menu-item index="/messages"><el-icon><ChatDotRound/></el-icon> 客服消息</el-menu-item>
        <el-menu-item index="/wallets"><el-icon><Wallet/></el-icon> 钱包管理</el-menu-item>
        <el-menu-item index="/settings"><el-icon><Setting/></el-icon> 系统设置</el-menu-item>
      </el-menu></el-aside>
    <el-container><el-header style="display:flex;align-items:center;justify-content:flex-end;border-bottom:1px solid #e4e7ed;background:#fff"><span style="margin-right:16px">{{auth.user?.username}}</span><el-button type="danger" text @click="logout">退出</el-button></el-header>
    <el-main style="background:#f5f7fa"><router-view/></el-main></el-container></el-container>
</template>
<script setup>
import { useRouter } from 'vue-router'; import { useAuthStore } from '../stores/auth'
const r=useRouter(); const auth=useAuthStore()
function logout(){auth.logout();r.replace('/login')}
</script>
