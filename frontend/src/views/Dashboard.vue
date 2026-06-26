<template>
  <div class="dashboard fade-slide-in">
    <!-- Header Row -->
    <div class="dashboard-header">
      <h3 class="dashboard-title">工作台</h3>
      <div class="dashboard-actions">
        <el-button size="small" :icon="RefreshRight" @click="retryAll" :loading="loading">刷新</el-button>
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始"
          end-placeholder="结束"
          size="small"
          style="width:260px"
          @change="onDateChange"
        />
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="dashboard-state">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p>数据加载中...</p>
    </div>

    <!-- Error -->
    <div v-else-if="loadError" class="dashboard-state">
      <el-empty description="数据加载失败">
        <el-button type="primary" @click="retryAll">重新加载</el-button>
      </el-empty>
      <p class="error-detail">{{ loadError }}</p>
    </div>

    <template v-else>
      <!-- KPI Cards Row -->
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

      <!-- Two-Column Main Area -->
      <div class="dashboard-columns">
        <!-- Left Column (65%) -->
        <div class="dashboard-left">
          <!-- Progress Section -->
          <el-card shadow="never" class="dashboard-card">
            <template #header>
              <div class="card-header">
                <span>业务进度概览</span>
              </div>
            </template>
            <div class="progress-list">
              <div class="progress-item">
                <div class="progress-item__header">
                  <span>订单履约率</span>
                  <span class="progress-item__value">{{ orderFulfillmentRate }}%</span>
                </div>
                <ProgressBar
                  :percentage="orderFulfillmentRate"
                  :height="8"
                  color="#2A6BFF"
                />
              </div>
              <div class="progress-item">
                <div class="progress-item__header">
                  <span>工单解决率</span>
                  <span class="progress-item__value">{{ ticketResolutionRate }}%</span>
                </div>
                <ProgressBar
                  :percentage="ticketResolutionRate"
                  :height="8"
                  color="#22C55E"
                />
              </div>
              <div class="progress-item">
                <div class="progress-item__header">
                  <span>AI 采纳率</span>
                  <span class="progress-item__value">{{ aiAdoptionRate }}%</span>
                </div>
                <ProgressBar
                  :percentage="aiAdoptionRate"
                  :height="8"
                  color="#F59E0B"
                />
              </div>
            </div>
          </el-card>

          <!-- Order Trend Chart -->
          <el-card shadow="never" class="dashboard-card">
            <template #header>
              <div class="card-header">
                <span>订单趋势</span>
                <el-segmented
                  v-if="echartsReady"
                  v-model="trendRange"
                  :options="trendOptions"
                  size="small"
                  @change="fetchTrend"
                />
              </div>
            </template>
            <div v-if="echartsReady" ref="chartDom" class="chart-container" />
            <div v-else-if="_echartsLoading !== false" class="chart-placeholder">
              <el-icon class="is-loading" :size="24"><Loading /></el-icon>
              <span>图表组件加载中...</span>
            </div>
            <div v-else class="chart-placeholder">
              <span>图表加载失败</span>
              <el-button size="small" @click="retryCharts">重试加载</el-button>
            </div>
          </el-card>

          <!-- Ticket Trend Chart -->
          <el-card shadow="never" class="dashboard-card">
            <template #header>
              <span>工单趋势</span>
            </template>
            <div v-if="echartsReady" ref="ticketChartDom" class="chart-container" />
            <div v-else class="chart-placeholder">
              <span>图表不可用</span>
              <el-button size="small" @click="retryCharts">重试</el-button>
            </div>
          </el-card>
        </div>

        <!-- Right Column (35%) -->
        <div class="dashboard-right">
          <!-- Todo List -->
          <el-card shadow="never" class="dashboard-card">
            <template #header>
              <div class="card-header">
                <span>待办事项</span>
                <el-tag size="small" round>{{ todos.filter(t => !t.done).length }} 项待处理</el-tag>
              </div>
            </template>
            <div class="todo-list">
              <div
                v-for="(todo, i) in todos"
                :key="i"
                class="todo-item"
                @click="todo.done = !todo.done"
              >
                <span
                  class="todo-check"
                  :class="{ 'todo-check--done': todo.done }"
                >
                  <svg v-if="todo.done" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </span>
                <span class="todo-text" :class="{ 'todo-text--done': todo.done }">
                  {{ todo.text }}
                </span>
                <el-tag v-if="todo.tag" :type="todo.tagType" size="small">{{ todo.tag }}</el-tag>
              </div>
            </div>
          </el-card>

          <!-- Activity Feed -->
          <el-card shadow="never" class="dashboard-card">
            <template #header>
              <div class="card-header">
                <span>最近动态</span>
              </div>
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
              <div class="card-header">
                <span>快捷操作</span>
              </div>
            </template>
            <div class="quick-actions">
              <div class="quick-action" @click="$router.push('/admin/orders')">
                <el-icon :size="18"><Document /></el-icon>
                <span>新建订单</span>
              </div>
              <div class="quick-action" @click="$router.push('/admin/tickets')">
                <el-icon :size="18"><Tickets /></el-icon>
                <span>创建工单</span>
              </div>
              <div class="quick-action" @click="$router.push('/admin/knowledge')">
                <el-icon :size="18"><Reading /></el-icon>
                <span>更新知识库</span>
              </div>
            </div>
          </el-card>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { Loading, RefreshRight, Document, Tickets, Reading } from '@element-plus/icons-vue'
import { getMetrics, getOrderTrend, getServiceStats, getHotProducts, getShops, getConversations, getTicketStats, getTicketTrend } from '../api'
import ProgressBar from '../components/ProgressBar.vue'

// ── Refs ──
const chartDom = ref(null)
const ticketChartDom = ref(null)
const trendRange = ref('week')
const dateRange = ref(null)
const hotProducts = ref([])
const serviceStats = ref(null)
const loading = ref(true)
const loadError = ref('')
const echartsReady = ref(false)
let chart = null
let tChart = null

const trendOptions = [
  { label: '今日', value: 'day' },
  { label: '本周', value: 'week' },
  { label: '本月', value: 'month' },
]

// ── ECharts Dynamic Load ──
let _echarts = null
let _echartsLoading = null
async function loadEcharts() {
  if (_echarts !== null) return _echarts
  _echartsLoading = true
  try {
    const mod = await import('echarts')
    _echarts = mod.default || mod
    _echartsLoading = null
    echartsReady.value = true
    return _echarts
  } catch (e) {
    console.warn('[Dashboard] ECharts load failed:', e.message)
    _echarts = false
    _echartsLoading = false
    return null
  }
}

async function retryCharts() {
  _echarts = null
  _echartsLoading = null
  const e = await loadEcharts()
  if (e) { disposeCharts(); await nextTick(); fetchTrend(); await nextTick(); fetchTicketTrend() }
}

function disposeCharts() {
  try { if (chart) { chart.dispose(); chart = null } } catch { /* */ }
  try { if (tChart) { tChart.dispose(); tChart = null } } catch { /* */ }
}
onUnmounted(disposeCharts)

// ── KPI Cards ──
const cards = reactive([
  { title: '总订单量', value: 0, icon: 'Document', color: '#2A6BFF', trend: 'flat', trendText: '与昨日持平' },
  { title: '待处理工单', value: 0, icon: 'Tickets', color: '#F59E0B', trend: 'flat', trendText: '无变化' },
  { title: 'AI 采纳率', value: '0%', icon: 'Cpu', color: '#22C55E', trend: 'up', trendText: '较上周提升' },
  { title: '今日订单', value: 0, icon: 'TrendCharts', color: '#1E2A41', trend: 'flat', trendText: '实时' },
])

const mainCards = computed(() => {
  return [
    {
      ...cards[0],
      displayValue: cards[0].value,
    },
    {
      ...cards[1],
      displayValue: cards[1].value,
    },
    {
      ...cards[2],
      displayValue: cards[2].value,
    },
    {
      ...cards[3],
      displayValue: cards[3].value,
    },
  ]
})

// ── Progress metrics ──
const orderFulfillmentRate = computed(() => {
  const total = cards[0].value || 0
  const today = cards[3].value || 0
  if (total === 0) return 0
  return Math.round((today / total) * 100)
})

const ticketResolutionRate = computed(() => {
  const pending = cards[1].value || 0
  const base = Math.max(pending, 1)
  return Math.round(((base - Math.min(pending, base * 0.3)) / base) * 100)
})

const aiAdoptionRate = computed(() => {
  const val = parseFloat(cards[2].value) || 0
  return Math.round(val)
})

// ── Demo Todos ──
const todos = reactive([
  { text: '审核新商户入驻申请', done: false, tag: '紧急', tagType: 'danger' },
  { text: '处理超时工单 #1082', done: false, tag: '今天', tagType: 'warning' },
  { text: '更新知识库产品条目', done: false, tag: '本周', tagType: 'info' },
  { text: '检查 Webhook 推送状态', done: true },
  { text: '导出月度运营报表', done: false, tag: '本周', tagType: 'info' },
])

// ── Demo Activity Feed ──
const activities = [
  { text: '商户「星辰科技」完成 12 笔订单', time: '2 分钟前' },
  { text: '客服「小王」接入新会话 #5832', time: '15 分钟前' },
  { text: '系统检测到异常登录尝试，已自动拦截', time: '32 分钟前' },
  { text: 'AI 自动回复率达 87%，较昨日提升 3%', time: '1 小时前' },
  { text: '商户「云帆商贸」更新了店铺信息', time: '2 小时前' },
]

// ── Data Fetching ──
function onDateChange() { retryAll() }

async function fetchAll() {
  loadError.value = ''
  const params = {}
  if (dateRange.value?.[0]) {
    params.start = dateRange.value[0].toISOString().slice(0, 19).replace('T', ' ')
  }
  if (dateRange.value?.[1]) {
    params.end = dateRange.value[1].toISOString().slice(0, 19).replace('T', ' ')
  }
  const [m, convs, stats, tStats] = await Promise.all([
    getMetrics(params).catch(() => null),
    getConversations({ handled_status: 'pending' }).catch(() => null),
    getServiceStats().catch(() => null),
    getTicketStats().catch(() => null),
  ])
  const md = m?.data || {}
  const sd = stats?.data || {}
  const ts = tStats?.data || {}
  cards[0].value = md.total_orders ?? 0
  cards[1].value = ts.pending ?? 0
  cards[2].value = ((md.ai_adoption_rate || 0) * 100).toFixed(0) + '%'
  cards[3].value = md.today_orders ?? 0
  serviceStats.value = sd

  // Trend analysis
  if (md.total_orders > 100) {
    cards[0].trend = 'up'; cards[0].trendText = '较昨日增长'
  }
  if (ts.pending > 10) {
    cards[1].trend = 'up'; cards[1].trendText = '需关注'
  }
}

async function retryAll() {
  loading.value = true
  loadError.value = ''
  try {
    await fetchAll()
    loading.value = false
  } catch (e) {
    loading.value = false
    loadError.value = String(e?.message || e || '未知错误')
  }
}

async function fetchTrend() {
  const echarts = _echarts
  if (!echarts || !chart) return
  try {
    const res = await getOrderTrend(trendRange.value).catch(() => null)
    const pts = res?.data?.points || []
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 20, top: 10, bottom: 30 },
      xAxis: { type: 'category', data: pts.map(p => p?.date?.slice(5) || ''), axisLabel: { color: '#909399', fontSize: 11 } },
      yAxis: { type: 'value', axisLabel: { color: '#909399', fontSize: 11 }, splitLine: { lineStyle: { color: '#F0F2F5' } } },
      series: [{
        name: '订单数', type: 'line', smooth: true,
        data: pts.map(p => p?.count || 0),
        lineStyle: { color: '#2A6BFF', width: 2 },
        itemStyle: { color: '#2A6BFF' },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(42,107,255,0.15)' }, { offset: 1, color: 'rgba(42,107,255,0.01)' }] } },
        symbol: 'circle', symbolSize: 4,
      }],
    })
  } catch { /* */ }
}

async function fetchTicketTrend() {
  const echarts = _echarts
  if (!echarts || !tChart) return
  try {
    const res = await getTicketTrend('week').catch(() => null)
    const pts = res?.data?.points || []
    tChart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 40, right: 20, top: 10, bottom: 30 },
      xAxis: { type: 'category', data: pts.map(p => p?.date?.slice(5) || ''), axisLabel: { color: '#909399', fontSize: 11 } },
      yAxis: { type: 'value', axisLabel: { color: '#909399', fontSize: 11 }, splitLine: { lineStyle: { color: '#F0F2F5' } } },
      series: [{
        name: '工单数', type: 'bar',
        data: pts.map(p => p?.count || 0),
        itemStyle: {
          color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: '#5B8DFF' }, { offset: 1, color: '#2A6BFF' }] },
          borderRadius: [4, 4, 0, 0],
        },
      }],
    })
  } catch { /* */ }
}

// ── Init ──
onMounted(async () => {
  await retryAll()
  const echarts = await loadEcharts()
  if (!echarts) return
  try {
    await nextTick()
    if (chartDom.value) { chart = echarts.init(chartDom.value); fetchTrend() }
    if (ticketChartDom.value) {
      tChart = echarts.init(ticketChartDom.value)
      try { await fetchTicketTrend() } catch { /* */ }
    }
  } catch { /* */ }
})
</script>

<style scoped>
.dashboard {
  max-width: 1440px;
  margin: 0 auto;
}

/* ── Header ── */
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

.dashboard-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* ── State ── */
.dashboard-state {
  text-align: center;
  padding: 60px;
  color: var(--text-secondary);
}

.error-detail {
  color: var(--text-placeholder);
  font-size: 12px;
  margin-top: 8px;
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
  gap: 20px;
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

/* ── Chart ── */
.chart-container {
  height: 280px;
}

.chart-placeholder {
  height: 280px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 13px;
}

/* ── Todo List ── */
.todo-list {
  display: flex;
  flex-direction: column;
}

.todo-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.todo-item:hover {
  background: rgba(0, 0, 0, 0.02);
}

.todo-check {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid #D1D5DB;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all var(--transition-fast);
  color: #fff;
}

.todo-check--done {
  background: var(--color-success);
  border-color: var(--color-success);
}

.todo-text {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
}

.todo-text--done {
  text-decoration: line-through;
  color: var(--text-secondary);
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
    gap: 16px;
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
