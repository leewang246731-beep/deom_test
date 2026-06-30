<template>
  <div>
    <h3 style="margin:0 0 16px">商户提现审核</h3>
    <el-card style="margin-bottom:16px">
      <el-radio-group v-model="status" @change="reload">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button label="pending">待审核</el-radio-button>
        <el-radio-button label="completed">已打款</el-radio-button>
        <el-radio-button label="rejected">已驳回</el-radio-button>
      </el-radio-group>
    </el-card>
    <el-table :data="list" border stripe v-loading="loading">
      <el-table-column prop="id" label="编号" width="70" />
      <el-table-column prop="shop_name" label="商户" width="140" />
      <el-table-column label="金额" width="110"><template #default="{row}">¥{{ fmt(row.amount) }}</template></el-table-column>
      <el-table-column prop="account_type" label="收款方式" width="90" />
      <el-table-column prop="account_info" label="收款账户" />
      <el-table-column label="状态" width="90"><template #default="{row}">
        <el-tag :type="tag(row.status)" size="small">{{ label(row.status) }}</el-tag></template></el-table-column>
      <el-table-column prop="created_at" label="申请时间" width="170" />
      <el-table-column label="操作" width="160"><template #default="{row}">
        <template v-if="row.status==='pending'">
          <el-button size="small" type="success" @click="approve(row)">通过打款</el-button>
          <el-button size="small" type="danger" @click="openReject(row)">驳回</el-button>
        </template>
        <span v-else style="color:#909399">{{ row.reject_reason || '—' }}</span>
      </template></el-table-column>
    </el-table>
    <el-pagination style="margin-top:16px;justify-content:flex-end" background layout="total,prev,next"
      :total="total" :page-size="20" v-model:current-page="page" @current-change="fetch" />

    <el-dialog v-model="rejectDlg" title="驳回提现" width="420px">
      <el-form><el-form-item label="驳回原因"><el-input v-model="rejectReason" type="textarea" :rows="3" /></el-form-item></el-form>
      <template #footer><el-button @click="rejectDlg=false">取消</el-button>
        <el-button type="danger" @click="doReject">确认驳回</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getWithdrawals, approveWithdrawal, rejectWithdrawal } from '../api'

const list = ref([]); const loading = ref(false); const total = ref(0); const page = ref(1)
const status = ref('pending')
const rejectDlg = ref(false); const rejectReason = ref(''); const rejecting = ref(null)

const fmt = (v) => Number(v || 0).toFixed(2)
const label = (s) => ({ pending: '待审核', completed: '已打款', approved: '已通过', rejected: '已驳回' }[s] || s)
const tag = (s) => ({ pending: 'warning', completed: 'success', approved: 'success', rejected: 'danger' }[s] || 'info')

function reload() { page.value = 1; fetch() }

async function fetch() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: 20 }
    if (status.value) params.status = status.value
    const res = await getWithdrawals(params)
    list.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch { list.value = []; total.value = 0 } finally { loading.value = false }
}

async function approve(row) {
  try { await ElMessageBox.confirm(`确认对「${row.shop_name}」提现 ¥${fmt(row.amount)} 打款？`, '提现审核', { type: 'warning' }) } catch { return }
  try { await approveWithdrawal(row.id); ElMessage.success('已通过并打款'); fetch() } catch { /* handled */ }
}

function openReject(row) { rejecting.value = row; rejectReason.value = ''; rejectDlg.value = true }
async function doReject() {
  if (!rejecting.value) return
  try { await rejectWithdrawal(rejecting.value.id, { reason: rejectReason.value }); ElMessage.success('已驳回'); rejectDlg.value = false; fetch() } catch { /* handled */ }
}

onMounted(fetch)
</script>
