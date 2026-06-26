<template>
  <div>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <el-button @click="$router.push('/orders')"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
      <h3 style="margin:0">订单详情 {{ order.order_no }}</h3>
    </div>
    <el-card v-loading="loading" shadow="never" style="margin-bottom:16px">
      <template #header>基本信息</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="订单号">{{ order.order_no }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="statusTag(order.status)">{{ order.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="总金额">&yen;{{ order.total_amount }}</el-descriptions-item>
        <el-descriptions-item label="实付金额">&yen;{{ order.pay_amount }}</el-descriptions-item>
        <el-descriptions-item label="收货人">{{ order.receiver_name }}</el-descriptions-item>
        <el-descriptions-item label="下单时间">{{ order.created_at }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="order.items && order.items.length" shadow="never" style="margin-bottom:16px">
      <template #header>商品明细</template>
      <el-table :data="order.items" border stripe size="small">
        <el-table-column prop="sku_spec" label="规格" min-width="200" />
        <el-table-column prop="unit_price" label="单价" width="100"><template #default="{row}">&yen;{{ row.unit_price }}</template></el-table-column>
        <el-table-column prop="quantity" label="数量" width="80" />
      </el-table>
    </el-card>

    <el-card v-if="order.logistics" shadow="never" style="margin-bottom:16px">
      <template #header>物流信息</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="物流公司">{{ order.logistics.company }}</el-descriptions-item>
        <el-descriptions-item label="运单号">{{ order.logistics.tracking_no }}</el-descriptions-item>
        <el-descriptions-item label="物流状态">{{ order.logistics.status }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="order.status === 'paid'" shadow="never">
      <template #header>操作</template>
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="物流公司"><el-input v-model="shipForm.company" placeholder="顺丰速运" /></el-form-item>
        <el-form-item label="运单号"><el-input v-model="shipForm.tracking_no" placeholder="选填" /></el-form-item>
        <el-form-item><el-button type="primary" :loading="shipping" @click="doShip">确认发货</el-button></el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getOrder, shipOrder } from '../api'
import { ElMessage } from 'element-plus'

const route = useRoute()
const order = ref({})
const loading = ref(false)
const shipping = ref(false)
const shipForm = reactive({ company: '顺丰速运', tracking_no: '' })

function statusTag(s) {
  if (s === 'paid') return 'warning'
  if (s === 'shipped') return ''
  if (s === 'completed') return 'success'
  return 'info'
}

async function fetch() {
  loading.value = true
  try { order.value = (await getOrder(route.params.id)).data || {} }
  catch { /* */ }
  finally { loading.value = false }
}

async function doShip() {
  if (!shipForm.company) return ElMessage.warning('请输入物流公司')
  shipping.value = true
  try {
    await shipOrder(order.value.id, { company: shipForm.company, tracking_no: shipForm.tracking_no })
    ElMessage.success('发货成功')
    await fetch()
  } catch { /* */ }
  finally { shipping.value = false }
}

onMounted(fetch)
</script>
