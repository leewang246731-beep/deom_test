<template>
  <div style="max-width:600px;margin:0 auto;padding:16px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px">
      <h2 style="margin:0">个人中心</h2>
      <el-button text @click="$router.push('/home')">返回首页</el-button>
    </div>

    <!-- 个人信息卡片 -->
    <el-card shadow="hover" style="margin-bottom:16px">
      <template #header><span style="font-weight:bold">👤 个人信息</span>
        <el-button size="small" text style="float:right" @click="showEdit=true">编辑</el-button>
      </template>
      <el-descriptions :column="1" border size="small" v-loading="loading">
        <el-descriptions-item label="昵称">{{ profile.nickname || '-' }}</el-descriptions-item>
        <el-descriptions-item label="用户名">{{ profile.username || '-' }}</el-descriptions-item>
        <el-descriptions-item label="手机号">{{ profile.phone || '-' }}</el-descriptions-item>
        <el-descriptions-item label="注册来源">{{ profile.source || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 钱包卡片 -->
    <el-card shadow="hover" style="margin-bottom:16px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:#fff" v-loading="loading">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
          <p style="margin:0;font-size:13px;opacity:0.85">💰 我的钱包
            <span v-if="wallet.status===0" style="color:#f56c6c;font-size:11px">(已冻结)</span>
          </p>
          <h1 style="margin:8px 0;font-size:36px">¥{{ walletBalance }}</h1>
          <p style="margin:0;font-size:12px;opacity:0.7">
            累计充值 ¥{{ fmt(wallet.total_recharged) }}
            &nbsp;|&nbsp; 累计消费 ¥{{ fmt(wallet.total_spent) }}
          </p>
        </div>
        <el-icon :size="56" color="rgba(255,255,255,0.3)"><Wallet /></el-icon>
      </div>
    </el-card>

    <!-- 快捷入口 -->
    <el-row :gutter="12" style="margin-bottom:16px">
      <el-col :span="8">
        <el-card shadow="hover" style="text-align:center;cursor:pointer" @click="$router.push('/orders')">
          <el-icon :size="28" color="#409eff"><Document /></el-icon>
          <p style="margin:6px 0 0;font-size:13px">我的订单</p>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" style="text-align:center;cursor:pointer" @click="showTx=true;fetchTx()">
          <el-icon :size="28" color="#67c23a"><List /></el-icon>
          <p style="margin:6px 0 0;font-size:13px">交易记录</p>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" style="text-align:center;cursor:pointer" @click="logout">
          <el-icon :size="28" color="#f56c6c"><SwitchButton /></el-icon>
          <p style="margin:6px 0 0;font-size:13px">退出登录</p>
        </el-card>
      </el-col>
    </el-row>

    <!-- 交易记录对话框 -->
    <el-dialog v-model="showTx" title="交易记录" width="500px">
      <div v-loading="txLoading">
        <el-timeline>
          <el-timeline-item v-for="t in transactions" :key="t.id"
            :timestamp="t.created_at?.slice(0,16)"
            :color="t.type==='recharge'?'#67c23a':t.type==='payment'?'#409eff':'#e6a23c'"
            :hollow="false">
            <div style="display:flex;justify-content:space-between">
              <span>{{ t.remark || typeLabel(t.type) }}</span>
              <span :style="{color:t.type==='recharge'?'#67c23a':'#f56c6c',fontWeight:'bold'}">
                {{ t.type==='recharge'?'+':'-' }}¥{{ fmt(Math.abs(t.amount)) }}
              </span>
            </div>
            <span style="font-size:11px;color:#909399">余额: ¥{{ fmt(t.balance_after) }}</span>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-if="!transactions.length" description="暂无交易记录" :image-size="40"/>
      </div>
    </el-dialog>

    <!-- 编辑个人信息 -->
    <el-dialog v-model="showEdit" title="编辑个人信息" width="400px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="昵称"><el-input v-model="editForm.nickname"/></el-form-item>
        <el-form-item label="手机号"><el-input v-model="editForm.phone"/></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEdit=false">取消</el-button>
        <el-button type="primary" @click="doUpdate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({ baseURL: '/api/v1', timeout: 15000 })
http.interceptors.request.use(c => {
  const t = localStorage.getItem('vmall_token')
  if (t) c.headers.Authorization = `Bearer ${t}`
  return c
})
http.interceptors.response.use(
  r => r.data,
  err => { ElMessage.error('请求失败: ' + (err.response?.data?.detail?.msg || err.message)); return Promise.reject(err) }
)

const router = useRouter()
const auth = useAuthStore()
const loading = ref(true)
const txLoading = ref(false)
const profile = reactive({
  id: 0, username: '', nickname: '', phone: '', avatar: '', source: '', status: 1,
  wallet: { id: 0, balance: 0, total_recharged: 0, total_spent: 0, status: 1 }
})
const wallet = computed(() => profile.wallet || {})
const walletBalance = computed(() => {
  const b = profile.wallet?.balance
  return typeof b === 'number' ? b.toFixed(2) : '0.00'
})
const transactions = ref([])
const showTx = ref(false)
const showEdit = ref(false)
const editForm = reactive({ nickname: '', phone: '' })

function fmt(v) {
  if (v === null || v === undefined) return '0.00'
  const n = typeof v === 'number' ? v : parseFloat(v)
  return isNaN(n) ? '0.00' : n.toFixed(2)
}
function typeLabel(t) {
  return { recharge: '充值', payment: '付款', refund: '退款', adjustment: '调整' }[t] || t
}

async function fetchProfile() {
  loading.value = true
  try {
    const resp = await http.get('/consumer/profile')
    const d = resp.data || resp
    Object.assign(profile, d)
    if (d.wallet) profile.wallet = d.wallet
    editForm.nickname = d.nickname || ''
    editForm.phone = d.phone || ''
    console.log('[Profile] loaded, balance:', d.wallet?.balance)
  } catch (e) {
    console.error('[Profile] load failed:', e)
    ElMessage.error('加载个人信息失败')
  } finally {
    loading.value = false
  }
}

async function fetchTx() {
  txLoading.value = true
  try {
    const resp = await http.get('/consumer/wallet/transactions', { params: { page: 1, page_size: 50 } })
    const d = resp.data || resp
    transactions.value = d.items || []
  } catch (e) {
    console.error('[Profile] tx load failed:', e)
    transactions.value = []
  } finally {
    txLoading.value = false
  }
}

async function doUpdate() {
  try {
    await http.put('/consumer/profile', { nickname: editForm.nickname, phone: editForm.phone })
    showEdit.value = false
    fetchProfile()
    ElMessage.success('已更新')
  } catch (e) {
    ElMessage.error('更新失败')
  }
}

function logout() { auth.logout(); router.replace('/login') }

onMounted(fetchProfile)
</script>
