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
        <!-- 多商户选择（仅在检测到多商户时显示） -->
        <el-form-item v-if="availableMerchants.length > 0" prop="merchant_id">
          <el-select v-model="form.merchant_id" placeholder="请选择商户" style="width:100%">
            <el-option v-for="m in availableMerchants" :key="m.merchant_id"
              :label="'商户 #' + m.merchant_id + ' — ' + m.display_name + ' (' + m.role + ')'"
              :value="m.merchant_id" />
          </el-select>
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
import { login, loginPlatform } from '../api'

const router = useRouter()
const auth = useAuthStore()
const formRef = ref(null)
const loading = ref(false)
const form = reactive({ username: '', password: '', merchant_id: null })
const availableMerchants = ref([])

const portalConfig = computed(() => {
  const port = window.location.port
  if (port === '8095') {
    return {
      title: '智能托管 SaaS - 客服工作台',
      hint: '演示账号：service / 123456',
      defaultRedirect: '/service/workbench',
      loginApi: 'merchant',
      allowedRoles: ['admin', 'manager', 'service'],
      defaultUser: 'service',
    }
  }
  if (port === '8094') {
    return {
      title: '商户工作台 - 智能托管',
      hint: '演示账号：admin / 123456',
      defaultRedirect: '/merchant/dashboard',
      loginApi: 'merchant',
      allowedRoles: ['admin', 'manager'],
      defaultUser: 'admin',
    }
  }
  // :8093 管理后台 — 平台运营账号
  return {
    title: '多平台智能托管 SaaS - 管理后台',
    hint: '演示账号：super_admin / 123456',
    defaultRedirect: '/admin/dashboard',
    loginApi: 'platform',
    allowedRoles: ['super_admin', 'manager'],
    defaultUser: 'super_admin',
  }
})

onMounted(() => {
  form.username = portalConfig.value.defaultUser
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
    const cfg = portalConfig.value
    // 根据入口选择登录 API
    const apiCall = cfg.loginApi === 'platform' ? loginPlatform : login
    const res = await apiCall(form.username, form.password, form.merchant_id || undefined)

    console.log('[Login] API response:', res)
    const role = res.data?.user?.role
    console.log('[Login] role:', role, 'allowedRoles:', cfg.allowedRoles)

    if (!cfg.allowedRoles.includes(role)) {
      auth.logout()
      auth.logoutPlatform()
      ElMessage.error('此入口不支持「' + role + '」角色登录，请使用正确的入口')
      loading.value = false
      return
    }

    // 根据登录类型分别存储
    if (cfg.loginApi === 'platform') {
      auth.loginPlatform(res.data)
    } else {
      auth.login(res.data)
    }

    console.log('[Login] token saved, redirecting to:', cfg.defaultRedirect)
    router.replace(cfg.defaultRedirect)
  } catch (e) {
    console.error('[Login] error:', e)
    const detail = e?.response?.data?.detail
    if (detail && detail.code === 40002 && detail.available_merchants) {
      // 多商户场景 — 显示商户选择器
      availableMerchants.value = detail.available_merchants
      form.merchant_id = detail.available_merchants[0]?.merchant_id
      ElMessage.warning(detail.msg)
    } else {
      const msg = (typeof detail === 'object' && detail.msg) ? detail.msg : '登录失败，请检查用户名和密码'
      ElMessage.error(msg)
    }
  } finally {
    loading.value = false
  }
}
</script>
