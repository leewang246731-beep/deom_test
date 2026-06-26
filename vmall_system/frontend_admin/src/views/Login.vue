<template>
  <div class="vmall-login">
    <!-- Background overlay -->
    <div class="login-bg-overlay" />

    <!-- Login Card -->
    <div class="login-card">
      <div class="login-card__accent" />
      <div class="login-card__body">
        <!-- Brand -->
        <div class="login-brand">
          <svg width="40" height="40" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="6" fill="#2A6BFF"/>
            <path d="M14 6L6 12l8 6 8-6-8-6z" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M6 16l8 6 8-6" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/>
          </svg>
          <h2 class="login-brand__title">vMall 运营后台</h2>
          <p class="login-brand__subtitle">虚拟商城管理平台</p>
        </div>

        <!-- Form -->
        <el-form :model="f" size="large" class="login-form">
          <el-form-item>
            <el-input
              v-model="f.u"
              placeholder="用户名"
              prefix-icon="User"
              class="login-input"
            />
          </el-form-item>
          <el-form-item>
            <el-input
              v-model="f.p"
              type="password"
              placeholder="密码"
              prefix-icon="Lock"
              show-password
              class="login-input"
              @keyup.enter="doLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              class="login-btn"
              :loading="l"
              @click="doLogin"
            >
              登 录
            </el-button>
          </el-form-item>
        </el-form>

        <p class="login-hint">admin_vmall / 123456</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { login } from '../api'

const r = useRouter()
const a = useAuthStore()
const l = ref(false)
const f = reactive({ u: 'admin_vmall', p: '123456' })

async function doLogin() {
  l.value = true
  try {
    const res = await login(f.u, f.p)
    a.login(res.data)
    r.replace('/dashboard')
  } finally {
    l.value = false
  }
}
</script>

<style scoped>
.vmall-login {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  position: relative;
  z-index: var(--z-content);
  overflow: hidden;
}

/* ── Background ── */
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
  width: 400px;
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
  padding: 36px 36px 28px;
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

/* ── Button ── */
.login-btn {
  width: 100%;
  height: 44px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 2px;
  border-radius: var(--radius-sm);
  margin-top: 4px;
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

@media (max-width: 480px) {
  .login-card {
    width: calc(100% - 32px);
  }
  .login-card__body {
    padding: 28px 24px 24px;
  }
}
</style>
