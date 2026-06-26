<template>
  <div>
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h3 style="margin:0">工作台</h3>
      <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始" end-placeholder="结束" size="small" style="width:260px" @change="onDateChange" />
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" style="text-align:center;padding:60px">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <p style="color:#909399;margin-top:12px">数据加载中...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="loadError" style="text-align:center;padding:60px">
      <el-empty description="数据加载失败">
        <el-button type="primary" @click="retryAll">重新加载</el-button>
      </el-empty>
      <p style="color:#c0c4cc;font-size:12px;margin-top:8px">{{ loadError }}</p>
    </div>

    <template v-else>
      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="6" v-for="card in cards" :key="card.title" style="margin-bottom:8px">
          <el-card shadow="hover">
            <div style="display:flex;align-items:center;justify-content:space-between">
              <div>
                <p style="color:#909399;font-size:13px;margin:0">{{ card.title }}</p>
                <h2 style="margin:6px 0 0;font-size:24px;color:#303133">{{ card.value }}</h2>
              </div>
              <el-icon :size="36" :color="card.color"><component :is="card.icon" /></el-icon>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="12">
          <el-card><template #header><span>订单趋势</span><el-segmented v-if="echartsReady" v-model="trendRange" :options="['day','week','month']" style="margin-left:8px" @change="fetchTrend" size="small"/></template>
            <div v-if="echartsReady" ref="chartDom" style="height:280px"/>
            <div v-else style="height:280px;display:flex;align-items:center;justify-content:center;color:#c0c4cc;font-size:13px">图表组件加载中...</div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card><template #header>工单趋势</template>
            <div v-if="echartsReady" ref="ticketChartDom" style="height:280px"/>
            <div v-else style="height:280px;display:flex;align-items:center;justify-content:center;color:#c0c4cc;font-size:13px">图表组件加载中...</div>
          </el-card>
        </el-col>
      </el-row>

      <el-row :gutter="16" style="margin-bottom:16px">
        <el-col :span="14">
          <el-card><template #header>客服统计</template>
            <el-table :data="serviceStats?.per_service || []" size="small"><el-table-column prop="display_name" label="客服"/><el-table-column prop="handled" label="处理量"/><el-table-column label="角色"><template #default="{row}">{{row?.role}}</template></el-table-column></el-table>
            <div style="margin-top:8px;color:#909399;font-size:13px">AI采纳率: {{ ((serviceStats?.ai_adoption_rate || 0) * 100).toFixed(1) }}% | 待回复: {{ serviceStats?.pending || 0 }} | 已回复: {{ serviceStats?.replied || 0 }}</div>
          </el-card>
        </el-col>
        <el-col :span="10">
          <el-card><template #header>热门商品 TOP 5</template>
            <div v-for="(h,i) in hotProducts" :key="i" style="display:flex;align-items:center;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f0f0f0"><span>{{i+1}}. {{ h?.product?.title || '未知商品' }}</span><el-tag size="small" type="danger">¥{{ h?.product?.price || 0 }}</el-tag></div>
            <el-empty v-if="!hotProducts?.length" description="暂无数据" :image-size="50"/>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { Loading } from '@element-plus/icons-vue'
import { getMetrics, getOrderTrend, getServiceStats, getHotProducts, getShops, getConversations, getTicketStats, getTicketTrend } from '../api'

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

// 动态加载 ECharts — 失败时不阻塞页面渲染
let _echarts = null
async function loadEcharts() {
  if (_echarts !== null) return _echarts
  try {
    const mod = await import('echarts')
    _echarts = mod.default || mod
    echartsReady.value = true
    return _echarts
  } catch (e) {
    console.warn('[Dashboard] ECharts 加载失败，图表不可用:', e.message)
    _echarts = false
    return null
  }
}

function disposeCharts() {
  try { if (chart) { chart.dispose(); chart = null } } catch { /* */ }
  try { if (tChart) { tChart.dispose(); tChart = null } } catch { /* */ }
}
onUnmounted(disposeCharts)

const cards = reactive([
  { title: '总订单量', value: 0, icon: 'Document', color: '#409eff' },
  { title: '待处理工单', value: 0, icon: 'Tickets', color: '#e6a23c' },
  { title: '待回复会话', value: 0, icon: 'ChatDotRound', color: '#409eff' },
  { title: '超时工单', value: 0, icon: 'WarningFilled', color: '#f56c6c' },
  { title: 'AI 采纳率', value: '0%', icon: 'Cpu', color: '#67c23a' },
  { title: '活跃店铺', value: 0, icon: 'Shop', color: '#909399' },
  { title: '工单总数', value: 0, icon: 'DocumentChecked', color: '#e6a23c' },
  { title: '今日订单', value: 0, icon: 'TrendCharts', color: '#67c23a' },
])

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
  const [m, shops, convs, stats, hot, tStats] = await Promise.all([
    getMetrics(params).catch(() => null),
    getShops().catch(() => null),
    getConversations({ handled_status: 'pending' }).catch(() => null),
    getServiceStats().catch(() => null),
    getHotProducts({ top_k: 5 }).catch(() => null),
    getTicketStats().catch(() => null),
  ])
  const md = m?.data || {}
  const sd = stats?.data || {}
  const ts = tStats?.data || {}
  cards[0].value = md.total_orders ?? 0
  cards[1].value = ts.pending ?? 0
  cards[2].value = md.pending_conversations ?? convs?.data?.total ?? 0
  cards[3].value = ts.sla_breached ?? 0
  cards[4].value = ((md.ai_adoption_rate || 0) * 100).toFixed(0) + '%'
  cards[5].value = md.active_shops ?? shops?.data?.length ?? 0
  cards[6].value = ts.total ?? 0
  cards[7].value = md.today_orders ?? 0
  hotProducts.value = (hot?.data?.recommendations || []).slice(0, 5)
  serviceStats.value = sd
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
    chart.setOption({ tooltip: { trigger: 'axis' }, xAxis: { type: 'category', data: pts.map(p => p?.date?.slice(5) || '') }, yAxis: { type: 'value' }, series: [{ name: '订单数', type: 'line', smooth: true, data: pts.map(p => p?.count || 0), areaStyle: { opacity: .1 } }] })
  } catch { /* */ }
}

onMounted(async () => {
  // 数据加载和 ECharts 加载并行进行，互不阻塞
  await retryAll()
  const echarts = await loadEcharts()
  if (!echarts) return  // ECharts 不可用，图表区显示占位文字
  try {
    await nextTick()
    if (chartDom.value) { chart = echarts.init(chartDom.value); fetchTrend() }
    if (ticketChartDom.value) {
      tChart = echarts.init(ticketChartDom.value)
      try {
        const res = await getTicketTrend('week').catch(() => null)
        const pts = res?.data?.points || []
        tChart.setOption({ tooltip: { trigger: 'axis' }, xAxis: { type: 'category', data: pts.map(p => p?.date?.slice(5) || '') }, yAxis: { type: 'value' }, series: [{ name: '工单数', type: 'bar', data: pts.map(p => p?.count || 0) }] })
      } catch { /* */ }
    }
  } catch { /* */ }
})
</script>
