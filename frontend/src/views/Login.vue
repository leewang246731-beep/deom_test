<template>
  <div class="login-page">
    <!-- Gradient overlay -->
    <div class="login-bg-overlay" />

    <!-- Login Card -->
    <div class="login-card">
      <div class="login-card__accent" />
      <div class="login-card__body">
        <!-- Brand -->
        <div class="login-brand">
          <svg width="40" height="40" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="6" fill="#2A6BFF"/>
            <path d="M8 18l4-8 4 6 4-8 4 10" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <h2 class="login-brand__title">{{ portalConfig.title }}</h2>
          <p class="login-brand__subtitle">企业级智能托管平台</p>
        </div>

        <!-- Form -->
        <el-form
          :model="form"
          :rules="rules"
          ref="formRef"
          label-width="0"
          size="large"
          class="login-form"
        >
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="用户名"
              prefix-icon="User"
              class="login-input"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="密码"
              prefix-icon="Lock"
              show-password
              class="login-input"
              @keyup.enter="handleLogin"
            />
          </el-form-item>

          <!-- Multi-merchant select -->
          <el-form-item v-if="availableMerchants.length > 0" prop="merchant_id">
            <el-select
              v-model="form.merchant_id"
              placeholder="请选择商户"
              style="width: 100%"
              class="login-select"
            >
              <el-option
                v-for="m in availableMerchants"
                :key="m.merchant_id"
                :label="'商户 #' + m.merchant_id + ' — ' + m.display_name + ' (' + m.role + ')'"
                :value="m.merchant_id"
              />
            </el-select>
          </el-form-item>

          <el-form-item>
            <el-button
              ref="loginBtn"
              type="primary"
              class="login-btn"
              :loading="loading"
              @click="handleLogin"
            >
              登 录
            </el-button>
          </el-form-item>
        </el-form>

        <!-- Hint -->
        <p class="login-hint">{{ portalConfig.hint }}</p>
      </div>
    </div>
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
const loginBtn = ref(null)
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

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  position: relative;
  z-index: var(--z-content);
  overflow: hidden;
}

/* ── Background Overlay ── */
.login-bg-overlay {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse at 30% 20%, rgba(42, 107, 255, 0.08) 0%, transparent 60%),
    radial-gradient(ellipse at 70% 80%, rgba(30, 42, 65, 0.06) 0%, transparent 60%),
    var(--bg-main);
  z-index: 0;
}

/* ── Card ── */
.login-card {
  position: relative;
  z-index: 1;
  width: 420px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border-radius: var(--radius-lg);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.10), 0 2px 8px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}

.login-card__accent {
  height: 3px;
  background: linear-gradient(90deg, #2A6BFF, #5B8DFF, #2A6BFF);
}

.login-card__body {
  padding: 36px 40px 28px;
}

/* ── Brand ── */
.login-brand {
  text-align: center;
  margin-bottom: 28px;
}

.login-brand__title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 12px 0 6px;
  letter-spacing: 0.3px;
}

.login-brand__subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
}

/* ── Form ── */
.login-form {
  margin-top: 8px;
}

.login-input :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--border-color) inset;
  border-radius: var(--radius-sm);
  padding: 2px 12px;
}

.login-input :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--color-brand) inset;
}

.login-select :deep(.el-input__wrapper) {
  border-radius: var(--radius-sm);
}

/* ── Button ── */
.login-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 2px;
  border-radius: var(--radius-sm);
  margin-top: 4px;
  transition: all var(--transition-fast);
}

.login-btn:not(.is-loading):active {
  transform: scale(0.97);
}

/* ── Hint ── */
.login-hint {
  text-align: center;
  color: var(--text-secondary);
  font-size: 12px;
  margin: 16px 0 0;
}

/* ── Responsive ── */
@media (max-width: 480px) {
  .login-card {
    width: calc(100% - 32px);
    margin: 0 16px;
  }

  .login-card__body {
    padding: 28px 24px 24px;
  }
}
</style>
