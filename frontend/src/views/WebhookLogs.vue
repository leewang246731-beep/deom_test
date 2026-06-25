<template>
  <div>
    <h3 style="margin:0 0 16px">Webhook 事件监控</h3>

    <el-card style="margin-bottom:16px">
      <el-row :gutter="12">
        <el-col :span="5">
          <el-select v-model="filters.event_type" placeholder="事件类型" clearable style="width:100%" @change="fetch">
            <el-option label="订单已付款" value="ORDER_PAID" />
            <el-option label="订单已发货" value="ORDER_SHIPPED" />
            <el-option label="订单已完成" value="ORDER_COMPLETED" />
            <el-option label="物流更新" value="LOGISTICS_UPDATED" />
            <el-option label="退款成功" value="REFUND_SUCCESS" />
            <el-option label="新消息" value="NEW_MESSAGE" />
            <el-option label="售后创建" value="AFTER_SALE_CREATED" />
          </el-select>
        </el-col>
        <el-col :span="4">
          <el-select v-model="filters.status" placeholder="状态" clearable style="width:100%" @change="fetch">
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
            <el-option label="重试中" value="retrying" />
          </el-select>
        </el-col>
        <el-col :span="4"><el-button @click="resetFilters">重置</el-button></el-col>
      </el-row>
    </el-card>

    <el-table :data="logs" border stripe v-loading="loading" empty-text="暂无记录">
      <el-table-column prop="event_type" label="事件类型" width="150" />
      <el-table-column prop="source_shop_id" label="店铺ID" width="80" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failed' ? 'danger' : 'warning'" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="response_code" label="响应码" width="80" />
      <el-table-column label="耗时" width="90">
        <template #default="{ row }">{{ row.duration_ms ? row.duration_ms + 'ms' : '-' }}</template>
      </el-table-column>
      <el-table-column prop="payload_json" label="载荷" min-width="180" show-overflow-tooltip />
      <el-table-column prop="created_at" label="时间" width="170" />
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'failed'" size="small" text type="warning" @click="handleRetry(row.id)">重试</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next" :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch" />
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { getWebhookLogs, retryWebhook } from '../api'
import { ElMessage } from 'element-plus'

const logs = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const filters = reactive({ event_type: '', status: '' })

async function fetch() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (filters.event_type) params.event_type = filters.event_type
    if (filters.status) params.status = filters.status
    const res = await getWebhookLogs(params)
    logs.value = res.data?.items || []
    total.value = res.data?.total || 0
  } finally { loading.value = false }
}

function resetFilters() {
  Object.assign(filters, { event_type: '', status: '' })
  page.value = 1
  fetch()
}

async function handleRetry(id) {
  try { await retryWebhook(id); ElMessage.success('已加入重试队列'); fetch() } catch {}
}

fetch()
</script>
