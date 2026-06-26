<template>
  <div class="service-layout">
    <!-- Header -->
    <header class="service-header glass-header">
      <div class="service-header__left">
        <span class="service-header__brand" @click="$router.push('/service/workbench')">
          <svg width="24" height="24" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="6" fill="#2A6BFF"/>
            <path d="M8 18l4-8 4 6 4-8 4 10" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          客服工作台
        </span>
        <el-segmented v-model="globalMode" :options="modeOptions" @change="onModeChange" size="small" class="mode-switcher" />
        <el-tabs v-model="activeTab" @tab-change="onTabChange" class="service-tabs">
          <el-tab-pane label="会话" name="workbench" />
          <el-tab-pane label="知识库" name="knowledge" />
        </el-tabs>
      </div>

      <div class="service-header__right">
        <!-- Sync status -->
        <span class="sync-dot sync-dot--ok" title="系统正常" />

        <!-- User -->
        <div class="header-user">
          <div class="header-user__avatar">
            {{ (auth.user?.display_name || auth.user?.username || 'S')[0].toUpperCase() }}
          </div>
          <span class="header-user__name">{{ auth.user?.display_name || auth.user?.username }}</span>
        </div>

        <el-button type="danger" text size="small" @click="handleLogout" class="logout-btn">
          退出
        </el-button>
      </div>
    </header>

    <!-- Content -->
    <main class="service-content">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { updateServiceModeConfig, getServiceModeConfig } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const globalMode = ref('copilot')
const modeOptions = [
  { label: '纯人工', value: 'manual' },
  { label: '人机协同', value: 'copilot' },
  { label: '全自动', value: 'auto' },
]

const activeTab = computed(() => route.path === '/service/knowledge' ? 'knowledge' : 'workbench')

function onTabChange(name) {
  router.push(name === 'knowledge' ? '/service/knowledge' : '/service/workbench')
}

async function onModeChange(mode) {
  const label = modeOptions.find(o => o.value === mode)?.label || mode
  try {
    await ElMessageBox.confirm(
      `确定将默认客服模式切换为「${label}」吗？`,
      '切换确认',
      { confirmButtonText: '切换', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  try {
    await updateServiceModeConfig({ default_mode: mode })
    ElMessage.success(`默认模式已切换为 ${label}`)
  } catch { /* error shown by interceptor */ }
}

function handleLogout() {
  auth.logout()
  router.replace('/login')
}

onMounted(async () => {
  try {
    const res = await getServiceModeConfig()
    if (res.data?.default_mode) globalMode.value = res.data.default_mode
  } catch { /* */ }
})
</script>

<style scoped>
.service-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-main);
  position: relative;
  z-index: var(--z-content);
}

/* ── Header ── */
.service-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 20px;
  flex-shrink: 0;
  background: var(--bg-header);
  backdrop-filter: blur(12px) saturate(180%);
  -webkit-backdrop-filter: blur(12px) saturate(180%);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  z-index: var(--z-header);
}

.service-header__left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.service-header__brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
  cursor: pointer;
  white-space: nowrap;
  letter-spacing: 0.3px;
}

.mode-switcher {
  flex-shrink: 0;
}

.service-tabs {
  margin-left: 4px;
}

.service-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.service-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
}

.service-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sync-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.sync-dot--ok {
  background-color: var(--color-success);
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.4);
}

.header-user {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-user__avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: var(--color-brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.header-user__name {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

.logout-btn {
  color: var(--text-secondary);
}

/* ── Content ── */
.service-content {
  flex: 1;
  overflow: hidden;
  background: var(--bg-main);
}
</style>
