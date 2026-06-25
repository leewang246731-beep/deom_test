<template>
  <div style="display:flex;justify-content:center;align-items:center;height:100vh;background:#f5f7fa">
    <el-card style="width:420px">
      <template #header><h2 style="text-align:center;margin:0">{{ portalConfig.title }}</h2></template>
      <el-form :model="form" :rules="rules" ref="formRef" label-width="0" size="large">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="用户名" prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" placeholder="密码" prefix-icon="Lock" show-password @keyup.enter="handleLogin" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" style="width:100%" :loading="loading" @click="handleLogin">登 录</el-button>
        </el-form-item>
      </el-form>
      <p style="text-align:center;color:#909399;font-size:12px">{{ portalConfig.hint }}</p>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { login } from '../api'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref(null)
const loading = ref(false)
const form = reactive({ username: '', password: '' })

const portalConfig = computed(() => {
  const port = window.location.port
  if (port === '8095') {
    return {
      title: '智能托管 SaaS 客服工作台',
      hint: '演示账号：service / 123456',
      defaultRedirect: '/service/workbench',
      allowedRoles: ['admin', 'manager', 'service'],
    }
  }
  if (port === '8094') {
    return {
      title: '商户工作台 - 智能托管',
      hint: '演示账号：admin / 123456',
      defaultRedirect: '/merchant/dashboard',
      allowedRoles: ['admin', 'manager'],
    }
  }
  // default: :8093 admin
  return {
    title: '多平台智能托管 SaaS',
    hint: '演示账号：admin / 123456',
    defaultRedirect: '/admin/dashboard',
    allowedRoles: ['admin', 'manager'],
  }
})

onMounted(() => {
  const port = window.location.port
  if (port === '8095') {
    form.username = 'service'
  } else {
    form.username = 'admin'
  }
  form.password = '123456'
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    const res = await login(form.username, form.password)
    const role = res.data?.user?.role
    const cfg = portalConfig.value
    if (!cfg.allowedRoles.includes(role)) {
      auth.logout()
      ElMessage.error(`此入口不支持 ${role} 角色登录，请使用正确的入口`)
      loading.value = false
      return
    }
    auth.login(res.data)
    router.replace(cfg.defaultRedirect)
  } finally {
    loading.value = false
  }
}
</script>
