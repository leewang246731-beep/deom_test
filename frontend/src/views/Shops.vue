<template>
  <div>
    <div style="margin-bottom:16px;display:flex;justify-content:space-between">
      <h3 style="margin:0">店铺管理</h3>
      <el-button type="primary" @click="showBind = true">绑定店铺</el-button>
    </div>
    <el-table :data="shops" border stripe v-loading="loading" empty-text="暂无店铺，请先绑定">
      <el-table-column prop="shop_name" label="店铺名称" min-width="160" />
      <el-table-column prop="platform_type" label="平台" width="100" />
      <el-table-column prop="product_count" label="商品数" width="80" />
      <el-table-column prop="order_count" label="订单数" width="80" />
      <el-table-column prop="sync_status" label="同步状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.sync_status === 'idle' ? 'success' : row.sync_status === 'syncing' ? 'warning' : 'danger'" size="small">{{ row.sync_status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" @click="handleSync(row)">同步</el-button>
          <el-popconfirm title="解绑将删除该店铺所有数据" @confirm="handleUnbind(row.id)">
            <template #reference><el-button size="small" type="danger" text>解绑</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showBind" title="绑定店铺" width="400px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="店铺名称"><el-input v-model="form.shop_name" placeholder="例：模拟数码专营店" /></el-form-item>
        <el-form-item label="平台类型">
          <el-select v-model="form.platform_type" style="width:100%">
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
  </div>
</template>

<script setup>
import { ref, onMounted, reactive } from 'vue'
import { getShops, bindShop, unbindShop, syncShop } from '../api'
import { ElMessage } from 'element-plus'

const shops = ref([])
const loading = ref(false)
const binding = ref(false)
const showBind = ref(false)
const form = reactive({ shop_name: '', platform_type: 'mock' })

async function fetch() { loading.value = true; try { const res = await getShops(); shops.value = res.data || [] } finally { loading.value = false } }
async function handleBind() {
  if (!form.shop_name) return ElMessage.warning('请输入店铺名称')
  binding.value = true
  try { await bindShop({ ...form }); showBind.value = false; form.shop_name = ''; ElMessage.success('绑定成功'); await fetch() }
  finally { binding.value = false }
}
async function handleSync(row) {
  try { const res = await syncShop(row.id); ElMessage.success(res.msg || '同步完成'); await fetch() }
  catch { /* error shown by interceptor */ }
}
async function handleUnbind(id) { await unbindShop(id); ElMessage.success('已解绑'); await fetch() }

onMounted(fetch)
</script>
