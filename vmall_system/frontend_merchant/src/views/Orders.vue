<template>
  <div>
    <h3 style="margin-bottom:16px">订单管理</h3>
    <el-card>
      <el-table :data="list" v-loading="loading" style="width:100%">
        <el-table-column prop="id" label="订单号" width="80" />
        <el-table-column prop="buyer_name" label="买家" />
        <el-table-column prop="total_amount" label="金额" width="100" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="下单时间" width="170" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push(`/orders/${row.id}`)">详情</el-button>
            <el-button v-if="row.status === '待发货'" size="small" type="primary" @click="handleShip(row)">发货</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        style="margin-top:16px;justify-content:flex-end"
        v-model:current-page="page"
        :page-size="size"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchData"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getOrders, shipOrder } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const list = ref([])
const loading = ref(false)
const page = ref(1)
const size = ref(10)
const total = ref(0)

function statusType(s) {
  return s === '待发货' ? 'warning' : s === '已发货' ? 'success' : 'info'
}

async function fetchData() {
  loading.value = true
  try {
    const data = await getOrders({ page: page.value, size: size.value })
    list.value = data.items || []
    total.value = data.total || 0
  } catch { list.value = []; total.value = 0 }
  finally { loading.value = false }
}

async function handleShip(row) {
  try { await ElMessageBox.confirm(`确认将订单#${row.id}标记为已发货？`, '提示', { type: 'info' }) } catch { return }
  try {
    await shipOrder(row.id, { tracking_no: '' })
    ElMessage.success('已发货')
    fetchData()
  } catch { /* error shown by interceptor */ }
}

onMounted(fetchData)
</script>
