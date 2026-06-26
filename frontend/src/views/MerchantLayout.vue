<template>
  <div class="merchant-layout">
    <!-- Sidebar -->
    <aside
      class="merchant-sidebar"
      :class="{ 'merchant-sidebar--collapsed': collapsed }"
      :style="{ width: collapsed ? '64px' : '220px' }"
    >
      <!-- Brand -->
      <div class="sidebar-brand" @click="$router.push('/merchant/dashboard')">
        <div class="sidebar-brand__icon">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="6" fill="#2A6BFF"/>
            <path d="M8 18l4-8 4 6 4-8 4 10" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <transition name="fade">
          <span v-show="!collapsed" class="sidebar-brand__text">商户工作台</span>
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
    <div class="merchant-main">
      <!-- Header -->
      <header class="merchant-header glass-header">
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

          <!-- Sync status -->
          <span class="sync-dot sync-dot--ok" title="系统正常" />

          <!-- User -->
          <el-dropdown trigger="click">
            <div class="header-user">
              <div class="header-user__avatar">
                {{ (auth.user?.display_name || auth.user?.username || 'M')[0].toUpperCase() }}
              </div>
              <span class="header-user__name">{{ auth.user?.display_name || auth.user?.username }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item>
                  <el-icon><UserFilled /></el-icon> 个人设置
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- Content -->
      <main class="merchant-content">
        <router-view />
      </main>

      <!-- Footer -->
      <footer class="merchant-footer">
        <span>v2.0.0</span>
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
  DataAnalysis, Shop, Goods, Document, ChatDotRound, Tickets,
  MagicStick, Setting, User, Notebook, Monitor, Connection,
  ArrowLeft, Search, Bell, UserFilled, SwitchButton,
  DArrowLeft, DArrowRight,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

// ── Collapse ──
const collapsed = ref(false)
onMounted(() => {
  if (localStorage.getItem('merchant-sidebar-collapsed') === 'true') collapsed.value = true
})
function toggleCollapse() {
  collapsed.value = !collapsed.value
  localStorage.setItem('merchant-sidebar-collapsed', String(collapsed.value))
}

// ── Menu ──
const menuItems = [
  { index: '/merchant/dashboard', label: '工作台', icon: DataAnalysis },
  { index: '/merchant/shops', label: '店铺管理', icon: Shop },
  { index: '/merchant/products', label: '我的商品', icon: Goods },
  { index: '/merchant/orders', label: '订单管理', icon: Document },
  { index: '/merchant/conversations', label: '会话管理', icon: ChatDotRound },
  { index: '/merchant/tickets', label: '工单管理', icon: Tickets },
  { index: '/merchant/recommendations', label: 'AI推荐', icon: MagicStick },
  { index: '/merchant/service-mode', label: '客服模式', icon: Setting },
  { index: '/merchant/users', label: '用户管理', icon: User },
  { index: '/merchant/auto-reply-logs', label: 'AI 话术日志', icon: Notebook },
  { index: '/merchant/live-monitor', label: '实时监控', icon: Monitor },
  { index: '/merchant/connectors', label: '平台连接器', icon: Connection },
]

const activeMenu = computed(() => '/' + route.path.split('/').filter(Boolean).slice(0, 2).join('/'))

const showBack = computed(() => route.path !== '/merchant/dashboard')

const pageTitle = computed(() => {
  const map = {
    '/merchant/dashboard': '工作台', '/merchant/shops': '店铺管理',
    '/merchant/products': '我的商品', '/merchant/orders': '订单管理',
    '/merchant/conversations': '会话管理', '/merchant/tickets': '工单管理',
    '/merchant/recommendations': 'AI推荐', '/merchant/service-mode': '客服模式',
    '/merchant/users': '用户管理', '/merchant/auto-reply-logs': 'AI 话术日志',
    '/merchant/live-monitor': '实时监控', '/merchant/connectors': '平台连接器',
  }
  if (route.path.startsWith('/merchant/tickets/')) return '工单详情'
  return map[route.path] || ''
})

function goBack() {
  if (window.history.length > 2) router.back()
  else router.push('/merchant/dashboard')
}

function handleLogout() {
  auth.logout()
  router.replace('/login')
}
</script>

<style scoped>
.merchant-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  position: relative;
  z-index: var(--z-content);
}

.merchant-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg-main);
}

/* ── Sidebar ── */
.merchant-sidebar {
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width var(--transition-slow);
  overflow: hidden;
}

.merchant-sidebar--collapsed .nav-item {
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
  background: rgba(255, 255, 255, 0.1);
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
.merchant-header {
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
  background: rgba(0, 0, 0, 0.04);
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
  background: rgba(0, 0, 0, 0.04);
  border-radius: var(--radius-sm);
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
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.header-user:hover {
  background: rgba(0, 0, 0, 0.04);
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
.merchant-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  overflow-x: hidden;
  background: var(--bg-main);
}

/* ── Footer ── */
.merchant-footer {
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
