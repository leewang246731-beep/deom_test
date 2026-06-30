<template>
  <div class="admin-layout">
    <!-- Sidebar -->
    <aside
      class="admin-sidebar"
      :class="{ 'admin-sidebar--collapsed': collapsed }"
      :style="{ width: collapsed ? '64px' : '220px' }"
    >
      <!-- Brand -->
      <div class="sidebar-brand" @click="$router.push('/admin/dashboard')">
        <div class="sidebar-brand__icon">
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect width="28" height="28" rx="6" fill="#2A6BFF"/>
            <path d="M8 18l4-8 4 6 4-8 4 10" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <transition name="fade">
          <span v-show="!collapsed" class="sidebar-brand__text">智能托管 SaaS</span>
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
    <div class="admin-main">
      <!-- Header -->
      <header class="admin-header glass-header">
        <div class="header-left">
          <el-button v-if="showBack" text @click="goBack" class="header-back-btn">
            <el-icon><ArrowLeft /></el-icon>
            <span>返回</span>
          </el-button>
          <span class="header-title">{{ pageTitle }}</span>
        </div>

        <div class="header-center">
          <el-select
            v-model="activeMerchant"
            placeholder="选择商户"
            size="small"
            style="width: 200px"
            @change="onMerchantChange"
            clearable
          >
            <el-option
              v-for="m in merchantList"
              :key="m.id"
              :label="m.name"
              :value="m.id"
            />
          </el-select>
        </div>

        <div class="header-right">
          <!-- Global Search -->
          <div class="header-search">
            <el-icon :size="16" color="#909399"><Search /></el-icon>
            <input
              class="header-search__input"
              type="text"
              placeholder="搜索..."
            />
          </div>

          <!-- Notifications -->
          <el-badge :value="0" :hidden="true" class="header-badge">
            <el-button text class="header-icon-btn">
              <el-icon :size="20"><Bell /></el-icon>
            </el-button>
          </el-badge>

          <!-- Sync Status -->
          <el-tooltip content="系统运行正常" placement="bottom">
            <span class="sync-indicator" title="系统运行正常">
              <span class="sync-dot sync-dot--ok" />
            </span>
          </el-tooltip>

          <!-- User -->
          <el-dropdown trigger="click">
            <div class="header-user">
              <div class="header-user__avatar">
                {{ (auth.platformUser?.display_name || auth.platformUser?.username || 'U')[0].toUpperCase() }}
              </div>
              <span class="header-user__name">
                {{ auth.platformUser?.display_name || auth.platformUser?.username || auth.user?.display_name || auth.user?.username }}
              </span>
              <span class="header-user__role">
                {{ auth.platformUser?.role || auth.user?.role }}
              </span>
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
      <main class="admin-content">
        <router-view />
      </main>

      <!-- Footer -->
      <footer class="admin-footer">
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
  DataAnalysis, OfficeBuilding, Connection, WarningFilled, Link,
  AlarmClock, FolderOpened, Cpu, Reading, Monitor,
  ArrowLeft, Search, Bell, UserFilled, SwitchButton,
  DArrowLeft, DArrowRight,
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
import { getMerchants } from '../api'

// ── 商户选择器 ──
const activeMerchant = ref(parseInt(localStorage.getItem('active_merchant_id')) || null)
const merchantList = ref([])

onMounted(async () => {
  try {
    const res = await getMerchants()
    merchantList.value = res.data || []
    if (!activeMerchant.value && merchantList.value.length) {
      activeMerchant.value = merchantList.value[0].id
      localStorage.setItem('active_merchant_id', String(activeMerchant.value))
    }
  } catch { /* 非平台 token 则接口返回 403，静默 */ }
})

function onMerchantChange(val) {
  if (val) {
    localStorage.setItem('active_merchant_id', String(val))
  } else {
    localStorage.removeItem('active_merchant_id')
  }
}

const auth = useAuthStore()

// ── Collapse ──
const collapsed = ref(false)
onMounted(() => {
  const saved = localStorage.getItem('admin-sidebar-collapsed')
  if (saved === 'true') collapsed.value = true
})
function toggleCollapse() {
  collapsed.value = !collapsed.value
  localStorage.setItem('admin-sidebar-collapsed', String(collapsed.value))
}

// ── Menu ──
const menuItems = [
  { index: '/admin/dashboard', label: '工作台', icon: DataAnalysis },
  { index: '/admin/shops', label: '商户管理', icon: OfficeBuilding },
  { index: '/admin/connectors', label: '平台连接器', icon: Connection },
  { index: '/admin/audit-logs', label: '审计日志', icon: WarningFilled },
  { index: '/admin/webhook-logs', label: 'Webhook 监控', icon: Link },
  { index: '/admin/sla-policies', label: 'SLA 策略', icon: AlarmClock },
  { index: '/admin/ticket-categories', label: '工单分类', icon: FolderOpened },
  { index: '/admin/ai-config', label: 'AI 配置', icon: Cpu },
  { index: '/admin/knowledge', label: '企业知识库', icon: Reading },
  { index: '/admin/live-monitor', label: '实时监控', icon: Monitor },
]

const activeMenu = computed(() => {
  const parts = route.path.split('/').filter(Boolean)
  return '/' + parts.slice(0, 2).join('/')
})

const showBack = computed(() => route.path.split('/').filter(Boolean).length > 2)

const pageTitle = computed(() => {
  const titles = {
    '/admin/dashboard': '工作台', '/admin/shops': '商户管理',
    '/admin/connectors': '平台连接器', '/admin/audit-logs': '审计日志',
    '/admin/webhook-logs': 'Webhook 监控', '/admin/sla-policies': 'SLA 策略',
    '/admin/ticket-categories': '工单分类', '/admin/ai-config': 'AI 配置',
    '/admin/knowledge': '企业知识库', '/admin/live-monitor': '实时监控',
  }
  if (route.path.startsWith('/admin/tickets/')) return '工单详情'
  if (route.path.startsWith('/admin/products/')) return '商品详情'
  if (route.path.startsWith('/admin/orders/')) return '订单详情'
  return titles[route.path] || ''
})

function goBack() {
  if (window.history.length > 2) { router.back() }
  else { router.push('/admin/dashboard') }
}

function handleLogout() {
  auth.logoutPlatform()
  router.replace('/login')
}
</script>

<style scoped>
/* ── Layout ── */
.admin-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
  position: relative;
  z-index: var(--z-content);
}

.admin-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--bg-main);
}

/* ── Sidebar ── */
.admin-sidebar {
  background: var(--bg-sidebar);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  transition: width var(--transition-slow);
  overflow: hidden;
  position: relative;
  z-index: var(--z-sidebar);
}

.admin-sidebar--collapsed .nav-item {
  justify-content: center;
  padding: 12px 0;
}

/* ── Sidebar Brand ── */
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

/* ── Sidebar Nav ── */
.sidebar-nav {
  flex: 1;
  padding: 8px 0;
  overflow-y: auto;
  overflow-x: hidden;
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

.nav-item__text {
  flex: 1;
}

/* ── Sidebar Toggle ── */
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
.admin-header {
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

.header-back-btn {
  color: var(--text-secondary);
}

.header-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-regular);
}

.header-center {
  display: flex;
  align-items: center;
  flex: 1;
  justify-content: center;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── Header Search ── */
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

/* ── Header Icon Btn ── */
.header-icon-btn {
  padding: 6px;
  color: var(--text-regular);
}

.header-icon-btn:hover {
  background: rgba(0, 0, 0, 0.04);
  border-radius: var(--radius-sm);
}

/* ── Sync Indicator ── */
.sync-indicator {
  display: flex;
  align-items: center;
  padding: 4px;
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

.sync-dot--syncing {
  background-color: var(--color-warning);
  animation: pulse-glow 2s ease-in-out infinite;
}

/* ── Header User ── */
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

.header-user__role {
  font-size: 11px;
  color: var(--text-secondary);
  background: rgba(0, 0, 0, 0.04);
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

/* ── Main Content ── */
.admin-content {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
  z-index: var(--z-content);
  background: var(--bg-main);
}

/* ── Footer ── */
.admin-footer {
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

/* ── Transitions ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* ── Scrollbar ── */
.sidebar-nav::-webkit-scrollbar {
  width: 4px;
}

.sidebar-nav::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}
</style>
