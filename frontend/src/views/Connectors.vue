<template>
  <div>
    <h3 style="margin:0 0 16px">平台连接器</h3>

    <el-alert type="info" :closable="false" style="margin-bottom:16px">
      连接器负责从各电商平台拉取商品、订单、会话数据。支持淘宝、京东、vMall 以及 Mock 模拟数据。
    </el-alert>

    <!-- Scheduler panel -->
    <el-card style="margin-bottom:16px">
      <div style="display:flex;align-items:center;justify-content:space-between">
        <div>
          <strong>定时同步</strong>
          <el-tag type="success" size="small" style="margin-left:8px">运行中</el-tag>
          <span style="margin-left:12px;color:#909399;font-size:13px">每 30 分钟自动同步全部活跃店铺</span>
        </div>
        <el-button type="primary" size="small" @click="handleSyncAll" :loading="syncingAll">立即全量同步</el-button>
      </div>
      <div v-if="schedStatus?.recent_logs?.length" style="margin-top:12px">
        <p style="margin:0 0 8px;font-size:13px;color:#606266">最近同步记录：</p>
        <div v-for="(entry, i) in schedStatus.recent_logs.slice(0, 3)" :key="i" style="font-size:12px;color:#909399;margin-bottom:4px">
          {{ entry.time?.slice(0, 16) }}
          <span v-for="r in entry.results" :key="r.shop_id" style="margin-left:8px">
            {{ r.shop_name }}:
            <span :style="{color: r.status === 'ok' ? '#67c23a' : '#f56c6c'}">{{ r.status === 'ok' ? `+${r.new || 0} / 更新${r.updated || 0}` : r.error }}</span>
          </span>
        </div>
      </div>
    </el-card>

    <el-table :data="connectors" border stripe v-loading="loading" empty-text="暂无店铺，请先绑定店铺">
      <el-table-column prop="shop_name" label="店铺名称" min-width="150" />
      <el-table-column label="平台" width="90">
        <template #default="{ row }">
          <el-tag :type="platformTag(row.platform_type)" size="small">{{ row.platform_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.sync_status === 'idle' ? 'success' : row.sync_status === 'syncing' ? 'warning' : 'danger'" size="small">
            {{ row.sync_status === 'idle' ? '就绪' : row.sync_status === 'syncing' ? '同步中' : '错误' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="product_count" label="商品" width="70" />
      <el-table-column prop="order_count" label="订单" width="70" />
      <el-table-column prop="conversation_count" label="会话" width="70" />
      <el-table-column label="最近同步" width="170">
        <template #default="{ row }">{{ row.last_sync_at ? row.last_sync_at.slice(0, 16) : '从未' }}</template>
      </el-table-column>
      <el-table-column label="Token" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.access_token" type="success" size="small">有效</el-tag>
          <el-tag v-else type="info" size="small">未获取</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="handleSync(row.id)" :loading="syncingId === row.id">同步</el-button>
          <el-button size="small" type="danger" text @click="handleDelete(row)">解绑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div style="margin-top:16px">
      <el-button type="primary" @click="showBind = true">绑定新店铺</el-button>
    </div>

    <el-dialog v-model="showBind" title="绑定店铺" width="480px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="平台类型" required>
          <el-select v-model="form.platform_type" style="width:100%">
            <el-option label="Mock 模拟数据" value="mock" />
            <el-option label="vMall 电商系统" value="vmall" />
            <el-option label="淘宝" value="taobao" />
            <el-option label="京东" value="jd" />
          </el-select>
        </el-form-item>
        <el-form-item label="店铺名称" required><el-input v-model="form.shop_name" /></el-form-item>
        <el-form-item v-if="form.platform_type === 'vmall'" label="店铺URL"><el-input v-model="form.shop_url" placeholder="http://127.0.0.1:8020" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBind = false">取消</el-button>
        <el-button type="primary" :loading="binding" @click="handleBind">绑定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { getShops, bindShop, unbindShop, syncShop, getSchedulerStatus, triggerSyncAll } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const connectors = ref([])
const loading = ref(false)
const binding = ref(false)
const syncingId = ref(null)
const syncingAll = ref(false)
const showBind = ref(false)
const schedStatus = ref(null)
const form = reactive({ platform_type: 'mock', shop_name: '', shop_url: '' })

function platformTag(p) {
  const map = { mock: '', vmall: 'success', taobao: 'warning', jd: 'danger' }
  return map[p] || ''
}

async function fetch() {
  loading.value = true
  try {
    const res = await getShops()
    connectors.value = res.data || []
  } catch {
    connectors.value = []
  } finally { loading.value = false }
}

async function handleBind() {
  if (!form.shop_name.trim()) return ElMessage.warning('请输入店铺名称')
  binding.value = true
  try {
    await bindShop({ ...form })
    ElMessage.success('店铺已绑定')
    showBind.value = false
    Object.assign(form, { platform_type: 'mock', shop_name: '', shop_url: '' })
    fetch()
  } catch {
    // error shown by interceptor
  } finally { binding.value = false }
}

async function handleSync(id) {
  syncingId.value = id
  try {
    const res = await syncShop(id)
    ElMessage.success(res.msg || '同步完成')
    fetch()
  } catch {
    // error shown by interceptor
  } finally { syncingId.value = null }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定解绑"${row.shop_name}"？将清空该店铺所有数据。`, '危险操作', { type: 'warning' })
  } catch { return }
  try {
    await unbindShop(row.id)
    ElMessage.success('已解绑')
    fetch()
  } catch {
    // error shown by interceptor
  }
}

async function loadSched() {
  try {
    const r = await getSchedulerStatus()
    schedStatus.value = r.data
  } catch {
    schedStatus.value = null
  }
}

async function handleSyncAll() {
  syncingAll.value = true
  try {
    await triggerSyncAll()
    ElMessage.success('全量同步已触发，请稍后刷新查看结果')
    loadSched()
  } catch {
    // error shown by interceptor
  } finally { syncingAll.value = false }
}

fetch()
loadSched()
</script>
