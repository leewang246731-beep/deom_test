<template>
  <div>
    <h3 style="margin:0 0 16px">商户钱包监控</h3>
    <el-card style="margin-bottom:16px">
      <el-checkbox v-model="negativeOnly" @change="reload">只看负余额（平台垫付/风险）</el-checkbox>
    </el-card>
    <el-table :data="list" border stripe v-loading="loading">
      <el-table-column prop="merchant_id" label="商户ID" width="90" />
      <el-table-column prop="shop_name" label="商户" width="160" />
      <el-table-column label="余额" width="120"><template #default="{row}">
        <span :style="{ color: row.negative ? '#f56c6c' : '#303133', fontWeight: row.negative ? 'bold' : 'normal' }">
          ¥{{ fmt(row.balance) }}</span></template></el-table-column>
      <el-table-column label="可用" width="110"><template #default="{row}">¥{{ fmt(row.available) }}</template></el-table-column>
      <el-table-column label="冻结" width="100"><template #default="{row}">¥{{ fmt(row.frozen) }}</template></el-table-column>
      <el-table-column label="累计收入" width="120"><template #default="{row}">¥{{ fmt(row.total_revenue) }}</template></el-table-column>
      <el-table-column label="累计提现" width="120"><template #default="{row}">¥{{ fmt(row.total_withdrawn) }}</template></el-table-column>
      <el-table-column label="累计退款" width="120"><template #default="{row}">¥{{ fmt(row.total_refunded) }}</template></el-table-column>
      <el-table-column label="风险" width="90"><template #default="{row}">
        <el-tag v-if="row.negative" type="danger" size="small">负余额</el-tag>
        <el-tag v-else type="success" size="small">正常</el-tag></template></el-table-column>
      <el-table-column label="操作" width="100"><template #default="{row}">
        <el-button size="small" text @click="openTx(row)">流水</el-button></template></el-table-column>
    </el-table>
    <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total,prev,next"
      :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch" />

    <el-dialog v-model="txDlg" :title="`商户#${txMid} 钱包流水`" width="640px">
      <el-table :data="txList" border size="small">
        <el-table-column label="类型" width="110"><template #default="{row}">
          <el-tag :type="txTag(row.type)" size="small">{{ txLabel(row.type) }}</el-tag></template></el-table-column>
        <el-table-column label="金额" width="120"><template #default="{row}">¥{{ fmt(row.amount) }}</template></el-table-column>
        <el-table-column label="变动后" width="120"><template #default="{row}">¥{{ fmt(row.balance_after) }}</template></el-table-column>
        <el-table-column prop="order_no" label="订单" width="150" />
        <el-table-column prop="remark" label="备注" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getMerchantWallets, getMerchantWalletTx } from '../api'

const list = ref([]); const loading = ref(false); const total = ref(0); const page = ref(1)
const negativeOnly = ref(false)
const txDlg = ref(false); const txList = ref([]); const txMid = ref(null)

const fmt = (v) => Number(v || 0).toFixed(2)
const txLabel = (t) => ({ order_income: '订单收入', refund_out: '退款支出', withdraw: '提现', adjustment: '调整' }[t] || t)
const txTag = (t) => ({ order_income: 'success', refund_out: 'danger', withdraw: 'warning' }[t] || 'info')

function reload() { page.value = 1; fetch() }

async function fetch() {
  loading.value = true
  try {
    const res = await getMerchantWallets({ page: page.value, page_size: 20, negative_only: negativeOnly.value })
    list.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch { list.value = []; total.value = 0 } finally { loading.value = false }
}

async function openTx(row) {
  txMid.value = row.merchant_id; txDlg.value = true; txList.value = []
  try { const res = await getMerchantWalletTx(row.merchant_id, { page: 1, page_size: 50 }); txList.value = res.data?.items || [] } catch { /* handled */ }
}

onMounted(fetch)
</script>
