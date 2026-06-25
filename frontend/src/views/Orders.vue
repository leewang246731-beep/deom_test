<template>
  <div>
    <div style="margin-bottom:16px;display:flex;justify-content:space-between">
      <h3 style="margin:0">订单中心</h3>
      <el-button type="warning" @click="handleRemind" :loading="reminding">一键催单（未付款）</el-button>
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
      <template v-if="detail">
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getOrders, getShops, refundOrder, remindPayment } from '../api'
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
  } catch { /* */ } finally { loading.value = false }
}

function showDetail(row) { detail.value = row; detailVisible.value = true }
async function handleRefund(id) { try { await refundOrder(id); ElMessage.success('售后完成'); fetch() } catch { /* */ } }
async function handleRemind() {
  reminding.value = true
  try {
    const res = await remindPayment(1) // shop 1 for demo
    ElMessage.success(`已生成 ${res.data?.count || 0} 条催单话术`)
  } catch { /* */ } finally { reminding.value = false }
}

onMounted(async () => {
  try { const res = await getShops(); shops.value = res.data || [] } catch { /* ok */ }
  fetch()
})
</script>
