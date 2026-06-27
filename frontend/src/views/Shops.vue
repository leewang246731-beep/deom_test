<template>
  <div>
    <div style="margin-bottom:16px;display:flex;justify-content:space-between">
      <h3 style="margin:0">店铺管理</h3>
      <el-button type="primary" @click="showBind = true">绑定店铺</el-button>
    </div>
    <el-table :data="shops" border stripe v-loading="loading" empty-text="暂无店铺，请先绑定">
      <el-table-column prop="shop_name" label="店铺名称" min-width="160" />
      <el-table-column prop="platform_type" label="平台" width="100">
        <template #default="{ row }">
          <el-tag :type="row.platform_type === 'vmall' ? '' : 'info'" size="small" effect="plain">{{ row.platform_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="bind_status" label="绑定状态" width="110">
        <template #default="{ row }">
          <template v-if="row.platform_type === 'vmall'">
            <el-tag v-if="row.bind_status === 'active'" type="success" size="small">已绑定</el-tag>
            <el-tag v-else-if="row.bind_status === 'pending'" type="warning" size="small">待确认</el-tag>
            <el-tag v-else type="info" size="small">未绑定</el-tag>
          </template>
          <span v-else style="color:#909399;font-size:12px">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="product_count" label="商品数" width="80" />
      <el-table-column prop="order_count" label="订单数" width="80" />
      <el-table-column prop="sync_status" label="同步状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.sync_status === 'idle' ? 'success' : row.sync_status === 'syncing' ? 'warning' : 'danger'" size="small">{{ row.sync_status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" min-width="280">
        <template #default="{ row }">
          <el-button size="small" :loading="syncingId === row.id" @click="handleSync(row)">同步</el-button>
          <template v-if="row.platform_type === 'vmall'">
            <el-button v-if="row.bind_status !== 'active'" size="small" type="success" @click="handleGenToken(row)">生成绑定码</el-button>
            <el-button v-else size="small" type="warning" @click="handleShowToken(row)">查看绑定码</el-button>
          </template>
          <el-popconfirm title="解绑将删除该店铺所有数据" @confirm="handleUnbind(row.id)">
            <template #reference><el-button size="small" type="danger" text>解绑</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <!-- Bind dialog -->
    <el-dialog v-model="showBind" title="绑定店铺" width="450px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="店铺名称"><el-input v-model="form.shop_name" placeholder="例：数码旗舰店" /></el-form-item>
        <el-form-item label="平台类型">
          <el-select v-model="form.platform_type" style="width:100%">
            <el-option label="vMall 虚拟电商" value="vmall" />
            <el-option label="Mock（模拟演示）" value="mock" />
            <el-option label="淘宝（二期）" value="taobao" disabled />
            <el-option label="京东（二期）" value="jd" disabled />
            <el-option label="抖音（三期）" value="douyin" disabled />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBind = false">取消</el-button>
        <el-button type="primary" :loading="binding" @click="handleBind">确认绑定</el-button>
      </template>
    </el-dialog>

    <!-- Token dialog -->
    <el-dialog v-model="showToken" title="vMall 绑定码" width="500px">
      <el-alert v-if="tokenData.bind_status === 'active'" type="success" :closable="false" style="margin-bottom:16px">
        该店铺已成功绑定到 vMall
      </el-alert>
      <el-alert v-else type="warning" :closable="false" style="margin-bottom:16px">
        请将以下信息发送给 vMall 商户，由商户在后台完成绑定确认
      </el-alert>
      <el-form label-width="80px">
        <el-form-item label="SaaS 地址">
          <el-input :model-value="tokenData.saas_url || ''" readonly>
            <template #append><el-button @click="copyText(tokenData.saas_url)">复制</el-button></template>
          </el-input>
        </el-form-item>
        <el-form-item label="绑定码">
          <el-input :model-value="tokenData.bind_token || ''" readonly style="font-family:monospace;font-size:16px">
            <template #append><el-button type="primary" @click="copyText(tokenData.bind_token)">复制</el-button></template>
          </el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showToken = false">关闭</el-button>
        <el-button v-if="tokenData.bind_status !== 'active'" type="warning" :loading="regenLoading" @click="handleRegenToken">重新生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { getShops, bindShop, unbindShop, syncShop, generateBindToken, regenerateToken } from '../api'
import { ElMessage } from 'element-plus'

const shops = ref([])
const loading = ref(false)
const binding = ref(false)
const regenLoading = ref(false)
const syncingId = ref(null)
const showBind = ref(false)
const showToken = ref(false)
const tokenData = ref({})
const currentShopId = ref(null)
const form = reactive({ shop_name: '', platform_type: 'vmall' })

async function fetch() {
  loading.value = true
  try {
    const res = await getShops()
    shops.value = res.data || []
  } catch {
    ElMessage.error('加载店铺列表失败')
  } finally {
    loading.value = false
  }
}

async function handleBind() {
  if (!form.shop_name) { ElMessage.warning('请输入店铺名称'); return }
  binding.value = true
  try {
    await bindShop({ ...form })
    ElMessage.success('店铺绑定成功')
    showBind.value = false
    form.shop_name = ''
    await fetch()
  } catch {
    // error shown by interceptor
  } finally {
    binding.value = false
  }
}

async function handleSync(row) {
  syncingId.value = row.id
  try {
    const res = await syncShop(row.id)
    ElMessage.success(res.msg || '同步完成')
    await fetch()
  } catch {
    // error shown by interceptor
  } finally {
    syncingId.value = null
  }
}

async function handleUnbind(id) {
  try {
    await unbindShop(id)
    ElMessage.success('店铺已解绑')
    await fetch()
  } catch {
    // error shown by interceptor
  }
}

async function handleGenToken(row) {
  currentShopId.value = row.id
  try {
    const res = await generateBindToken(row.id)
    tokenData.value = { ...res.data, saas_url: tokenData.value.saas_url || 'http://127.0.0.1:8010' }
    showToken.value = true
    ElMessage.success('绑定码已生成')
    await fetch()
  } catch {
    // error shown by interceptor
  }
}

async function handleShowToken(row) {
  currentShopId.value = row.id
  tokenData.value = {
    bind_token: row.bind_token || '',
    bind_status: row.bind_status || 'active',
    saas_url: 'http://127.0.0.1:8010',
    shop_name: row.shop_name,
  }
  showToken.value = true
}

async function handleRegenToken() {
  if (!currentShopId.value) return
  regenLoading.value = true
  try {
    const res = await regenerateToken(currentShopId.value)
    tokenData.value.bind_token = res.data.bind_token
    tokenData.value.bind_status = res.data.bind_status
    ElMessage.success('绑定码已重新生成')
    await fetch()
  } catch {
    // error shown by interceptor
  } finally {
    regenLoading.value = false
  }
}

function copyText(text) {
  navigator.clipboard.writeText(text).then(() => ElMessage.success('已复制'))
}

onMounted(fetch)
</script>
