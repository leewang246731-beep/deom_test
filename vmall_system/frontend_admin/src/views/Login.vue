<template>
  <div style="display:flex;justify-content:center;align-items:center;height:100vh;background:#f5f7fa">
    <el-card style="width:380px"><template #header><h2 style="text-align:center;margin:0">vMall 运营后台</h2></template>
      <el-form :model="f" size="large">
        <el-form-item><el-input v-model="f.u" placeholder="用户名" prefix-icon="User"/></el-form-item>
        <el-form-item><el-input v-model="f.p" type="password" placeholder="密码" prefix-icon="Lock" show-password @keyup.enter="doLogin"/></el-form-item>
        <el-form-item><el-button type="primary" style="width:100%" :loading="l" @click="doLogin">登 录</el-button></el-form-item></el-form>
      <p style="text-align:center;color:#909399;font-size:12px">admin_vmall / 123456</p></el-card></div>
</template>
<script setup>
import { reactive, ref } from 'vue'; import { useRouter } from 'vue-router'; import { useAuthStore } from '../stores/auth'; import { login } from '../api'
const r=useRouter(); const a=useAuthStore(); const l=ref(false); const f=reactive({u:'admin_vmall',p:'123456'})
async function doLogin(){l.value=true;try{const res=await login(f.u,f.p);a.login(res.data);r.replace('/dashboard')}finally{l.value=false}}
</script>
