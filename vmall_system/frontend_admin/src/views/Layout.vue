<template>
  <div class="vmall-layout">
    <!-- Sidebar -->
    <aside
      class="vmall-sidebar"
      :class="{ 'vmall-sidebar--collapsed': collapsed }"
      :style="{ width: collapsed ? '64px' : '220px' }"
    >
      <!-- Brand -->
      <div class="sidebar-brand" @click="$router.push('/dashboard')">
        <div class="sidebar-brand__icon">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="6" fill="#2A6BFF"/>
            <path d="M14 6L6 12l8 6 8-6-8-6z" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M6 16l8 6 8-6" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/>
          </svg>
        </div>
        <transition name="fade">
          <span v-show="!collapsed" class="sidebar-brand__text">vMall 运营后台</span>
        </transition>
      </div>

      <!-- Menu -->
      <nav class="sidebar-nav">
        <div
          v-for="item in menuItems"
          :key="item.index"
          class="nav-item"
          :class="{ 'nav-item--active': activeMenu === item.index }"
          @click="$router.push(item.index)"
        >
          <el-icon :size="18"><component :is="item.icon" /></el-icon>
          <transition name="fade">
            <span v-show="!collapsed" class="nav-item__text">{{ item.label }}</span>
          </transition>
          <span v-if="activeMenu === item.index" class="nav-item__indicator" />
        </div>
      </nav>

      <!-- Collapse Toggle -->
      <div class="sidebar-toggle" @click="toggleCollapse">
        <el-icon :size="18">
          <component :is="collapsed ? 'DArrowRight' : 'DArrowLeft'" />
        </el-icon>
      </div>
    </aside>

    <!-- Main Area -->
    <div class="vmall-main">
      <!-- Header -->
      <header class="vmall-header glass-header">
        <div class="header-left">
          <el-button v-if="showBack" text @click="goBack" class="header-back-btn">
            <el-icon><ArrowLeft /></el-icon>
            <span>返回</span>
          </el-button>
          <span class="header-title">{{ pageTitle }}</span>
        </div>

        <div class="header-right">
          <!-- Search -->
          <div class="header-search">
            <el-icon :size="16" color="#909399"><Search /></el-icon>
            <input class="header-search__input" type="text" placeholder="搜索..." />
          </div>

          <!-- Notifications -->
          <el-badge :value="0" :hidden="true">
            <el-button text class="header-icon-btn">
              <el-icon :size="20"><Bell /></el-icon>
            </el-button>
          </el-badge>

          <!-- Sync Status -->
          <span class="sync-dot sync-dot--ok" title="系统运行正常" />

          <!-- User -->
          <el-dropdown trigger="click">
            <div class="header-user">
              <div class="header-user__avatar">
                {{ (auth.user?.username || 'V')[0].toUpperCase() }}
              </div>
              <span class="header-user__name">{{ auth.user?.username }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>
                  <el-icon><UserFilled /></el-icon> 个人设置
                </el-dropdown-item>
                <el-dropdown-item divided @click="logout">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- Content -->
      <main class="vmall-content">
        <router-view />
      </main>

      <!-- Footer -->
      <footer class="vmall-footer">
        <span>v1.0.0</span>
        <span>·</span>
        <span>技术支持</span>
        <span>·</span>
        <span>隐私政策</span>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import {
  DataAnalysis, Document, Warning, ChatDotRound, Van, Wallet, Setting,
  ArrowLeft, Search, Bell, UserFilled, SwitchButton,
  DArrowLeft, DArrowRight,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// ── Collapse ──
const collapsed = ref(false)
onMounted(() => {
  if (localStorage.getItem('vmall-sidebar-collapsed') === 'true') collapsed.value = true
})
function toggleCollapse() {
  collapsed.value = !collapsed.value
  localStorage.setItem('vmall-sidebar-collapsed', String(collapsed.value))
}

// ── Menu ──
const menuItems = [
  { index: '/dashboard', label: '总览', icon: DataAnalysis },
  { index: '/orders', label: '订单管理', icon: Document },
  { index: '/after-sales', label: '售后管理', icon: Warning },
  { index: '/conversations', label: '客服消息', icon: ChatDotRound },
  { index: '/logistics', label: '物流管理', icon: Van },
  { index: '/wallets', label: '钱包管理', icon: Wallet },
  { index: '/settings', label: '系统设置', icon: Setting },
]

const activeMenu = computed(() => {
  const path = route.path
  if (path.startsWith('/orders')) return '/orders'
  if (path.startsWith('/after-sales')) return '/after-sales'
  if (path.startsWith('/conversations')) return '/conversations'
  if (path.startsWith('/logistics')) return '/logistics'
  if (path.startsWith('/wallets')) return '/wallets'
  if (path.startsWith('/settings')) return '/settings'
  return '/dashboard'
})

const showBack = computed(() => route.path !== '/dashboard')

const pageTitle = computed(() => {
  const path = route.path
  if (path.startsWith('/orders')) return '订单管理'
  if (path.startsWith('/after-sales')) return '售后管理'
  if (path.startsWith('/conversations')) return '客服消息'
  if (path.startsWith('/logistics')) return '物流管理'
  if (path.startsWith('/wallets')) return '钱包管理'
  if (path.startsWith('/settings')) return '系统设置'
  return '总览'
})

function goBack() {
  if (window.history.length > 2) router.back()
  else router.push('/dashboard')
}

function logout() { auth.logout(); router.replace('/login') }
</script>

<style scoped>
.vmall-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  position: relative;
  z-index: var(--z-content);
}

.vmall-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg-main);
}

/* ── Sidebar ── */
.vmall-sidebar {
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width var(--transition-slow);
  overflow: hidden;
}

.vmall-sidebar--collapsed .nav-item {
  justify-content: center;
  padding: 12px 0;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px;
  cursor: pointer;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}

.sidebar-brand__icon {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}

.sidebar-brand__text {
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  white-space: nowrap;
  letter-spacing: 0.5px;
}

.sidebar-nav {
  flex: 1;
  padding: 8px 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.sidebar-nav::-webkit-scrollbar {
  width: 4px;
}

.sidebar-nav::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.1);
  border-radius: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  color: var(--text-sidebar);
  cursor: pointer;
  font-size: 14px;
  transition: all var(--transition-fast);
  position: relative;
  white-space: nowrap;
}

.nav-item:hover {
  background: var(--bg-sidebar-hover);
  color: var(--text-sidebar-active);
}

.nav-item--active {
  background: var(--bg-sidebar-active);
  color: var(--text-sidebar-active);
  font-weight: 500;
}

.nav-item__indicator {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 24px;
  background: var(--color-brand);
  border-radius: 0 3px 3px 0;
}

.sidebar-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px;
  color: var(--text-sidebar);
  cursor: pointer;
  border-top: 1px solid rgba(255,255,255,0.06);
  transition: all var(--transition-fast);
  flex-shrink: 0;
}

.sidebar-toggle:hover {
  background: var(--bg-sidebar-hover);
  color: var(--text-sidebar-active);
}

/* ── Header ── */
.vmall-header {
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

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-back-btn { color: var(--text-secondary); }

.header-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-regular);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-search {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: rgba(0,0,0,0.04);
  border-radius: var(--radius-full);
  border: 1px solid transparent;
  transition: all var(--transition-fast);
  width: 200px;
}

.header-search:focus-within {
  background: var(--bg-card);
  border-color: var(--color-brand);
  box-shadow: 0 0 0 3px var(--color-brand-bg);
  width: 240px;
}

.header-search__input {
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  color: var(--text-primary);
  width: 100%;
}

.header-search__input::placeholder {
  color: var(--text-placeholder);
}

.header-icon-btn {
  padding: 6px;
  color: var(--text-regular);
}

.header-icon-btn:hover {
  background: rgba(0,0,0,0.04);
  border-radius: var(--radius-sm);
}

.sync-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.sync-dot--ok {
  background-color: var(--color-success);
  box-shadow: 0 0 6px rgba(34,197,94,0.4);
}

.header-user {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.header-user:hover {
  background: rgba(0,0,0,0.04);
}

.header-user__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-brand);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
}

.header-user__name {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
}

/* ── Content ── */
.vmall-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--bg-main);
}

/* ── Footer ── */
.vmall-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 20px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-card);
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
  height: var(--footer-height);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
