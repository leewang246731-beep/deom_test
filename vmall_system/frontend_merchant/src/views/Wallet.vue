<template>
  <div>
    <h3 style="margin-bottom:20px">店铺收益</h3>
    <el-row :gutter="20">
      <el-col :span="6">
        <el-card shadow="hover" style="text-align:center">
          <div style="font-size:28px;" :style="{ color: wallet.balance < 0 ? '#f56c6c' : '#409eff' }">
            ¥{{ fmt(wallet.balance) }}
          </div>
          <div style="color:#909399;margin-top:8px">账户余额{{ wallet.balance < 0 ? '（平台垫付待补）' : '' }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" style="text-align:center">
          <div style="font-size:28px;color:#67c23a">¥{{ fmt(wallet.available) }}</div>
          <div style="color:#909399;margin-top:8px">可提现（扣冻结）</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" style="text-align:center">
          <div style="font-size:28px;color:#e6a23c">¥{{ fmt(wallet.frozen) }}</div>
          <div style="color:#909399;margin-top:8px">提现冻结中</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" style="text-align:center">
          <div style="font-size:28px;color:#909399">¥{{ fmt(wallet.total_revenue) }}</div>
          <div style="color:#909399;margin-top:8px">累计收入</div>
        </el-card>
      </el-col>
    </el-row>

    <div style="margin:20px 0">
      <el-button type="primary" :disabled="wallet.available <= 0" @click="openWithdraw">申请提现</el-button>
      <span style="color:#909399;margin-left:12px">累计提现 ¥{{ fmt(wallet.total_withdrawn) }} · 累计退款 ¥{{ fmt(wallet.total_refunded) }}</span>
    </div>

    <el-card>
      <template #header>
        <el-radio-group v-model="tab" @change="reload">
          <el-radio-button label="transactions">资金流水</el-radio-button>
          <el-radio-button label="withdrawals">提现记录</el-radio-button>
        </el-radio-group>
      </template>

      <el-table v-if="tab === 'transactions'" :data="txList" style="width:100%">
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="txTagType(row.type)" size="small">{{ txLabel(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="金额" width="140">
          <template #default="{ row }">
            <span :style="{ color: inflow(row.type) ? '#67c23a' : '#f56c6c' }">
              {{ inflow(row.type) ? '+' : '-' }}¥{{ fmt(row.amount) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="balance_after" label="变动后余额" width="140">
          <template #default="{ row }">¥{{ fmt(row.balance_after) }}</template>
        </el-table-column>
        <el-table-column prop="order_no" label="关联订单" width="160" />
        <el-table-column prop="remark" label="备注" />
        <el-table-column prop="created_at" label="时间" width="180" />
      </el-table>

      <el-table v-else :data="wdList" style="width:100%">
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column label="金额" width="140">
          <template #default="{ row }">¥{{ fmt(row.amount) }}</template>
        </el-table-column>
        <el-table-column prop="account_type" label="收款方式" width="120" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="wdTagType(row.status)" size="small">{{ wdLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="reject_reason" label="驳回原因" />
        <el-table-column prop="created_at" label="申请时间" width="180" />
      </el-table>

      <el-pagination style="margin-top:16px" layout="prev, pager, next" :total="total"
        :page-size="pageSize" :current-page="page" @current-change="onPage" />
    </el-card>

    <el-dialog v-model="dialog" title="申请提现" width="460px">
      <el-form label-width="90px">
        <el-form-item label="可提现">¥{{ fmt(wallet.available) }}</el-form-item>
        <el-form-item label="提现金额">
          <el-input-number v-model="form.amount" :min="1" :max="wallet.available" :precision="2" />
        </el-form-item>
        <el-form-item label="收款方式">
          <el-select v-model="form.account_type">
            <el-option label="银行卡" value="bank" />
            <el-option label="支付宝" value="alipay" />
            <el-option label="微信" value="wechat" />
          </el-select>
        </el-form-item>
        <el-form-item label="收款账户">
          <el-input v-model="form.account" placeholder="账号/卡号" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitWithdraw">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getWallet, getWalletTransactions, applyWithdraw, getMyWithdrawals } from '../api'

const wallet = ref({ balance: 0, available: 0, frozen: 0, total_revenue: 0, total_withdrawn: 0, total_refunded: 0 })
const tab = ref('transactions')
const txList = ref([])
const wdList = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const dialog = ref(false)
const submitting = ref(false)
const form = ref({ amount: 0, account_type: 'alipay', account: '' })

// 兼容两种响应：拦截器可能返回信封 {code,msg,data} 或已剥壳的内层 data
const unwrap = (body) => (body && body.code !== undefined && 'data' in body) ? body.data : body
const fmt = (v) => Number(v || 0).toFixed(2)
const inflow = (t) => t === 'order_income'
const txLabel = (t) => ({ order_income: '订单收入', refund_out: '退款支出', withdraw: '提现', adjustment: '调整' }[t] || t)
const txTagType = (t) => ({ order_income: 'success', refund_out: 'danger', withdraw: 'warning' }[t] || 'info')
const wdLabel = (s) => ({ pending: '待审核', approved: '已通过', rejected: '已驳回', completed: '已打款' }[s] || s)
const wdTagType = (s) => ({ pending: 'warning', completed: 'success', approved: 'success', rejected: 'danger' }[s] || 'info')

async function loadWallet() {
  try { wallet.value = unwrap(await getWallet()) } catch { /* handled */ }
}

async function reload() {
  page.value = 1
  await loadList()
}

async function loadList() {
  try {
    if (tab.value === 'transactions') {
      const r = unwrap(await getWalletTransactions({ page: page.value, page_size: pageSize }))
      txList.value = r.items || []
      total.value = r.total || 0
    } else {
      const r = unwrap(await getMyWithdrawals({ page: page.value, page_size: pageSize }))
      wdList.value = r.items || []
      total.value = r.total || 0
    }
  } catch { /* handled */ }
}

function onPage(p) { page.value = p; loadList() }

function openWithdraw() {
  form.value = { amount: Math.min(wallet.value.available, wallet.value.available), account_type: 'alipay', account: '' }
  dialog.value = true
}

async function submitWithdraw() {
  if (!form.value.amount || form.value.amount <= 0) return ElMessage.warning('请输入提现金额')
  if (!form.value.account) return ElMessage.warning('请输入收款账户')
  submitting.value = true
  try {
    await applyWithdraw(form.value)
    ElMessage.success('提现申请已提交')
    dialog.value = false
    await loadWallet()
    if (tab.value === 'withdrawals') await loadList()
  } catch { /* handled */ } finally { submitting.value = false }
}

onMounted(async () => { await loadWallet(); await loadList() })
</script>
