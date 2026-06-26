<template>
  <div>
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <el-button @click="$router.back()"><el-icon><ArrowLeft /></el-icon> 返回</el-button>
      <h3 style="margin:0">订单详情 #{{ order.id }}</h3>
    </div>
    <el-card v-loading="loading">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="订单号">{{ order.id }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="order.status === '待发货' ? 'warning' : 'success'">{{ order.status }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="买家">{{ order.buyer_name }}</el-descriptions-item>
        <el-descriptions-item label="金额">{{ order.total_amount }}</el-descriptions-item>
        <el-descriptions-item label="商品">{{ order.product_name }}</el-descriptions-item>
        <el-descriptions-item label="数量">{{ order.quantity }}</el-descriptions-item>
        <el-descriptions-item label="下单时间">{{ order.created_at }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { getOrder } from '../api'

const route = useRoute()
const order = ref({})
const loading = ref(false)

onMounted(async () => {
  loading.value = true
  try {
    order.value = await getOrder(route.params.id)
  } catch { /* handled */ }
  finally { loading.value = false }
})
</script>
