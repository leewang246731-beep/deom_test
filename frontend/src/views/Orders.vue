<template>
  <div>
    <div style="margin-bottom:16px;display:flex;justify-content:space-between">
      <h3 style="margin:0">订单中心</h3>
      <div>
        <el-button @click="handleExport">导出CSV</el-button>
        <el-button type="warning" @click="handleRemind" :loading="reminding">一键催单（未付款）</el-button>
      </div>
    </div>
    <el-card style="margin-bottom:16px">
      <el-row :gutter="12">
        <el-col :span="4"><el-select v-model="filters.shop_id" placeholder="店铺" clearable style="width:100%"><el-option v-for="s in shops" :key="s.id" :label="s.shop_name" :value="s.id" /></el-select></el-col>
        <el-col :span="4"><el-select v-model="filters.status" placeholder="状态" clearable style="width:100%"><el-option v-for="s in statuses" :key="s" :label="s" :value="s" /></el-select></el-col>
        <el-col :span="4"><el-button type="primary" @click="fetch">筛选</el-button></el-col>
      </el-row>
    </el-card>
    <el-table :data="orders" border stripe v-loading="loading" empty-text="暂无订单">
      <el-table-column prop="buyer_nick" label="买家" width="100" />
      <el-table-column label="金额" width="100"><template #default="{ row }">¥{{ row.pay_amount }}</template></el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }"><el-tag :type="statusTag(row.status)" size="small">{{ row.status }}</el-tag></template>
      </el-table-column>
      <el-table-column label="商品" min-width="200">
        <template #default="{ row }">{{ (row.sku_details_json || []).map?.(s => s.title).join(' / ') || row.platform_order_id }}</template>
      </el-table-column>
      <el-table-column label="收货人" width="100"><template #default="{ row }">{{ row.receiver_name }}</template></el-table-column>
      <el-table-column label="下单时间" width="170"><template #default="{ row }">{{ row.created_at }}</template></el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="showDetail(row)">详情</el-button>
          <el-popconfirm v-if="row.status !== 'refunded' && row.status !== 'refunding'" title="确认售后？" @confirm="handleRefund(row.id)">
            <template #reference><el-button size="small" type="danger" text>售后</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next" :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch" />

    <el-dialog v-model="detailVisible" title="订单详情" width="600px">
      <template v-if="detailLoading"><el-skeleton :rows="5" animated /></template>
      <template v-else-if="detail">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="买家">{{ detail.buyer_nick }}</el-descriptions-item>
          <el-descriptions-item label="状态"><el-tag :type="statusTag(detail.status)" size="small">{{ detail.status }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="总金额">¥{{ detail.total_amount }}</el-descriptions-item>
          <el-descriptions-item label="实付">¥{{ detail.pay_amount }}</el-descriptions-item>
          <el-descriptions-item label="收货人">{{ detail.receiver_name }}</el-descriptions-item>
          <el-descriptions-item label="电话">{{ detail.receiver_phone }}</el-descriptions-item>
          <el-descriptions-item label="地址" :span="2">{{ detail.receiver_address }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-dialog>

    <!-- 催单话术结果弹窗 (BUG-004) -->
    <el-dialog v-model="remindVisible" title="催单话术" width="650px">
      <el-alert v-if="!reminders.length" type="info" :closable="false" title="当前无待催付订单" />
      <div v-else v-for="(r, i) in reminders" :key="i" style="padding:10px;margin-bottom:8px;background:#fafafa;border-radius:6px;border:1px solid #ebeef5">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
          <strong style="font-size:13px">{{ r.buyer_nick }}</strong>
          <el-tag size="small" type="warning">{{ r.product_title }}</el-tag>
        </div>
        <p style="margin:0;font-size:13px;line-height:1.6;color:#303133">{{ r.script }}</p>
        <div style="margin-top:4px;display:flex;gap:6px;justify-content:flex-end">
          <el-button size="small" plain @click="navigator.clipboard.writeText(r.script).then(()=>ElMessage.success('已复制'))">复制话术</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getOrders, getOrder, getShops, refundOrder, remindPayment, exportCSV } from '../api'
import { ElMessage } from 'element-plus'

const orders = ref([])
const shops = ref([])
const loading = ref(false)
const reminding = ref(false)
const total = ref(0)
const page = ref(1)
const filters = reactive({ shop_id: null, status: null })
const detailVisible = ref(false)
const detail = ref(null)
const detailLoading = ref(false)
const remindVisible = ref(false)
const reminders = ref([])
const statuses = ['pending', 'paid', 'shipped', 'completed', 'refunding', 'refunded']

function statusTag(s) {
  const map = { pending: 'warning', paid: '', shipped: 'primary', completed: 'success', refunding: 'warning', refunded: 'info' }
  return map[s] || ''
}

async function fetch() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (filters.shop_id) params.shop_id = filters.shop_id
    if (filters.status) params.status = filters.status
    const res = await getOrders(params)
    orders.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch {
    orders.value = []
    total.value = 0
  } finally { loading.value = false }
}

async function showDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  try {
    const res = await getOrder(row.id)
    detail.value = res.data || row
  } catch {
    detail.value = row // fallback to row data
  } finally { detailLoading.value = false }
}

async function handleRefund(id) {
  try {
    await refundOrder(id)
    ElMessage.success('售后处理完成')
    fetch()
  } catch {
    // error shown by interceptor
  }
}

async function handleRemind() {
  reminding.value = true
  try {
    const shopId = filters.shop_id || shops.value[0]?.id
    if (!shopId) { ElMessage.warning('请先选择店铺'); reminding.value = false; return }
    const res = await remindPayment(shopId)
    reminders.value = res.data?.reminders || []
    remindVisible.value = true
    const count = reminders.value.length
    if (count > 0) {
      ElMessage.success(`已生成 ${count} 条催单话术`)
    } else {
      ElMessage.info('当前无待付款订单')
    }
  } catch {
    // error shown by interceptor
  } finally { reminding.value = false }
}

function handleExport() {
  const p = {}
  if (filters.shop_id) p.shop_id = filters.shop_id
  if (filters.status) p.status = filters.status
  exportCSV('orders', p)
}

onMounted(async () => {
  try {
    const res = await getShops()
    shops.value = res.data || []
  } catch {
    // shops list not critical
  }
  fetch()
})
</script>
