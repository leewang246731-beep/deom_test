<template>
  <div>
    <h3 style="margin-bottom:20px">工作台</h3>
    <el-row :gutter="20">
      <el-col :span="6" v-for="c in cards" :key="c.label">
        <el-card shadow="hover" style="text-align:center;cursor:pointer" @click="c.link && $router.push(c.link)">
          <div style="font-size:28px;color:#409eff">{{ c.value }}</div>
          <div style="color:#909399;margin-top:8px">{{ c.label }}</div>
        </el-card>
      </el-col>
    </el-row>
    <el-card style="margin-top:20px">
      <template #header>最近订单</template>
      <el-table :data="recentOrders" style="width:100%">
        <el-table-column prop="id" label="订单号" width="100" />
        <el-table-column prop="buyer_name" label="买家" />
        <el-table-column prop="total_amount" label="金额" />
        <el-table-column prop="status" label="状态" />
        <el-table-column prop="created_at" label="时间" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getDashboard } from '../api'
import { useMerchantStore } from '../stores/merchant'

const store = useMerchantStore()
const cards = ref([])
const recentOrders = ref([])

onMounted(async () => {
  try {
    const data = await getDashboard()
    const s = data.stats || {}
    cards.value = [
      { label: '商品总数', value: s.product_count || 0, link: '/products' },
      { label: '今日订单', value: s.today_orders || 0, link: '/orders' },
      { label: '待处理', value: s.pending_orders || 0, link: '/orders' },
      { label: '绑定状态', value: store.user?.saas_bound ? '已绑定' : '未绑定', link: '/binding' },
    ]
    recentOrders.value = data.recent_orders || []
  } catch { /* handled */ }
})
</script>
