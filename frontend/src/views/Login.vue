<template>
  <div style="display:flex;justify-content:center;align-items:center;height:100vh;background:#f5f7fa">
    <el-card style="width:420px">
      <template #header><h2 style="text-align:center;margin:0">{{ portalTitle }}</h2></template>
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
      <p style="text-align:center;color:#909399;font-size:12px">{{ portalHint }}</p>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { login } from '../api'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref(null)
const loading = ref(false)
const form = reactive({ username: '', password: '' })

const isServicePortal = computed(() => {
  return window.location.port === '8094'
})

const portalTitle = computed(() => {
  return isServicePortal.value ? '智能托管 SaaS 客服工作台' : '多平台智能托管 SaaS'
})

const portalHint = computed(() => {
  return isServicePortal.value ? '演示账号：service / 123456' : '演示账号：admin / 123456'
})

onMounted(() => {
  if (isServicePortal.value) {
    form.username = 'service'
    form.password = '123456'
  } else {
    form.username = 'admin'
    form.password = '123456'
  }
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
    auth.login(res.data)
    const role = res.data?.user?.role
    if (role === 'service') router.replace('/service/workbench')
    else router.replace('/admin/dashboard')
  } finally {
    loading.value = false
  }
}
</script>