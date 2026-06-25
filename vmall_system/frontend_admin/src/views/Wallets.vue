<template>
  <div>
    <h3 style="margin:0 0 16px">钱包管理</h3>
    <el-card style="margin-bottom:16px">
      <el-input v-model="keyword" placeholder="搜索买家（用户名/昵称）" style="width:260px" clearable @keyup.enter="fetch"/>
      <el-button type="primary" style="margin-left:8px" @click="fetch" :loading="loading">搜索</el-button>
    </el-card>
    <el-table :data="wallets" border stripe v-loading="loading">
      <el-table-column prop="username" label="用户名" width="120"/>
      <el-table-column prop="nickname" label="昵称" width="120"/>
      <el-table-column label="余额(元)" width="140"><template #default="{row}"><span style="font-size:18px;font-weight:bold;color:#67c23a">¥{{row.balance}}</span></template></el-table-column>
      <el-table-column label="累计充值" width="120"><template #default="{row}">¥{{row.total_recharged}}</template></el-table-column>
      <el-table-column label="累计消费" width="120"><template #default="{row}">¥{{row.total_spent}}</template></el-table-column>
      <el-table-column label="状态" width="80"><template #default="{row}"><el-tag :type="row.status===1?'success':'danger'" size="small">{{row.status===1?'正常':'冻结'}}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{row}">
          <el-button size="small" type="primary" @click="openRecharge(row)">充值</el-button>
          <el-button size="small" @click="openTx(row)">记录</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total,prev,next" :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch"/>

    <el-dialog v-model="showRecharge" title="充值" width="400px">
      <el-form :model="rechargeForm" label-width="100px">
        <el-form-item label="买家">{{ rechargeTarget?.nickname || rechargeTarget?.username }}</el-form-item>
        <el-form-item label="当前余额"><strong style="color:#67c23a;font-size:20px">¥{{ rechargeTarget?.balance }}</strong></el-form-item>
        <el-form-item label="充值金额" required>
          <el-input-number v-model="rechargeForm.amount" :min="0.01" :step="100" :precision="2" style="width:200px" size="large"/>
          <span style="margin-left:8px;color:#909399">元</span>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="rechargeForm.remark" placeholder="充值备注"/></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRecharge=false">取消</el-button>
        <el-button type="primary" :loading="recharging" @click="doRecharge">确认充值</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showTx" title="交易记录" width="550px">
      <el-timeline>
        <el-timeline-item v-for="t in transactions" :key="t.id"
          :timestamp="t.created_at?.slice(0,16)"
          :color="t.type==='recharge'?'#67c23a':t.type==='payment'?'#409eff':'#e6a23c'">
          <div style="display:flex;justify-content:space-between">
            <span>{{ t.remark || t.type }}</span>
            <span :style="{color:t.type==='recharge'?'#67c23a':'#f56c6c',fontWeight:'bold'}">
              {{ t.type==='recharge'?'+':'-' }}¥{{ Math.abs(t.amount) }}</span>
          </div>
          <span style="font-size:11px;color:#909399">余额: ¥{{ t.balance_before }} → ¥{{ t.balance_after }}</span>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-if="!transactions.length" description="暂无交易记录" :image-size="40"/>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getWallets, rechargeWallet, getWalletTx } from '../api'

const wallets = ref([]); const loading = ref(false); const total = ref(0); const page = ref(1); const keyword = ref('')
const showRecharge = ref(false); const showTx = ref(false)
const rechargeTarget = ref(null); const recharging = ref(false)
const rechargeForm = reactive({ amount: 100, remark: '' })
const transactions = ref([])

async function fetch() {
  loading.value = true
  try {
    const p = { page: page.value, page_size: 20 }
    if (keyword.value) p.keyword = keyword.value
    const r = await getWallets(p)
    wallets.value = r.data?.items || []
    total.value = r.data?.total || 0
  } finally { loading.value = false }
}

function openRecharge(row) {
  rechargeTarget.value = row
  rechargeForm.amount = 100
  rechargeForm.remark = ''
  showRecharge.value = true
}

async function doRecharge() {
  if (rechargeForm.amount <= 0) return ElMessage.warning('金额必须大于0')
  recharging.value = true
  try {
    await rechargeWallet(rechargeTarget.value.buyer_id, { amount: rechargeForm.amount, remark: rechargeForm.remark })
    showRecharge.value = false
    ElMessage.success(`充值 ¥${rechargeForm.amount} 成功`)
    fetch()
  } finally { recharging.value = false }
}

async function openTx(row) {
  showTx.value = true
  try {
    const r = await getWalletTx(row.buyer_id, { page: 1, page_size: 50 })
    transactions.value = r.data?.items || []
  } catch { /* */ }
}

onMounted(fetch)
</script>
