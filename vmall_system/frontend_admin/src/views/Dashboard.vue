<template>
  <div class="vmall-dashboard fade-slide-in">
    <div class="dashboard-header">
      <h3 class="dashboard-title">总览</h3>
      <el-button size="small" :icon="RefreshRight" @click="fetchData" :loading="loading">刷新</el-button>
    </div>

    <!-- KPI Cards -->
    <div class="kpi-row">
      <div
        v-for="card in mainCards"
        :key="card.title"
        class="kpi-card card-hover"
      >
        <div class="kpi-card__header">
          <span class="kpi-card__title">{{ card.title }}</span>
          <el-icon :size="20" :color="card.color">
            <component :is="card.icon" />
          </el-icon>
        </div>
        <div class="kpi-card__value">{{ card.displayValue }}</div>
        <div class="kpi-card__trend" :class="'kpi-card__trend--' + card.trend">
          <span v-if="card.trend === 'up'">▲</span>
          <span v-else-if="card.trend === 'down'">▼</span>
          <span v-else>—</span>
          {{ card.trendText }}
        </div>
      </div>
    </div>

    <!-- Two-Column Area -->
    <div class="dashboard-columns">
      <!-- Left (65%) — Order Status Overview -->
      <div class="dashboard-left">
        <el-card shadow="never" class="dashboard-card">
          <template #header>
            <div class="card-header">
              <span>订单状态概览</span>
            </div>
          </template>
          <div class="progress-list">
            <div class="progress-item">
              <div class="progress-item__header">
                <span>履约进度</span>
                <span class="progress-item__value">{{ fulfillmentRate }}%</span>
              </div>
              <ProgressBar :percentage="fulfillmentRate" :height="10" color="#2A6BFF" />
            </div>
            <div class="progress-item">
              <div class="progress-item__header">
                <span>售后处理率</span>
                <span class="progress-item__value">{{ afterSaleRate }}%</span>
              </div>
              <ProgressBar :percentage="afterSaleRate" :height="10" color="#22C55E" />
            </div>
          </div>
        </el-card>

        <!-- Order Summary -->
        <el-card shadow="never" class="dashboard-card">
          <template #header>
            <div class="card-header"><span>订单摘要</span></div>
          </template>
          <el-table :data="orderSummary" size="small" :show-header="true" stripe>
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column prop="count" label="数量" align="center" />
            <el-table-column label="占比" width="180">
              <template #default="{ row }">
                <ProgressBar
                  :percentage="row.percent"
                  :height="6"
                  :showText="false"
                  :color="row.color"
                />
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>

      <!-- Right (35%) -->
      <div class="dashboard-right">
        <!-- Activity Feed -->
        <el-card shadow="never" class="dashboard-card">
          <template #header>
            <div class="card-header"><span>最近动态</span></div>
          </template>
          <div class="activity-feed">
            <div v-for="(act, i) in activities" :key="i" class="activity-feed-item">
              <div class="activity-feed-item__dot" />
              <div class="activity-feed-item__content">
                <p class="activity-feed-item__text">{{ act.text }}</p>
                <span class="activity-feed-item__time">{{ act.time }}</span>
              </div>
            </div>
          </div>
        </el-card>

        <!-- Quick Actions -->
        <el-card shadow="never" class="dashboard-card">
          <template #header>
            <div class="card-header"><span>快捷操作</span></div>
          </template>
          <div class="quick-actions">
            <div class="quick-action" @click="$router.push('/orders')">
              <el-icon :size="18"><Document /></el-icon>
              <span>查看订单</span>
            </div>
            <div class="quick-action" @click="$router.push('/after-sales')">
              <el-icon :size="18"><Warning /></el-icon>
              <span>处理售后</span>
            </div>
            <div class="quick-action" @click="$router.push('/conversations')">
              <el-icon :size="18"><ChatDotRound /></el-icon>
              <span>客服消息</span>
            </div>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, computed, onMounted } from 'vue'
import { RefreshRight, Document, Box, Warning, Money, ChatDotRound } from '@element-plus/icons-vue'
import { getDashboard } from '../api'
import ProgressBar from '../components/ProgressBar.vue'

const loading = ref(false)

const cards = reactive([
  { title: '今日订单', value: 0, icon: 'Document', color: '#2A6BFF', trend: 'flat', trendText: '实时' },
  { title: '待发货', value: 0, icon: 'Box', color: '#F59E0B', trend: 'flat', trendText: '待处理' },
  { title: '待审核售后', value: 0, icon: 'Warning', color: '#EF4444', trend: 'flat', trendText: '需关注' },
  { title: '今日 GMV', value: '¥0', icon: 'Money', color: '#22C55E', trend: 'up', trendText: '实时' },
])

const mainCards = computed(() => cards.map(c => ({
  ...c,
  displayValue: c.value,
})))

// ── Progress calculations ──
const fulfillmentRate = computed(() => {
  const total = cards[0].value || 0
  const pending = cards[1].value || 0
  if (total === 0) return 0
  return Math.round(((total - pending) / total) * 100)
})

const afterSaleRate = computed(() => {
  const total = cards[0].value || 1
  const pending = cards[2].value || 0
  return Math.round(Math.max(0, 100 - (pending / total) * 100))
})

// ── Demo order summary ──
const orderSummary = computed(() => [
  { status: '已完成', count: Math.round(cards[0].value * 0.65), percent: 65, color: '#22C55E' },
  { status: '待发货', count: cards[1].value, percent: Math.round((cards[1].value / Math.max(cards[0].value, 1)) * 100), color: '#F59E0B' },
  { status: '退款/售后', count: cards[2].value, percent: Math.round((cards[2].value / Math.max(cards[0].value, 1)) * 100), color: '#EF4444' },
])

// ── Demo Activity ──
const activities = [
  { text: '新订单 #VM2024001 已创建，待发货', time: '5 分钟前' },
  { text: '售后申请 #AS2024032 待审核', time: '27 分钟前' },
  { text: '客服「张三」处理了新会话', time: '1 小时前' },
  { text: '物流信息更新：订单 #VM2023891 已签收', time: '2 小时前' },
]

// ── Fetch ──
async function fetchData() {
  loading.value = true
  try {
    const d = (await getDashboard()).data
    cards[0].value = d.today_orders
    cards[1].value = d.pending_ship
    cards[2].value = d.pending_review
    cards[3].value = '¥' + d.today_gmv

    if (d.today_orders > 50) { cards[0].trend = 'up'; cards[0].trendText = '较昨日增长' }
    if (d.pending_ship === 0) { cards[1].trend = 'down'; cards[1].trendText = '已清零' }
  } catch { /* */ }
  finally { loading.value = false }
}

onMounted(fetchData)
</script>

<style scoped>
.vmall-dashboard {
  max-width: 1200px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.dashboard-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* ── KPI Row ── */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.kpi-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 20px 24px;
  box-shadow: var(--shadow-normal);
  border: 1px solid var(--border-light);
}

.kpi-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.kpi-card__title {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 500;
}

.kpi-card__value {
  font-size: 28px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.2;
  margin-bottom: 8px;
}

.kpi-card__trend {
  font-size: 12px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.kpi-card__trend--up { color: var(--color-success); }
.kpi-card__trend--down { color: var(--color-danger); }
.kpi-card__trend--flat { color: var(--text-secondary); }

/* ── Columns ── */
.dashboard-columns {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 16px;
  align-items: start;
}

.dashboard-left {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-width: 0;
}

.dashboard-right {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── Cards ── */
.dashboard-card {
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

/* ── Progress List ── */
.progress-list {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.progress-item__header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--text-regular);
}

.progress-item__value {
  font-weight: 600;
  color: var(--text-primary);
}

/* ── Activity Feed ── */
.activity-feed {
  display: flex;
  flex-direction: column;
}

.activity-feed-item {
  display: flex;
  gap: 12px;
  padding: 10px 0;
}

.activity-feed-item:not(:last-child) {
  border-bottom: 1px solid var(--border-light);
}

.activity-feed-item__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-brand);
  margin-top: 4px;
  flex-shrink: 0;
}

.activity-feed-item__content {
  flex: 1;
}

.activity-feed-item__text {
  font-size: 13px;
  color: var(--text-primary);
  margin: 0 0 4px;
  line-height: 1.4;
}

.activity-feed-item__time {
  font-size: 11px;
  color: var(--text-secondary);
}

/* ── Quick Actions ── */
.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.quick-action {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--bg-main);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  transition: all var(--transition-fast);
}

.quick-action:hover {
  border-color: var(--color-brand);
  color: var(--color-brand);
  background: var(--color-brand-bg);
  transform: translateY(-1px);
}

/* ── Responsive ── */
@media (max-width: 1200px) {
  .dashboard-columns {
    grid-template-columns: 1fr;
  }
  .dashboard-right {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 768px) {
  .kpi-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .dashboard-right {
    grid-template-columns: 1fr;
  }
}
</style>
