<template>
  <div>
    <h3 style="margin:0 0 16px">操作审计日志</h3>

    <el-card style="margin-bottom:16px">
      <el-row :gutter="12">
        <el-col :span="5">
          <el-select v-model="filters.action" placeholder="操作类型" clearable style="width:100%" @change="fetch">
            <el-option label="创建" value="create" />
            <el-option label="更新" value="update" />
            <el-option label="删除" value="delete" />
            <el-option label="状态变更" value="status_change" />
          </el-select>
        </el-col>
        <el-col :span="5">
          <el-select v-model="filters.target_type" placeholder="目标类型" clearable style="width:100%" @change="fetch">
            <el-option label="工单" value="ticket" />
            <el-option label="商品" value="product" />
            <el-option label="用户" value="user" />
            <el-option label="订单" value="order" />
            <el-option label="店铺" value="shop" />
          </el-select>
        </el-col>
        <el-col :span="4"><el-button @click="resetFilters">重置</el-button></el-col>
      </el-row>
    </el-card>

    <el-table :data="logs" border stripe v-loading="loading" empty-text="暂无记录">
      <el-table-column prop="username" label="操作人" width="110" />
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-tag :type="actionTag(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="目标" width="140">
        <template #default="{ row }">{{ row.target_type ? targetLabel(row.target_type) + ' #' + row.target_id : '-' }}</template>
      </el-table-column>
      <el-table-column prop="detail_json" label="详情" min-width="200" show-overflow-tooltip />
      <el-table-column prop="ip" label="IP" width="130" />
      <el-table-column prop="created_at" label="时间" width="170" />
    </el-table>

    <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total, prev, pager, next" :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch" />
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { getAuditLogs } from '../api'

const logs = ref([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const filters = reactive({ action: '', target_type: '' })

function actionLabel(a) {
  const m = { create: '创建', update: '更新', delete: '删除', status_change: '状态变更', login: '登录' }
  return m[a] || a
}
function actionTag(a) {
  const m = { create: 'success', update: 'warning', delete: 'danger', status_change: 'info', login: '' }
  return m[a] || ''
}
function targetLabel(t) {
  const m = { ticket: '工单', product: '商品', user: '用户', order: '订单', shop: '店铺' }
  return m[t] || t
}

async function fetch() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (filters.action) params.action = filters.action
    if (filters.target_type) params.target_type = filters.target_type
    const res = await getAuditLogs(params)
    logs.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch {
    logs.value = []
    total.value = 0
  } finally { loading.value = false }
}

function resetFilters() {
  Object.assign(filters, { action: '', target_type: '' })
  page.value = 1
  fetch()
}

fetch()
</script>
